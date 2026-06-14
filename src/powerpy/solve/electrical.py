# -*- coding: utf-8 -*-
"""Electrical solve: per-cell operating point -> P_elec, wired for coupling.

This is the bridge that closes the electrical<->thermal loop. The thermal solver
needs each cell's extracted/dissipated electrical power ``P_elec``; this module
computes it from a SPICE solve of the whole :class:`~powerpy.model.circuit.Circuit`:

    circuit.build_probed_netlist()  ->  netlist + {id: (node+, node-, ammeter)}
    drive the bus, run a SPICE .op   ->  node voltages + ammeter branch currents
    per cell: V = V(+) - V(-),  I = i(ammeter),  P_elec = V * I

Sign convention matches the thermal model: a generating cell delivers power
(``P_elec > 0`` -> energy leaves as electricity -> cooler); a reverse-biased cell
has ``V < 0`` so ``P_elec < 0`` -> energy dumped as heat -> hotter.

The SPICE runner is **injected** as ``run(netlist) -> Solution`` where ``Solution``
has ``.voltage(node)`` and ``.current(branch)``. The production runner uses the
legacy ``ngspice`` (``electric.ng_sim``); tests inject a deterministic mock. So
the *wiring* is testable now, and swapping in real ngspice is a one-arg change
once ``cell.buildModel`` is repaired (see ``docs/CELL_PY_REPAIR.md``).
"""
from __future__ import annotations

from typing import Callable, Dict, List, Optional, Tuple

import numpy as np


class Solution:
    """Minimal SPICE-result interface. Any object exposing ``voltage(node)`` and
    ``current(branch)`` works; this is the plain in-memory implementation."""

    def __init__(self, voltages: Dict[str, float], currents: Dict[str, float]):
        self._v = {k.lower(): float(v) for k, v in voltages.items()}
        self._i = {k.lower(): float(v) for k, v in currents.items()}

    def voltage(self, node: str) -> float:
        if str(node) == "0":
            return 0.0                     # ground
        return self._v[str(node).lower()]

    def current(self, branch: str) -> float:
        return self._i[str(branch).lower()]


def _default_ngspice_backend():
    """One persistent NgSpiceShared with a ``solve(netlist) -> Solution``.

    The legacy ``electric.ng_sim`` calls ``NgSpiceShared.new_instance()`` (and
    ``destroy()``) on EVERY simulation -- the dominant cost when the coupling loop
    re-solves the circuit many times. This backend creates the instance ONCE and
    only swaps the circuit between solves (``load_circuit`` / ``remove_circuit``).
    Needs the ngspice shared library at call time (validate on real hardware).
    """
    from ..ngspice.Shared import NgSpiceShared      # guarded: only when used
    inst = NgSpiceShared.new_instance()

    class _Backend:
        def solve(self, netlist: str) -> Solution:
            inst.load_circuit(str(netlist))
            try:
                inst.run()
            except Exception:                          # ngspice raises on some .op
                pass
            plot = inst.plot(simulation=None, plot_name=inst.last_plot)

            class _PlotSolution:
                def voltage(self, node):
                    if str(node) == "0":
                        return 0.0
                    return plot["V(%s)" % node].to_waveform()[0].value

                def current(self, branch):
                    return plot["%s#branch" % str(branch).lower()].to_waveform()[0].value

            sol = _PlotSolution()
            inst.remove_circuit()                      # clear circuit, KEEP instance
            return sol

    return _Backend()


def ngspice_runner(extra_cards: str = "", *, instance_factory: Callable[[], object] = None
                   ) -> Callable[[str], Solution]:
    """Build a production runner that REUSES one ngspice instance across calls (P1).

    ``instance_factory() -> backend`` (with ``backend.solve(netlist) -> Solution``)
    is called **once**, lazily, on the first run; every later call reuses it. The
    default factory builds a persistent :class:`NgSpiceShared`. Inject a factory to
    swap in a mock (or a differently-configured ngspice). The error surfaces only
    when the runner is first called without a working backend.
    """
    factory = instance_factory or _default_ngspice_backend
    state = {"backend": None}

    def run(netlist: str) -> Solution:
        if state["backend"] is None:
            try:
                state["backend"] = factory()           # created ONCE, then reused
            except Exception as exc:                    # pragma: no cover
                raise RuntimeError(
                    "ngspice runner needs powerpy.ngspice (PySpice) or an injected "
                    "instance_factory. Cause: %s" % exc)
        return state["backend"].solve(str(netlist) + extra_cards)

    return run


def per_cell_vi(circuit, v_bus: float, run: Callable[[str], "Solution"], *,
                bus_node: str = "out", gnd_node: str = "0",
                analysis_cards: str = ".op\n") -> Dict[str, Tuple[float, float]]:
    """Solve the circuit at bus voltage ``v_bus`` and return ``{id: (V, I)}`` per cell."""
    netlist, probes = circuit.build_probed_netlist(bus_node, gnd_node)
    full = "%s\nV_bus %s %s %g\n%s.end\n" % (netlist, bus_node, gnd_node, v_bus, analysis_cards)
    sol = run(full)
    out: Dict[str, Tuple[float, float]] = {}
    for cid, (npos, nneg, amm) in probes.items():
        v = sol.voltage(npos) - sol.voltage(nneg)
        i = sol.current(amm)
        out[cid] = (v, i)
    return out


def per_cell_power(circuit, v_bus: float, run: Callable[[str], "Solution"],
                   order: Optional[List[str]] = None, **kw):
    """Return ``(ids, p_elec_array)`` with ``P_elec = V*I`` per cell, in ``order``
    (defaults to ``circuit.cell_ids`` so it lines up with the thermal area array)."""
    vi = per_cell_vi(circuit, v_bus, run, **kw)
    ids = list(order) if order is not None else list(circuit.cell_ids)
    p = np.array([vi[cid][0] * vi[cid][1] for cid in ids], dtype=float)
    return ids, p


def make_power_fn(circuit, v_bus: float, run: Callable[[str], "Solution"], *,
                  order: Optional[List[str]] = None,
                  set_temps: Optional[Callable[[object, np.ndarray], None]] = None,
                  **kw) -> Callable[[np.ndarray], np.ndarray]:
    """Return ``power_fn(T_front) -> p_elec_array`` for :func:`powerpy.solve.coupling.couple`.

    Each call (re)solves the circuit and returns per-cell ``P_elec`` in ``order``.
    ``set_temps(circuit, T)`` is the hook that pushes the current temperatures into
    the cell models before the electrical solve (e.g. ``cell.setTemperature``), so
    the coupling captures the real temperature-dependence of the IV curve. Until
    ``cell.py`` is repaired it can be left ``None`` (temperature-independent solve).
    """
    ids = list(order) if order is not None else list(circuit.cell_ids)

    def power_fn(t_front_c: np.ndarray) -> np.ndarray:
        if set_temps is not None:
            set_temps(circuit, np.asarray(t_front_c, float))
        _, p = per_cell_power(circuit, v_bus, run, order=ids, **kw)
        return p

    return power_fn
