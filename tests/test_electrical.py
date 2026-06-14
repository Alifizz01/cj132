# -*- coding: utf-8 -*-
"""Validation harness for the electrical<->thermal wiring (solve/electrical.py).

Proves the full chain WITHOUT real ngspice or the OCR-damaged cell: a stub cell
builds a subcircuit, the circuit emits a probed netlist (per-cell ammeters), a
deterministic MOCK SPICE solution supplies node voltages + branch currents, and
we check per-cell V*I -> P_elec and that this power_fn drives the coupling loop
so the most-dissipating cell ends up hottest.

Swapping the mock for ``ngspice_runner()`` and the stub for a repaired cell is
all that remains to make it a real end-to-end simulation.
"""
import importlib.util
import os
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_PKG = os.path.join(_HERE, "..", "src", "powerpy")


def _load(relpath, name=None):
    name = name or os.path.splitext(os.path.basename(relpath))[0]
    spec = importlib.util.spec_from_file_location(name, os.path.join(_PKG, relpath))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


th = _load("solve/thermal.py")        # registered "thermal" so coupling resolves
cp = _load("solve/coupling.py")
circ = _load("model/circuit.py")
elec = _load("solve/electrical.py")


class StubCell:
    """Duck-typed cell: a trivial SPICE subcircuit + temperature hook."""
    def __init__(self, name="stub"):
        self.season = 1
        self.temperature = 28.0
        self._name = name

    def setSeason(self, s):
        self.season = s

    def setTemperature(self, t):
        self.temperature = t

    def buildModel(self, name=None, dark=False):
        name = name or self._name
        return ".subckt %s p n\nR1 p n 1\n.ends %s\n" % (name, name), name


def _parallel4():
    """Four cells all between the bus rail and ground (clean, shared rails)."""
    return circ.Circuit.from_prototype(
        StubCell(), cells_per_line=1, lines_parallel=4,
        modules_per_block=1, n_blocks=1)


def _grid2x2():
    return circ.Circuit.from_prototype(
        StubCell(), cells_per_line=2, lines_parallel=2,
        modules_per_block=1, n_blocks=1)


# --------------------------------------------------- mapping (2x2, signs irrelevant)
def test_per_cell_vi_mapping_2x2():
    c = _grid2x2()
    _, probes = c.build_probed_netlist()
    nodes = set()
    for (npos, nneg, _amm) in probes.values():
        nodes.update({npos, nneg})
    volts = {n: 1.0 + 0.5 * k for k, n in enumerate(sorted(nodes - {"0"}))}
    currs = {amm: 0.4 + 0.01 * k for k, (_, _, amm) in enumerate(probes.values())}
    sol = elec.Solution(volts, currs)

    vi = elec.per_cell_vi(c, v_bus=70.0, run=lambda netlist: sol)
    assert set(vi) == set(probes)
    for cid, (npos, nneg, amm) in probes.items():
        exp_v = (0.0 if npos == "0" else volts[npos]) - (0.0 if nneg == "0" else volts[nneg])
        assert abs(vi[cid][0] - exp_v) < 1e-12
        assert abs(vi[cid][1] - currs[amm]) < 1e-12


# --------------------------------------------------- P = V*I with correct signs
def test_per_cell_power_sign_convention():
    c = _parallel4()
    _, probes = c.build_probed_netlist()           # all cells: out -> 0
    volts = {"out": 2.3}
    amms = [amm for (_, _, amm) in probes.values()]
    currs = dict(zip(amms, [0.48, 0.48, 0.48, -4.0]))   # last cell: reversed current
    sol = elec.Solution(volts, currs)

    ids, p = elec.per_cell_power(c, v_bus=2.3, run=lambda netlist: sol)
    assert len(p) == 4
    assert np.allclose(np.sort(p), np.sort([2.3 * i for i in [0.48, 0.48, 0.48, -4.0]]))
    assert (p > 0).sum() == 3 and (p < 0).sum() == 1   # one dissipating cell


# --------------------------------------------------- drives the coupling loop
def test_make_power_fn_drives_coupling():
    c = _parallel4()
    _, probes = c.build_probed_netlist()
    volts = {"out": 2.3}
    amms = [amm for (_, _, amm) in probes.values()]
    currs = dict(zip(amms, [0.48, 0.48, 0.48, -4.0]))
    sol = elec.Solution(volts, currs)

    ids, p = elec.per_cell_power(c, v_bus=2.3, run=lambda netlist: sol)
    pf = elec.make_power_fn(c, v_bus=2.3, run=lambda netlist: sol, order=ids)

    out = cp.couple(
        power_fn=pf, area=np.full(len(ids), 0.003),
        alpha_front=0.97, alpha_rear=0.93, epsilon_front=0.90, epsilon_rear=0.89,
        c_cond=1000.0, p_sun=1367.0,
    )
    assert out.converged
    hottest = int(np.argmax(out.t_front_c))
    most_dissipating = int(np.argmin(p))
    assert ids[hottest] == ids[most_dissipating]      # reverse cell -> hot-spot


# --------------------------------------------------- set_temps hook is invoked
def test_set_temps_hook_called():
    c = _parallel4()
    _, probes = c.build_probed_netlist()
    sol = elec.Solution({"out": 2.3}, {amm: 0.48 for (_, _, amm) in probes.values()})
    seen = {"calls": 0, "last_T": None}

    def set_temps(circuit, T):
        seen["calls"] += 1
        seen["last_T"] = np.asarray(T, float).copy()

    pf = elec.make_power_fn(c, v_bus=2.3, run=lambda netlist: sol, set_temps=set_temps)
    cp.couple(power_fn=pf, area=np.full(c.n_cells, 0.003),
              alpha_front=0.97, alpha_rear=0.93, epsilon_front=0.90, epsilon_rear=0.89,
              c_cond=1000.0, p_sun=1367.0)
    assert seen["calls"] >= 1 and seen["last_T"] is not None


def test_ngspice_runner_reuses_one_instance():
    """P1: the ngspice backend is created ONCE and reused across calls."""
    calls = {"n": 0}

    class _FakeBackend:
        def solve(self, netlist):
            return elec.Solution({"out": 2.3}, {})

    def factory():
        calls["n"] += 1
        return _FakeBackend()

    run = elec.ngspice_runner(instance_factory=factory)
    for _ in range(5):
        run("dummy netlist")
    assert calls["n"] == 1       # not 5 — instance reused, not recreated


if __name__ == "__main__":
    passed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn(); print("PASS", name); passed += 1
    print("\n%d/%d tests passed" % (passed, passed))
