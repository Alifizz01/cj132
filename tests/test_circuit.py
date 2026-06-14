# -*- coding: utf-8 -*-
"""Tests for the parametric Circuit (topology, registry, faults, netlist).

Uses a STUB cell so the topology is exercised without the OCR-damaged legacy
``cell`` or ngspice. Loaded by file path to avoid the package __init__.
"""
import importlib.util
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_PKG = os.path.join(_HERE, "..", "src", "powerpy")


def _load(relpath, name=None):
    name = name or os.path.splitext(os.path.basename(relpath))[0]
    spec = importlib.util.spec_from_file_location(name, os.path.join(_PKG, relpath))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


circ = _load("model/circuit.py")


class StubCell:
    """Minimal duck-typed cell: a season and a trivial SPICE subcircuit."""
    def __init__(self, name="stub"):
        self.season = 1
        self._name = name

    def setSeason(self, season):
        self.season = season

    def buildModel(self, name=None, dark=False):
        name = name or self._name
        sub = ".subckt %s high low\nR1 high low 1\n.ends %s\n" % (name, name)
        return sub, name


def _build(**kw):
    p = dict(cells_per_line=2, lines_parallel=2, modules_per_block=2, n_blocks=2)
    p.update(kw)
    return circ.Circuit.from_prototype(StubCell(), **p)


def test_cell_count_and_ids():
    c = _build()
    assert c.n_cells == 2 * 2 * 2 * 2 == 16
    assert "B0.M0.L0.C0" in c.cells
    assert "B1.M1.L1.C1" in c.cells
    # ids are unique
    assert len(set(c.cell_ids)) == 16


def test_series_parallel_bookkeeping():
    c = _build()
    # defaults: line series, module parallel, block series, circuit parallel
    # series cells = cells_per_line(2) * modules_per_block(2) = 4
    assert c.nominal_series_cells() == 4
    # parallel paths = lines_parallel(2) * n_blocks(2) = 4
    assert c.nominal_parallel_paths() == 4


def test_combine_is_configurable():
    # flip blocks to series and circuit to series -> more cells in series
    c = _build(block_combine="series", circuit_combine="series")
    assert c.nominal_series_cells() == 2 * 2 * 2  # cells_per_line*modules*blocks = 8


def test_fault_injection_is_local():
    c = _build()
    c.fail("B0.M0.L0.C0", "dead")
    assert c.cells["B0.M0.L0.C0"].season == 0
    # every other cell is untouched (deepcopy broke the reference)
    others = [cid for cid in c.cell_ids if cid != "B0.M0.L0.C0"]
    assert all(c.cells[cid].season == 1 for cid in others)


def test_fault_unknown_id_raises():
    c = _build()
    try:
        c.fail("B9.M9.L9.C9", "dead")
        assert False, "expected KeyError"
    except KeyError:
        pass


def test_netlist_has_instance_per_cell_and_rails():
    c = _build()
    net = c.build_netlist(bus_node="out", gnd_node="0")
    # one X instance per cell
    assert net.count("\nXB") + net.startswith("XB") == 16 or net.count("XB") == 16
    assert "out" in net and "\n" in net
    # the cell subcircuit is emitted
    assert ".subckt" in net and ".ends" in net


if __name__ == "__main__":
    passed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn(); print("PASS", name); passed += 1
    print("\n%d/%d tests passed" % (passed, passed))
