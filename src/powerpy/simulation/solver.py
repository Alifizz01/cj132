"""High-fidelity ngspice path (optional, not yet wired up).

The analytic single-diode model in ``cell_level.py`` is enough for most
work and needs no native dependency. This module is the hook for the
high-fidelity path: turn a SimNode tree into a SPICE netlist, hand it to
the vendored ngspice shared-library binding, and read back the result
vectors.

When implemented it MUST (see manual PWR-001, chapters 5, 17, 18):

  1. build the netlist as a pure function -- a SimNode tree in, a
     netlist string out -- testable with no ngspice loaded;
  2. load it into the in-tree ``NgSpiceShared`` binding (never the pip
     ``PySpice`` package);
  3. raise :class:`SimulationError` on failure -- never return ``None``;
  4. protect the ngspice instance with ``try/finally`` so it is always
     destroyed, even when a circuit fails to converge;
  5. pin and record the exact ngspice DLL version it loads.
"""
from __future__ import annotations

from powerpy.simulation.base import SimNode


class SimulationError(RuntimeError):
    """Raised when the circuit solver fails to produce a valid result."""


def build_netlist(node: SimNode) -> str:
    """Turn a SimNode tree into a SPICE netlist string (pure function)."""
    raise NotImplementedError(
        "build_netlist: ngspice path not yet wired up -- see this "
        "module's docstring and manual PWR-001 ch.17-18.")


def run_netlist(netlist: str) -> dict:
    """Run a netlist through the ngspice binding; return result vectors."""
    raise NotImplementedError(
        "run_netlist: ngspice path not yet wired up -- see this "
        "module's docstring and manual PWR-001 ch.17-18.")
