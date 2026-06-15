# -*- coding: utf-8 -*-
"""Generate authentic figures for PowerPy_Framework_Explained, using the REAL
powerpy solvers (single-diode IV, 2-node thermal, lateral conduction, transient,
bypass-diode spacing). Run from anywhere; writes PNGs next to this file.

    PYTHONPATH=../src python _build_framework_figs.py
"""
import os
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from powerpy.simulation.cell_level import fit_rseries, single_diode_iv, DiodeParams
from powerpy.solve.thermal import solve_thermal, SIGMA, T_ZERO_C, T_SPACE
from powerpy.solve.transient import solve_transient
from powerpy.model.diode import BypassDiode, spacing_scan

INK = "#16324f"
ACCENT = "#c05621"
GRID = "#d9dde2"

plt.rcParams.update({
    "font.size": 12,
    "axes.edgecolor": "#888",
    "axes.linewidth": 0.9,
    "axes.grid": True,
    "grid.color": GRID,
    "grid.linewidth": 0.8,
    "figure.dpi": 200,
})


# 3G30LARS_GEO begin-of-life datasheet points
ISC, IMP, VMP, VOC = 1.2311, 1.18425, 2.375, 2.679


def fig_iv():
    p = fit_rseries(ISC, IMP, VMP, VOC)
    V, I = single_diode_iv(p, step=0.005)
    P = V * I
    mp = int(np.argmax(P))

    fig, ax1 = plt.subplots(figsize=(8.2, 4.6))
    ax1.plot(V, I, color=INK, lw=2.4, label="current  I(V)")
    ax1.scatter([0], [I[0]], color=INK, zorder=5)
    ax1.annotate("Isc = %.3f A" % I[0], (0, I[0]), textcoords="offset points",
                 xytext=(10, -4), color=INK)
    ax1.scatter([V[-1]], [0], color=INK, zorder=5)
    ax1.annotate("Voc = %.3f V" % V[-1], (V[-1], 0), textcoords="offset points",
                 xytext=(-92, 12), color=INK)
    ax1.scatter([V[mp]], [I[mp]], color=ACCENT, zorder=6)
    ax1.annotate("MPP\n(Vmp=%.2f V, Imp=%.2f A)" % (V[mp], I[mp]),
                 (V[mp], I[mp]), textcoords="offset points", xytext=(-150, -40),
                 color=ACCENT)
    ax1.set_xlabel("Voltage  V  [V]")
    ax1.set_ylabel("Current  I  [A]", color=INK)
    ax1.set_ylim(0, I[0] * 1.18)
    ax1.set_xlim(0, V[-1] * 1.02)

    ax2 = ax1.twinx()
    ax2.plot(V, P, color=ACCENT, lw=1.8, ls="--", label="power  P = V·I")
    ax2.scatter([V[mp]], [P[mp]], color=ACCENT, zorder=6)
    ax2.annotate("Pmax = %.3f W" % P[mp], (V[mp], P[mp]),
                 textcoords="offset points", xytext=(8, 6), color=ACCENT)
    ax2.set_ylabel("Power  P  [W]", color=ACCENT)
    ax2.set_ylim(0, P[mp] * 1.25)
    ax2.grid(False)
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, "fig_fw_iv.png"))
    plt.close(fig)
    print("fig_fw_iv.png  Isc=%.3f Voc=%.3f Pmax=%.3f" % (I[0], V[-1], P[mp]))


def fig_newton():
    """Thermal 2x2 Newton residual collapsing from a cold start (single cell).

    Mirrors solve_thermal's non-lateral branch for ONE cell so we can record the
    energy-balance residual |f1|+|f2| at every iteration and plot it.
    """
    A = 0.04 ** 2
    aF, aR, eF, eR = 0.91, 0.14, 0.83, 0.83
    c_cond, p_sun = 1000.0, 1361.0
    Pe = 1.1
    CA = c_cond * A
    qF = aF * A * p_sun
    qR = 0.0
    tsp4 = T_SPACE ** 4
    # deliberately cold start (−120 °C) so several Newton steps are visible
    T1 = T2 = -120.0 - T_ZERO_C
    res = []
    for _ in range(14):
        f1 = qF - eF * A * SIGMA * (T1 ** 4 - tsp4) - Pe + CA * (T2 - T1)
        f2 = qR - eR * A * SIGMA * (T2 ** 4 - tsp4) - CA * (T2 - T1)
        res.append(abs(f1) + abs(f2))
        a = -4.0 * eF * A * SIGMA * T1 ** 3 - CA
        b = CA; cc = CA
        d = -4.0 * eR * A * SIGMA * T2 ** 3 - CA
        det = a * d - b * cc
        dT1 = -(d * f1 - b * f2) / det
        dT2 = -(-cc * f1 + a * f2) / det
        T1 += dT1; T2 += dT2
        if abs(dT1) < 1e-9 and abs(dT2) < 1e-9:
            f1 = qF - eF * A * SIGMA * (T1 ** 4 - tsp4) - Pe + CA * (T2 - T1)
            f2 = qR - eR * A * SIGMA * (T2 ** 4 - tsp4) - CA * (T2 - T1)
            res.append(abs(f1) + abs(f2))
            break
    res = [max(r, 1e-18) for r in res]
    fig, ax = plt.subplots(figsize=(7.4, 4.0))
    ax.semilogy(range(1, len(res) + 1), res, "o-", color=INK, lw=2)
    ax.set_xlabel("Newton iteration")
    ax.set_ylabel("energy-balance residual |f₁|+|f₂|  [W]  (log)")
    ax.set_title("2-node thermal solve: Newton from a cold start (T₀ = −120 °C)\n"
                 "converged front T = %.2f °C" % (T1 + T_ZERO_C), color=INK)
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, "fig_fw_newton.png"))
    plt.close(fig)
    print("fig_fw_newton.png  iters=%d  final=%.1e  T=%.2f" %
          (len(res), res[-1], T1 + T_ZERO_C))


def _grid_neighbours(nr, nc):
    def idx(r, c):
        return r * nc + c
    pairs = []
    for r in range(nr):
        for c in range(nc):
            if c + 1 < nc:
                pairs.append((idx(r, c), idx(r, c + 1)))
            if r + 1 < nr:
                pairs.append((idx(r, c), idx(r + 1, c)))
    return pairs


def fig_lateral():
    """One failed (reverse-biased) cell on a 9x9 panel: no spreading vs spreading."""
    nr = nc = 9
    n = nr * nc
    pitch = 0.04
    A = np.full(n, pitch ** 2)
    Pe = np.full(n, 1.1)               # healthy cells extract ~1.1 W
    fail = (nr // 2) * nc + nc // 2     # centre cell
    Pe[fail] = -9.6                      # reverse-biased: dissipates heat
    nb = _grid_neighbours(nr, nc)

    common = dict(area=A, alpha_front=0.91, alpha_rear=0.14,
                  epsilon_front=0.83, epsilon_rear=0.83, c_cond=1000.0,
                  p_sun=1361.0, p_albedo=0.0, p_ir=0.0, p_elec=Pe)

    r0 = solve_thermal(neighbours=nb, g_lat=0.0, **common)
    r1 = solve_thermal(neighbours=nb, g_lat=0.06, **common)
    g0 = r0.t_front_c.reshape(nr, nc)
    g1 = r1.t_front_c.reshape(nr, nc)

    vmin = min(g0.min(), g1.min())
    vmax = max(g0.max(), g1.max())
    fig, axes = plt.subplots(1, 2, figsize=(9.6, 4.4))
    for ax, g, ttl in ((axes[0], g0, "g_lat = 0  (isolated cells)"),
                       (axes[1], g1, "g_lat = 0.06 W/K  (lateral conduction)")):
        im = ax.imshow(g, cmap="inferno", vmin=vmin, vmax=vmax)
        ax.set_title(ttl, color=INK, fontsize=12)
        ax.set_xticks([]); ax.set_yticks([]); ax.grid(False)
        ax.text(nc // 2, nr // 2, "%.0f°C" % g[nr // 2, nc // 2],
                ha="center", va="center", color="white", fontsize=9, weight="bold")
    cb = fig.colorbar(im, ax=axes, fraction=0.046, pad=0.04)
    cb.set_label("front temperature  [°C]")
    fig.suptitle("Heat spreading drops the peak but warms the neighbours",
                 color=INK, fontsize=13)
    fig.savefig(os.path.join(HERE, "fig_fw_lateral.png"), bbox_inches="tight")
    plt.close(fig)
    print("fig_fw_lateral.png  peak g0=%.1f  peak g1=%.1f" % (g0.max(), g1.max()))


class _FP:
    __slots__ = ("time_s", "p_sun", "p_albedo", "p_ir", "tilt")

    def __init__(self, t, ps, pa, pir, tilt):
        self.time_s, self.p_sun, self.p_albedo, self.p_ir, self.tilt = t, ps, pa, pir, tilt


def fig_transient():
    """A single cell fails at t=0; watch its front temperature climb to steady."""
    dt = 5.0
    nt = 240
    series = [_FP(k * dt, 1361.0, 0.0, 0.0, 1.0) for k in range(nt)]
    # heat capacity ~ aluminium-backed cell
    A = np.array([0.04 ** 2])
    C = 2700.0 * 900.0 * 0.0008 * A          # rho*cp*thick*area
    # power: healthy for first 20 steps, then reverse-biased (failure)
    pe = np.full((nt, 1), 1.1)
    pe[20:, 0] = -9.6
    res = solve_transient(
        area=A, alpha_front=0.91, alpha_rear=0.14, epsilon_front=0.83,
        epsilon_rear=0.83, c_cond=1000.0, heat_capacity=C,
        flux_series=series, p_elec_series=pe, t_init_c=60.0)
    t = res.times / 60.0
    Tf = res.t_front_c[:, 0]
    fig, ax = plt.subplots(figsize=(7.8, 4.2))
    ax.plot(t, Tf, color=ACCENT, lw=2.2)
    ax.axvline(20 * dt / 60.0, color=INK, ls=":", lw=1.3)
    ax.annotate("cell fails\n(goes reverse-biased)", (20 * dt / 60.0, Tf.min() + 6),
                textcoords="offset points", xytext=(14, 0), color=INK)
    ax.set_xlabel("time  [min]")
    ax.set_ylabel("front temperature  [°C]")
    ax.set_title("Transient: hot-spot climbs after a failure (implicit Euler)",
                 color=INK)
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, "fig_fw_transient.png"))
    plt.close(fig)
    print("fig_fw_transient.png  start=%.1f end=%.1f" % (Tf[0], Tf[-1]))


def fig_diode():
    diode = BypassDiode(v_forward=0.7)
    rows = spacing_scan(i=1.18, v_cell=2.4, n_series=22, diode=diode,
                        cells_per_diode_options=[2, 4, 6, 8, 11])
    labels = ["none" if r["cells_per_diode"] is None else str(r["cells_per_diode"])
              for r in rows]
    pw = [r["p_reverse_w"] for r in rows]
    fig, ax = plt.subplots(figsize=(7.8, 4.2))
    bars = ax.bar(labels, pw, color=[INK if l != "none" else ACCENT for l in labels])
    ax.set_xlabel("cells protected per bypass diode")
    ax.set_ylabel("reverse power in failed cell  [W]")
    ax.set_title("Tighter diode spacing → cooler hot-spot", color=INK)
    for b, v in zip(bars, pw):
        ax.text(b.get_x() + b.get_width() / 2, v + 0.6, "%.1f" % v,
                ha="center", color=INK, fontsize=10)
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, "fig_fw_diode.png"))
    plt.close(fig)
    print("fig_fw_diode.png  unprotected=%.1f W" % pw[0])


if __name__ == "__main__":
    fig_iv()
    fig_newton()
    fig_lateral()
    fig_transient()
    fig_diode()
    print("done.")
