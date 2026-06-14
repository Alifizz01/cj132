"""Figure builders -- each is a pure (results, out_path) -> Path.

Every figure here writes to disk and returns the saved path.  None of
them returns a live Figure object; that would not survive being
shipped between processes and would force the report to render before
it could be saved.

All figures use the non-interactive Agg backend.
"""
from __future__ import annotations

import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

# ArrayModel/CaseResult appear only in (lazy, string) type annotations below, so
# we do NOT import the simulation engine at module load -- keeping config-only
# report rendering independent of the (OCR-damaged) legacy cell engine.


# ---------------------------------------------------------------- helpers
def _label(s: str) -> str:
    return s.replace("_", " ").upper()


# ---------------------------------------------------------------- single
def iv_pv_figure(
    array: ArrayModel,
    out_path: Path,
    *,
    bus_voltage_v: float | None = None,
    title: str = "Array I-V / P-V",
    requirement_w: float | None = None,
) -> Path:
    """Twin-axis I-V / P-V for the WHOLE array, MPP marked, bus line."""
    v, i = array.iv_curve()
    p = v * i
    k = int(np.argmax(p))

    fig, ax_i = plt.subplots(figsize=(8.0, 4.6), constrained_layout=True)
    ax_p = ax_i.twinx()

    ax_i.plot(v, i, color="#2b6cb0", lw=2.2,
              marker="o", markevery=max(1, len(v) // 24),
              markersize=4, markerfacecolor="white",
              label="current")
    ax_p.plot(v, p, color="#c53030", lw=2.2, ls="--",
              marker="x", markevery=max(1, len(v) // 24),
              markersize=4, markerfacecolor="black",
              label="power")

    # MPP marker on the power axis
    ax_p.scatter(v[k], p[k], color="black", s=55, zorder=5)
    ax_i.scatter(v[k], i[k], color="black", s=55, zorder=5)
    ax_i.text(
        0.5, 0.06,
        f"MPP : {p[k]:.2f} W @ {v[k]:.3f} V    (I = {i[k]:.3f} A)",
        transform=ax_i.transAxes, ha="center", va="bottom",
        fontsize=9, color="black",
        bbox=dict(boxstyle="round,pad=0.35", facecolor="white",
                  edgecolor="gray", alpha=0.9),
    )

    # bus voltage marker
    if bus_voltage_v is not None:
        i_bus = float(array.current_at_voltage(bus_voltage_v))
        p_bus = bus_voltage_v * i_bus
        ax_i.axvline(bus_voltage_v, color="orange", ls=":", lw=1.4,
                     label=f"V_bus = {bus_voltage_v:.1f} V")
        ax_p.scatter(bus_voltage_v, p_bus, color="orange", s=40,
                     zorder=4)

    if requirement_w is not None:
        ax_p.axhline(requirement_w, color="purple", ls=":", lw=1.2,
                     label=f"requirement = {requirement_w:.0f} W")

    ax_i.set_xlabel("voltage [V]")
    ax_i.set_ylabel("current [A]", color="#2b6cb0")
    ax_p.set_ylabel("power [W]",   color="#c53030")
    ax_i.tick_params(axis="y", labelcolor="#2b6cb0")
    ax_p.tick_params(axis="y", labelcolor="#c53030")
    ax_i.set_title(title)
    ax_i.grid(True, alpha=0.3)

    h1, l1 = ax_i.get_legend_handles_labels()
    h2, l2 = ax_p.get_legend_handles_labels()
    ax_i.legend(h1 + h2, l1 + l2, loc="lower left", fontsize=8)

    fig.savefig(out_path, dpi=170)
    plt.close(fig)
    return out_path


# ---------------------------------------------------------------- per-section grid
def sections_grid_figure(
    array: ArrayModel,
    out_path: Path,
    *,
    bus_voltage_v: float | None = None,
    title: str = "Per-section I-V / P-V",
) -> Path:
    """One small twin-axis I-V/P-V per section, on a grid."""
    sections = list(array.iter_sections())
    n = len(sections)
    if n == 0:
        raise ValueError("sections_grid_figure: array has no sections")
    cols = min(4, n)
    rows = math.ceil(n / cols)

    fig, axes = plt.subplots(rows, cols,
                             figsize=(3.2 * cols, 2.6 * rows),
                             constrained_layout=True,
                             squeeze=False)
    for ax_i, sec in zip(axes.flat, sections):
        v, i = sec.iv_curve()
        p = v * i
        k = int(np.argmax(p))
        ax_p = ax_i.twinx()
        ax_i.plot(v, i, color="#2b6cb0", lw=1.6)
        ax_p.plot(v, p, color="#c53030", lw=1.6, ls="--")
        ax_p.scatter(v[k], p[k], color="black", s=18, zorder=5)
        ax_i.set_title(_label(sec.name), fontsize=8.5)
        if bus_voltage_v is not None:
            ax_i.axvline(bus_voltage_v, color="orange", ls=":", lw=0.8)
        ax_i.tick_params(labelsize=6); ax_p.tick_params(labelsize=6)
        ax_i.grid(True, alpha=0.25)

    # blank the spare cells
    for ax in axes.flat[len(sections):]:
        ax.axis("off")

    fig.suptitle(title, fontsize=11, fontweight="bold")
    fig.savefig(out_path, dpi=170)
    plt.close(fig)
    return out_path


# ---------------------------------------------------------------- regressors
# (title, y-axis label) for each regressor key, matching the reference report
_REGRESSOR_META = {
    "r_voc":  ("Open-Circuit voltage degradation",   r"$V_{oc}$ ratio"),
    "r_vmp":  ("Maximum-power voltage degradation",  r"$V_{mp}$ ratio"),
    "r_isc":  ("Short-Circuit Current degradation",  r"$I_{sc}$ ratio"),
    "r_imp":  ("Maximum-power Current degradation",  r"$I_{mp}$ ratio"),
    "voc_dt": ("Temperature Coefficient",            r"$dV_{oc}/dT$ [mV/K]"),
    "vmp_dt": ("Temperature Coefficient",            r"$dV_{mp}/dT$ [mV/K]"),
    "imp_dt": ("Temperature Coefficient",            r"$dI_{mp}/dT$ [mA/K]"),
    "isc_dt": ("Temperature Coefficient",            r"$dI_{sc}/dT$ [mA/K]"),
}
_REGRESSOR_ORDER = ["r_voc", "r_vmp", "r_isc", "r_imp",
                    "voc_dt", "vmp_dt", "imp_dt", "isc_dt"]


def cell_regressors_figure(regressors: dict, out_path: Path, *,
                           title: str = "Cell radiation regressors") -> Path:
    """Grid of the cell degradation + temperature-coefficient curves vs Dose [%].

    Reproduces the reference report's Figures 1-8 from the cell JSON's
    ``r_*`` / ``*_dt`` ``{dose, value}`` regressor blocks.
    """
    keys = [k for k in _REGRESSOR_ORDER if k in regressors]
    if not keys:
        raise RuntimeError("cell_regressors_figure: cell has no regressor curves")
    n = len(keys)
    cols = 2
    rows = math.ceil(n / cols)
    fig, axes = plt.subplots(rows, cols, figsize=(8.4, 2.3 * rows),
                             constrained_layout=True, squeeze=False)
    for ax, key in zip(axes.flat, keys):
        block = regressors[key]
        dose = np.asarray(block["dose"], float)
        val = np.asarray(block["value"], float)
        ttl, ylab = _REGRESSOR_META.get(key, (key, "value"))
        ax.plot(dose, val, color="#2b6cb0", lw=2.0)
        ax.set_title(ttl, fontsize=9)
        ax.set_xlabel("Dose [%]", fontsize=8)
        ax.set_ylabel(ylab, fontsize=8)
        ax.tick_params(labelsize=7)
        ax.grid(True, alpha=0.3)
    for ax in axes.flat[n:]:
        ax.axis("off")
    fig.suptitle(title, fontsize=11, fontweight="bold")
    fig.savefig(out_path, dpi=170)
    plt.close(fig)
    return out_path


# ---------------------------------------------------------------- cases
def case_compliance_figure(
    cases: list[CaseResult],
    out_path: Path,
    *,
    requirement_w: float | None = None,
    title: str = "Bus power by case",
) -> Path:
    """Bar of power-at-bus per case, with the requirement line."""
    labels = [c.case.label for c in cases]
    values = [c.bus.power_w if c.bus else c.results.array.p_mp
              for c in cases]

    fig, ax = plt.subplots(figsize=(7.5, 3.6), constrained_layout=True)
    bars = ax.bar(labels, values, color="#1f5048", edgecolor="black",
                  alpha=0.85)
    for b, v in zip(bars, values):
        ax.text(b.get_x() + b.get_width() / 2, v,
                f"{v:.1f}", ha="center", va="bottom", fontsize=8)
    if requirement_w is not None:
        ax.axhline(requirement_w, color="orange", ls="--", lw=1.4,
                   label=f"requirement = {requirement_w:.0f} W")
        ax.legend(loc="lower right", fontsize=8)
    ax.set_ylabel("power at V_bus  [W]")
    ax.set_title(title)
    plt.setp(ax.get_xticklabels(), rotation=20, ha="right",
             fontsize=8)
    ax.grid(True, axis="y", alpha=0.3)
    fig.savefig(out_path, dpi=170)
    plt.close(fig)
    return out_path
