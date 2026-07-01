"""Panel-layout visualisation -- draw a PanelLayout as a physical map.

Shows where each SCA sits, which series-string / block it belongs to (by
colour), where there is **no cell** (empty / bare-substrate tiles), diode
tiles, and the harness bus-bars that tie the parallel strings together at the
node between series blocks.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch, Rectangle


def panel_schematic_figure(sections, out_path: Path, *,
                           title: str = "Panel layout (one panel)",
                           sec_width: float = 3.0) -> Path:
    """Schematic of one panel's sections (blocks).

    Each section is drawn as a block whose height = its number of parallel
    strings; sections are top-aligned and placed side-by-side, so a section
    with fewer strings leaves a hatched **no-SCA** gap below it.  A heavy line
    between adjacent sections marks the harness / node bus-bar.  The real
    series count is shown in the label rather than the width (54 cells would
    be illegible).
    """
    secs = list(sections)
    if not secs:
        raise ValueError("panel_schematic_figure: no sections")
    h_max = max(s.n_strings_parallel for s in secs)

    fig, ax = plt.subplots(figsize=(min(16, 1.4 * len(secs) + 3.0),
                                    0.7 * h_max + 2.0),
                           constrained_layout=True)
    colors = ["#4C72B0", "#DD8452", "#55A868", "#C44E52", "#8172B3",
              "#937860", "#DA8BC3", "#CCB974"]

    x = 0.0
    for i, s in enumerate(secs):
        h = s.n_strings_parallel
        # cells present (top-aligned)
        ax.add_patch(Rectangle((x, h_max - h), sec_width, h,
                               facecolor=colors[i % len(colors)],
                               edgecolor="#222222", lw=1.0))
        ax.text(x + sec_width / 2, h_max - h / 2,
                f"{s.section_id}\n{s.n_strings_parallel} parallel\n"
                f"x {s.n_sca_series_per_string} series",
                ha="center", va="center", fontsize=8.5, color="white")
        # no-SCA gap below a shorter section
        if h < h_max:
            ax.add_patch(Rectangle((x, 0), sec_width, h_max - h,
                                   facecolor="white", edgecolor="#BBBBBB",
                                   lw=0.8, hatch="////"))
        # harness bus-bar between this section and the next
        if i < len(secs) - 1:
            ax.plot([x + sec_width, x + sec_width], [0, h_max],
                    color="#B00000", lw=2.6, zorder=5)
        x += sec_width

    ax.set_xlim(-0.4, x + 0.4)
    ax.set_ylim(-0.4, h_max + 0.6)
    ax.set_aspect("equal")
    ax.set_xticks([]); ax.set_yticks([])
    for sp in ax.spines.values():
        sp.set_visible(False)
    ax.set_ylabel("parallel strings")
    ax.set_title(title, fontsize=11)

    handles = [
        Patch(facecolor="#9aa7c4", edgecolor="#222222", label="SCA (cells)"),
        Patch(facecolor="white", edgecolor="#BBBBBB", hatch="////",
              label="no SCA (empty)"),
        plt.Line2D([0], [0], color="#B00000", lw=2.6,
                   label="harness / node bus-bar"),
    ]
    ax.legend(handles=handles, loc="upper center",
              bbox_to_anchor=(0.5, -0.02), ncol=3, fontsize=8, frameon=False)

    fig.savefig(out_path, dpi=170, bbox_inches="tight")
    plt.close(fig)
    return out_path

# a calm categorical palette for blocks
_BLOCK_COLORS = [
    "#4C72B0", "#DD8452", "#55A868", "#C44E52", "#8172B3",
    "#937860", "#DA8BC3", "#8C8C8C", "#CCB974", "#64B5CD",
]
_BARE_FACE = "#FFFFFF"
_BARE_EDGE = "#BBBBBB"
_DIODE_FACE = "#3A3A3A"


def layout_map_figure(layout, out_path: Path, *,
                      title: str | None = None,
                      label_tiles: bool = True,
                      show_harness: bool = True) -> Path:
    """Render ``layout`` (a :class:`PanelLayout`) to a labelled panel map."""
    nrows, ncols = layout.n_rows, layout.n_cols

    # assign a stable colour per block id (cells only)
    blocks = []
    for r in range(nrows):
        for c in range(ncols):
            b = layout.tile_at(r, c).block
            if b is not None and b not in blocks:
                blocks.append(b)
    block_color = {b: _BLOCK_COLORS[i % len(_BLOCK_COLORS)]
                   for i, b in enumerate(blocks)}

    fig_w = min(16, 0.55 * ncols + 2.5)
    fig_h = min(20, 0.55 * nrows + 2.0)
    fig, ax = plt.subplots(figsize=(fig_w, fig_h), constrained_layout=True)

    has_bare = has_diode = False
    for r in range(nrows):
        for c in range(ncols):
            t = layout.tile_at(r, c)
            x, y = c, nrows - 1 - r           # row 0 at the top
            if t.is_diode:
                face, edge, has_diode = _DIODE_FACE, "#222222", True
            elif t.is_cell:
                face, edge = block_color.get(t.block, "#4C72B0"), "#2A2A2A"
            else:
                face, edge, has_bare = _BARE_FACE, _BARE_EDGE, True
            hatch = None if (t.is_cell or t.is_diode) else "////"
            ax.add_patch(Rectangle((x, y), 1, 1, facecolor=face,
                                   edgecolor=edge, linewidth=0.6, hatch=hatch))
            if label_tiles and t.is_cell and t.string:
                ax.text(x + 0.5, y + 0.5, t.string, ha="center", va="center",
                        fontsize=6.5, color="white")
            elif t.is_diode:
                ax.text(x + 0.5, y + 0.5, "D", ha="center", va="center",
                        fontsize=8, color="white", fontweight="bold")

    # harness bus-bars: a heavy line at the column boundary where the block id
    # changes -- this is the node where the parallel strings tie together and
    # the inter-block harness runs.
    if show_harness:
        for r in range(nrows):
            for c in range(ncols - 1):
                b0 = layout.tile_at(r, c).block
                b1 = layout.tile_at(r, c + 1).block
                if b0 is not None and b1 is not None and b0 != b1:
                    x = c + 1
                    y = nrows - 1 - r
                    ax.plot([x, x], [y, y + 1], color="#B00000", lw=2.4,
                            solid_capstyle="butt", zorder=5)

    ax.set_xlim(-0.3, ncols + 0.3)
    ax.set_ylim(-0.3, nrows + 0.3)
    ax.set_aspect("equal")
    ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_title(title or layout.name or "Panel layout", fontsize=11)

    # legend
    handles = [Patch(facecolor=block_color[b], edgecolor="#2A2A2A", label=b)
               for b in blocks]
    if not blocks:   # grid with un-blocked cells (e.g. a cell/bare thermal map)
        handles.append(Patch(facecolor="#4C72B0", edgecolor="#2A2A2A",
                             label="SCA (cell)"))
    if has_bare:
        handles.append(Patch(facecolor=_BARE_FACE, edgecolor=_BARE_EDGE,
                             hatch="////", label="no cell (bare)"))
    if has_diode:
        handles.append(Patch(facecolor=_DIODE_FACE, edgecolor="#222222",
                             label="diode"))
    if show_harness and len(blocks) > 1:
        handles.append(plt.Line2D([0], [0], color="#B00000", lw=2.4,
                                  label="inter-block harness / node"))
    ax.legend(handles=handles, loc="center left", bbox_to_anchor=(1.01, 0.5),
              fontsize=8, frameon=False, title="legend")

    fig.savefig(out_path, dpi=170, bbox_inches="tight")
    plt.close(fig)
    return out_path
