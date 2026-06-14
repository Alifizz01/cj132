"""Figure builders for the thermal report -- each (data, out_path) -> Path."""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def panel_heatmap_figure(grid_c: np.ndarray, out_path: Path, *,
                         title: str = "Panel temperature map",
                         annotate_max: int = 144) -> Path:
    """Render a per-cell temperature grid as a heat-map with a colour bar."""
    grid = np.asarray(grid_c, dtype=float)
    nrows, ncols = grid.shape

    # A (near-)uniform grid would make imshow's autoscale amplify
    # floating-point noise into spurious extreme colours; pad the range.
    vmin, vmax = float(grid.min()), float(grid.max())
    if vmax - vmin < 1.0:
        mid = 0.5 * (vmin + vmax)
        vmin, vmax = mid - 0.5, mid + 0.5

    fig, ax = plt.subplots(figsize=(0.5 * ncols + 2.0, 0.5 * nrows + 1.5),
                           constrained_layout=True)
    im = ax.imshow(grid, cmap="inferno", aspect="equal", vmin=vmin, vmax=vmax)
    cbar = fig.colorbar(im, ax=ax, shrink=0.85)
    cbar.set_label("temperature [°C]")

    # annotate cells when the grid is small enough to stay readable
    if grid.size <= annotate_max:
        vmid = 0.5 * (grid.min() + grid.max())
        for r in range(nrows):
            for c in range(ncols):
                ax.text(c, r, f"{grid[r, c]:.0f}", ha="center", va="center",
                        fontsize=7,
                        color="white" if grid[r, c] < vmid else "black")

    ax.set_xticks(range(ncols)); ax.set_yticks(range(nrows))
    ax.set_xticklabels([f"{c+1}" for c in range(ncols)], fontsize=7)
    ax.set_yticklabels([f"{r+1}" for r in range(nrows)], fontsize=7)
    ax.set_xlabel("column"); ax.set_ylabel("row")
    ax.set_title(title)
    fig.savefig(out_path, dpi=170)
    plt.close(fig)
    return out_path
