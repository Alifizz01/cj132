# -*- coding: utf-8 -*-
"""Panel layout convention: a grid-map + palette.

The panel is described as a 2-D **grid** of single-character tiles, each keyed to
a **palette** entry that carries that tile's full properties (is it a cell, its
optical properties, which electrical string it belongs to, ...). This makes
asymmetric layouts and empty (no-cell) regions trivial to author, keeps the
layout human-readable and version-controllable as text/JSON, and -- crucially --
the grid directly yields the 4-neighbour **adjacency** the lateral-conduction
solver needs (tile (r,c) borders (r+-1,c) and (r,c+-1)).

Empty / bare-substrate tiles are first-class: they absorb sunlight but generate
**no** electrical power (``generates_power == False``), so all absorbed sun stays
as heat -- which is why bare regions run hotter than cell regions, and (through
lateral conduction) can heat their neighbours.

Status: standalone (numpy + json only), tested in isolation.
"""
from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np


@dataclass(frozen=True)
class TileType:
    """One palette entry: what sits at a tile and its thermal/electrical role."""
    key: str
    name: str = ""
    is_cell: bool = False
    is_diode: bool = False
    alpha_front: float = 0.90    # front absorptivity (fraction of sun soaked up)
    alpha_rear: float = 0.90
    epsilon_front: float = 0.90  # front emissivity (how well it glows heat away)
    epsilon_rear: float = 0.90
    string: Optional[str] = None # electrical group/string id (None for bare/diode)
    block: Optional[str] = None  # series-block id this tile belongs to (None if n/a)
    cell_type: Optional[str] = None

    @property
    def generates_power(self) -> bool:
        """Only real cells convert absorbed sun to electricity (heat leaves)."""
        return self.is_cell


@dataclass
class PanelLayout:
    """A panel as a 2-D grid of palette keys plus the palette itself."""
    grid: np.ndarray                 # 2-D array of single-char keys
    palette: Dict[str, TileType]
    pitch_mm: float = 40.0           # tile pitch (centre-to-centre), millimetres
    name: str = ""
    # optional per-string / per-block electrical params (harness R, diode opts),
    # keyed by the same `string`/`block` ids the tiles carry. Empty unless the
    # layout JSON provides a "circuit" block.
    circuit_params: Dict[str, dict] = field(default_factory=dict)

    # --- shape helpers ----------------------------------------------------
    @property
    def n_rows(self) -> int:
        return int(self.grid.shape[0])

    @property
    def n_cols(self) -> int:
        return int(self.grid.shape[1])

    @property
    def n_tiles(self) -> int:
        return int(self.grid.size)

    def index(self, r: int, c: int) -> int:
        """Flat (row-major) index of tile (r, c)."""
        return r * self.n_cols + c

    def tile_at(self, r: int, c: int) -> TileType:
        return self.palette[str(self.grid[r, c])]

    def flat_keys(self) -> List[str]:
        return [str(k) for k in self.grid.flatten()]

    # --- derived structures the solver needs ------------------------------
    def neighbours(self) -> List[Tuple[int, int]]:
        """4-neighbour adjacency as undirected flat-index pairs (each once)."""
        pairs: List[Tuple[int, int]] = []
        for r in range(self.n_rows):
            for c in range(self.n_cols):
                i = self.index(r, c)
                if c + 1 < self.n_cols:
                    pairs.append((i, self.index(r, c + 1)))
                if r + 1 < self.n_rows:
                    pairs.append((i, self.index(r + 1, c)))
        return pairs

    def prop_arrays(self) -> Dict[str, np.ndarray]:
        """Flat per-tile property arrays (row-major), for the vectorised solve."""
        tt = [self.palette[k] for k in self.flat_keys()]
        return {
            "alpha_front": np.array([t.alpha_front for t in tt], float),
            "alpha_rear": np.array([t.alpha_rear for t in tt], float),
            "epsilon_front": np.array([t.epsilon_front for t in tt], float),
            "epsilon_rear": np.array([t.epsilon_rear for t in tt], float),
            "is_cell": np.array([t.is_cell for t in tt], bool),
            "generates_power": np.array([t.generates_power for t in tt], bool),
        }

    def ascii_art(self) -> str:
        """Re-render the grid as a spaced character picture (for reports/specs)."""
        return "\n".join(" ".join(str(k) for k in row) for row in self.grid)

    def cell_strings(self):
        """Group cell tiles into electrical strings.

        Returns ``(strings, string_block)``: ``strings`` maps a string id to the
        row-major-ordered list of flat tile indices in that series string;
        ``string_block`` maps a string id to its parallel-section (``block``) id.
        Tiles sharing a ``string`` are one series string (order is row-major;
        irrelevant to the nominal IV, which is order-independent).
        """
        strings: Dict[str, List[int]] = {}
        string_block: Dict[str, str] = {}
        for idx, key in enumerate(self.flat_keys()):
            t = self.palette[key]
            if not t.is_cell:
                continue
            sid = t.string or t.key
            blk = t.block or "block_default"
            strings.setdefault(sid, []).append(idx)
            if sid in string_block and string_block[sid] != blk:
                raise ValueError(
                    "string %r spans conflicting blocks %r and %r -- a series "
                    "string must belong to exactly one parallel block"
                    % (sid, string_block[sid], blk))
            string_block[sid] = blk
        return strings, string_block


def _parse_layout_rows(rows) -> np.ndarray:
    """Accept rows as space-separated strings, dense strings, or lists of keys."""
    grid: List[List[str]] = []
    for row in rows:
        if isinstance(row, str):
            toks = row.split()
            if len(toks) <= 1 and len(row.strip()) > 1:
                toks = list(row.strip())          # dense form e.g. "AAAA..AA"
            grid.append(toks)
        else:
            grid.append([str(x) for x in row])
    width = max(len(r) for r in grid)
    for r in grid:
        if len(r) != width:
            raise ValueError("layout rows must all be the same length (got %d vs %d)"
                             % (len(r), width))
    return np.array(grid, dtype="<U8")


def from_dict(d: Dict) -> PanelLayout:
    """Build a PanelLayout from a parsed dict (the JSON/YAML schema)."""
    valid = {f.name for f in dataclasses.fields(TileType)} - {"key"}
    palette: Dict[str, TileType] = {}
    for key, spec in d["palette"].items():
        clean = {k: v for k, v in (spec or {}).items() if k in valid}
        palette[key] = TileType(key=key, **clean)
    grid = _parse_layout_rows(d["layout"])
    unknown = set(np.unique(grid)) - set(palette)
    if unknown:
        raise ValueError("layout uses keys not in palette: %s" % sorted(unknown))
    return PanelLayout(grid=grid, palette=palette,
                       pitch_mm=float(d.get("pitch_mm", 40.0)), name=d.get("name", ""),
                       circuit_params=dict(d.get("circuit", {})))


def load_layout(path: str) -> PanelLayout:
    """Load a layout from a JSON file following the convention."""
    with open(path, "r", encoding="utf-8") as f:
        return from_dict(json.load(f))


def panel_from_topology(n_blocks: int, n_parallel: int, n_series: int, *,
                        block_combine: str = "series",
                        arrangement: str = "side-by-side",
                        cell_props: Optional[Dict] = None,
                        pitch_mm: float = 55.0,
                        name: Optional[str] = None) -> PanelLayout:
    """Build a :class:`PanelLayout` from an electrical topology.

    ``n_series`` SCAs in series = a *string*; ``n_parallel`` strings in parallel
    tie at a block's two nodes = a *block*; ``n_blocks`` blocks combined by
    ``block_combine`` (``"series"`` => blocks chained node-to-node, voltages add;
    the parallels of adjacent blocks meet at the shared node).

    Physical ``arrangement`` (independent of the wiring -- it sets thermal
    neighbours):
      * ``"side-by-side"`` (default): rows = the ``n_parallel`` strings, columns =
        series, the ``n_blocks`` placed left-to-right with node bus bars between
        them -> ``n_parallel x (n_blocks*n_series)``.
      * ``"stacked"``: blocks stacked as row-groups -> ``(n_blocks*n_parallel) x n_series``.

    Every tile is tagged ``string='B{b}S{s}'`` and ``block='B{b}'`` so the
    electrical context is recoverable (the series count of a string = the number of
    tiles sharing its key). Returns a layout ready for ``solve_panel``.
    """
    if min(n_blocks, n_parallel, n_series) < 1:
        raise ValueError("n_blocks, n_parallel, n_series must all be >= 1")
    props = dict(alpha_front=0.97, alpha_rear=0.93, epsilon_front=0.90,
                 epsilon_rear=0.89, cell_type="GaAs-3J")
    if cell_props:
        props.update(cell_props)

    palette: Dict[str, TileType] = {}
    grid_rows: List[str] = []

    def add_key(b: int, s: int) -> str:
        k = "B%dS%d" % (b, s)
        if k not in palette:
            palette[k] = TileType(key=k, is_cell=True, string=k, block="B%d" % b, **props)
        return k

    if arrangement == "side-by-side":
        nrows, ncols = n_parallel, n_blocks * n_series
        for r in range(nrows):
            row = [add_key(c // n_series + 1, r + 1) for c in range(ncols)]
            grid_rows.append(" ".join(row))
    elif arrangement == "stacked":
        for r in range(n_blocks * n_parallel):
            k = add_key(r // n_parallel + 1, r % n_parallel + 1)
            grid_rows.append(" ".join([k] * n_series))
    else:
        raise ValueError("arrangement must be 'side-by-side' or 'stacked', got %r" % arrangement)

    nm = name or ("%d blocks (%s) x %d parallel x %d series = %d SCAs"
                  % (n_blocks, block_combine, n_parallel, n_series,
                     n_blocks * n_parallel * n_series))
    return PanelLayout(grid=_parse_layout_rows(grid_rows), palette=palette,
                       pitch_mm=pitch_mm, name=nm)
