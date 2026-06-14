"""Figure builders for the Monte-Carlo report."""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def peak_temp_hist_figure(peaks, out_path: Path, *, t_limit_c: float,
                          mean_c: float | None = None,
                          title: str = "Peak-temperature distribution") -> Path:
    """Histogram of per-run peak temperatures, with the limit + mean marked."""
    p = np.asarray(peaks, dtype=float)
    fig, ax = plt.subplots(figsize=(7.6, 4.2), constrained_layout=True)
    ax.hist(p, bins=min(40, max(8, p.size // 8)), color="#4C72B0",
            edgecolor="white", alpha=0.9)
    if mean_c is not None:
        ax.axvline(mean_c, color="black", ls="-", lw=1.6,
                   label=f"mean = {mean_c:.1f} °C")
    ax.axvline(t_limit_c, color="#B00000", ls="--", lw=1.8,
               label=f"limit = {t_limit_c:.0f} °C")
    ax.set_xlabel("peak panel temperature [°C]")
    ax.set_ylabel("number of Monte-Carlo runs")
    ax.set_title(title)
    ax.grid(True, axis="y", alpha=0.3)
    ax.legend(fontsize=8)
    fig.savefig(out_path, dpi=170)
    plt.close(fig)
    return out_path
