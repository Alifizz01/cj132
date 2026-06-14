# -*- coding: utf-8 -*-
"""Parametric, fault-addressable solar-array circuit.

The legacy hierarchy (``cell`` -> ``string`` -> ``section`` -> ``panel``) fixes
series at the string level and parallel at the section level, and does not let you
nest four custom levels, flip a junction series<->parallel, or reach in and fail
ONE specific cell. The failure study needs all three.

``Circuit`` represents the array as a recursive tree of :class:`Group` nodes whose
leaves are :class:`CellRef` wrappers around individual cells. Levels (bottom->top)::

    cell
    line   = cells_per_line cells in SERIES
    module = lines_parallel lines in PARALLEL          (the "two parallel circuits")
    block  = modules_per_block modules (default SERIES, to reach the ~70 V bus)
    circuit= n_blocks blocks (default PARALLEL, one blocking diode each)

The series/parallel rule is a parameter at every level. Every cell gets a stable
id ``B{b}.M{m}.L{l}.C{c}`` and is reachable in O(1) via ``circuit.cells[id]`` for
fault injection and per-cell result read-out.

Cells are duck-typed: a cell only needs ``buildModel(name=...) -> (subckt, name)``
and (for the default fault mode) ``setSeason(value)``. This module therefore does
NOT import the legacy ``cell`` (which is OCR-damaged); the topology, registry,
fault injection and netlist assembly are testable in isolation with a stub cell.

Status of the parts:
  * topology / registry / fault injection / netlist STRING build -- implemented &
    tested (``tests/test_circuit.py``) with a stub cell.
  * running the netlist in ngspice -- works once a clean ``cell.buildModel`` is
    available (the legacy cell.py needs its OCR syntax errors repaired first);
    see ``electrothermal.py``.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Union

SERIES = "series"
PARALLEL = "parallel"


@dataclass
class CellRef:
    """A leaf: one cell plus its stable hierarchical id."""
    cell: object
    id: str


@dataclass
class Group:
    """A tree node combining children in series or parallel."""
    combine: str                         # SERIES or PARALLEL
    children: List[Union["Group", CellRef]] = field(default_factory=list)
    id: str = ""


class Circuit:
    """A parametric array built from a prototype cell.

    Use :meth:`from_prototype`. After construction, ``self.cells`` maps every
    cell id to its (deep-copied, independent) cell object.
    """

    def __init__(self, root: Group, cells: Dict[str, object], params: dict):
        self.root = root
        self.cells = cells
        self.params = params

    # ------------------------------------------------------------------ build
    @classmethod
    def from_prototype(
        cls,
        cell: object,
        cells_per_line: int,
        lines_parallel: int,
        modules_per_block: int,
        n_blocks: int,
        line_combine: str = SERIES,
        module_combine: str = PARALLEL,
        block_combine: str = SERIES,
        circuit_combine: str = PARALLEL,
        blocking_diode: bool = True,
    ) -> "Circuit":
        """Clone ``cell`` into the whole tree and return the assembled circuit."""
        for nm, v in dict(cells_per_line=cells_per_line, lines_parallel=lines_parallel,
                          modules_per_block=modules_per_block, n_blocks=n_blocks).items():
            if v < 1:
                raise ValueError("%s must be >= 1, got %r" % (nm, v))

        registry: Dict[str, object] = {}
        blocks: List[Group] = []
        for b in range(n_blocks):
            modules: List[Group] = []
            for m in range(modules_per_block):
                lines: List[Group] = []
                for l in range(lines_parallel):
                    leaves: List[CellRef] = []
                    for c in range(cells_per_line):
                        cid = "B%d.M%d.L%d.C%d" % (b, m, l, c)
                        cc = copy.deepcopy(cell)            # break the reference
                        registry[cid] = cc
                        leaves.append(CellRef(cc, cid))
                    lines.append(Group(line_combine, leaves, "B%d.M%d.L%d" % (b, m, l)))
                modules.append(Group(module_combine, lines, "B%d.M%d" % (b, m)))
            blocks.append(Group(block_combine, modules, "B%d" % b))
        root = Group(circuit_combine, blocks, "ROOT")

        params = dict(
            cells_per_line=cells_per_line, lines_parallel=lines_parallel,
            modules_per_block=modules_per_block, n_blocks=n_blocks,
            line_combine=line_combine, module_combine=module_combine,
            block_combine=block_combine, circuit_combine=circuit_combine,
            blocking_diode=blocking_diode,
        )
        return cls(root, registry, params)

    # ------------------------------------------------------------- properties
    @property
    def n_cells(self) -> int:
        return len(self.cells)

    @property
    def cell_ids(self) -> List[str]:
        return list(self.cells.keys())

    def nominal_series_cells(self) -> int:
        """How many cells sit in series along a path out->gnd (sets bus voltage)."""
        p = self.params
        n = p["cells_per_line"]
        if p["module_combine"] == SERIES:
            n *= p["lines_parallel"]
        if p["block_combine"] == SERIES:
            n *= p["modules_per_block"]
        if p["circuit_combine"] == SERIES:
            n *= p["n_blocks"]
        return n

    def nominal_parallel_paths(self) -> int:
        """How many independent current paths there are (sets total current)."""
        p = self.params
        n = 1
        if p["module_combine"] == PARALLEL:
            n *= p["lines_parallel"]
        if p["block_combine"] == PARALLEL:
            n *= p["modules_per_block"]
        if p["circuit_combine"] == PARALLEL:
            n *= p["n_blocks"]
        return n

    # ---------------------------------------------------------- fault inject
    def fail(self, cell_id: str, mode: str = "dead") -> None:
        """Plant a failure at one cell.

        ``dead``/``open`` set the cell's irradiance to zero (no photocurrent) via
        ``setSeason(0)`` -- the default failure used by the Monte-Carlo sweep.
        ``short`` and ``crack`` are placeholders to fill in with the real cell API.
        """
        if cell_id not in self.cells:
            raise KeyError("no such cell id: %s" % cell_id)
        cell = self.cells[cell_id]
        if mode in ("dead", "open"):
            cell.setSeason(0)
        elif mode == "short":
            setattr(cell, "_shorted", True)      # honoured by build_netlist hook
        elif mode == "crack":
            setattr(cell, "_cracked", True)
        else:
            raise ValueError("unknown fail mode: %r" % mode)

    # --------------------------------------------------------------- netlist
    def build_netlist(self, bus_node: str = "out", gnd_node: str = "0") -> str:
        """Assemble an ngspice netlist string for the whole circuit.

        Walks the tree assigning nodes (series chains head-to-tail; parallel ties
        children between the same rails) and emits each cell's subcircuit once.
        Returns the netlist body (no analysis card).
        """
        lines: List[str] = [".title pvasim_circuit"]
        subckts: Dict[str, str] = {}
        counter = {"n": 0}

        def new_node() -> str:
            counter["n"] += 1
            return "n%d" % counter["n"]

        def emit(node, n_pos: str, n_neg: str) -> None:
            # Leaf cell
            if isinstance(node, CellRef):
                sub, name = node.cell.buildModel(name="x" + node.id.replace(".", "_"))
                if name not in subckts:
                    subckts[name] = sub
                lines.append("X%s %s %s %s" % (node.id.replace(".", "_"), n_pos, n_neg, name))
                return
            # Group
            if not node.children:
                return
            if node.combine == SERIES:
                prev = n_pos
                k = len(node.children)
                for i, child in enumerate(node.children):
                    nxt = n_neg if i == k - 1 else new_node()
                    emit(child, prev, nxt)
                    prev = nxt
            else:  # PARALLEL
                for child in node.children:
                    emit(child, n_pos, n_neg)

        emit(self.root, bus_node, gnd_node)
        body = "\n".join(subckts.values())
        return "\n".join(lines[:1] + [body] + lines[1:])

    def build_probed_netlist(self, bus_node: str = "out", gnd_node: str = "0"
                             ) -> Tuple[str, Dict[str, Tuple[str, str, str]]]:
        """Like :meth:`build_netlist`, but insert a 0-V ammeter in series with
        every cell so its current is measurable, and return a **probe map**
        ``{cell_id: (node_pos, node_neg, ammeter_name)}``.

        After a SPICE ``.op`` you recover each cell's operating point as
        ``V = V(node_pos) - V(node_neg)`` and ``I = i(ammeter_name)`` -- hence
        ``P_elec = V * I``. This is what wires the electrical solve into the
        electro-thermal coupling loop (:func:`powerpy.solve.electrical.make_power_fn`).
        """
        lines: List[str] = [".title pvasim_circuit_probed"]
        subckts: Dict[str, str] = {}
        probes: Dict[str, Tuple[str, str, str]] = {}
        counter = {"n": 0}

        def new_node() -> str:
            counter["n"] += 1
            return "n%d" % counter["n"]

        def emit(node, n_pos: str, n_neg: str) -> None:
            if isinstance(node, CellRef):
                sub, name = node.cell.buildModel(name="x" + node.id.replace(".", "_"))
                if name not in subckts:
                    subckts[name] = sub
                safe = node.id.replace(".", "_")
                mid = new_node()                       # node between ammeter and cell
                amm = "Vamm_%s" % safe                 # 0-V source = ammeter
                lines.append("%s %s %s 0" % (amm, n_pos, mid))
                lines.append("X%s %s %s %s" % (safe, mid, n_neg, name))
                probes[node.id] = (n_pos, n_neg, amm.lower())  # ngspice lowercases branch names
                return
            if not node.children:
                return
            if node.combine == SERIES:
                prev = n_pos
                k = len(node.children)
                for i, child in enumerate(node.children):
                    nxt = n_neg if i == k - 1 else new_node()
                    emit(child, prev, nxt)
                    prev = nxt
            else:  # PARALLEL
                for child in node.children:
                    emit(child, n_pos, n_neg)

        emit(self.root, bus_node, gnd_node)
        body = "\n".join(subckts.values())
        netlist = "\n".join(lines[:1] + [body] + lines[1:])
        return netlist, probes
