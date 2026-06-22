"""Example: Monte-Carlo thermal-failure study + report (plus two extras).

Run from the project root:

    python examples/run_montecarlo.py

What it does
------------
1. Loads the workbook + cell/substrate JSONs into a ReportMetadata.
2. Builds a panel from the cell optics and runs:
     - auto_monte_carlo : random cell failures, sampled until the standard
       error of the mean peak temperature is tight enough (stops itself);
     - worst_case_search: a greedy hunt for the most damaging failure cluster.
3. Prints the headline numbers, then renders an AIRBUS-style PDF.
4. demo_iv_engine : the cell I-V via the analytic vs vendored-ngspice engine.
5. demo_orbit     : the vendored orbit toolkit + an orbit-driven transient run.

Everything below is the public API -- copy it into your own scripts.
"""
import sys
from pathlib import Path

# make 'powerpy' importable without installation (vendored / no-pip setup)
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from powerpy.loader.report import load_report_data
from powerpy.schemas._common import Phase
from powerpy.schemas.fluxes import LaunchConfig

# --- low-level API: run the study yourself ---------------------------------
from powerpy.analysis.montecarlo_report import run_mc_study

# --- high-level API: study + PDF in one go ---------------------------------
from powerpy.render.montecarlo_report import MonteCarloReport


def demo_iv_engine(md) -> None:
    """Cell I-V via the two engines.

    ``iv_engine="analytic"`` (default) is the self-contained single-diode model.
    ``iv_engine="ngspice"`` uses the vendored ngspice/PySpice path on a machine
    that has it (psp/ + Spice64_dll); where it is absent it warns once and
    transparently falls back to analytic -- so the same code runs everywhere.
    """
    from powerpy.simulation.cell_level import CellModel
    from powerpy.simulation.environment import Environment
    env = Environment(temperature_c=51.1, dose_i=246.0, dose_v=511.0,
                      current_loss=0.94, voltage_loss=0.97)
    print("iv_engine demo (EOL operating point):")
    for engine in ("analytic", "ngspice"):
        cell = CellModel(md.cell, iv_engine=engine)
        cell.apply(env)
        v, i = cell.iv_curve()
        print(f"  {engine:8s}: Voc={v[-1]:.3f} V  Isc={i[0]:.3f} A  "
              f"MPP={(v * i).max():.2f} W")


def demo_orbit() -> None:
    """Vendored orbit toolkit (pure numpy) + an orbit-driven transient run."""
    from powerpy.model.orbit import summarize_orbit, orbit_flux_timeline
    from powerpy.solve.transient import (solve_transient, areal_heat_capacity,
                                         time_to_threshold)
    s = summarize_orbit(altitude_km=500, inclination_deg=51.6,
                        raan_deg=0, day_of_year=172)
    print("orbit demo (500 km LEO, summer solstice):")
    print(f"  period {s.period_min:.1f} min, beta {s.beta_deg:.1f} deg, "
          f"eclipse {100 * s.eclipse_fraction:.0f}% ({s.eclipse_min:.1f} min)")

    flux = orbit_flux_timeline(500, 51.6, 0, day_of_year=172, n_steps=240)
    # include the backing's thermal mass (a bare cell alone is too light)
    C = areal_heat_capacity(area=0.007075, rho=2700, cp=900, thickness=0.002)
    tr = solve_transient(area=0.007075, alpha_front=0.91, alpha_rear=0.48,
                         epsilon_front=0.83, epsilon_rear=0.76, c_cond=800.0,
                         heat_capacity=C, flux_series=flux, p_elec_series=2.2)
    t_lim = time_to_threshold(tr, limit_c=120.0, cell=0)
    print(f"  transient: Tmax {tr.t_front_c.max():.1f} C, "
          f"Tmin {tr.t_front_c.min():.1f} C, "
          f"reach 120 C: {('%.0f s' % t_lim) if t_lim else 'never (safe)'}")


def main() -> None:
    md = load_report_data(ROOT / "src" / "powerpy" / "param" / "params.xlsx", ROOT / "src" / "powerpy" / "data")

    # The panel layout is an INPUT. Two forms are accepted:
    #   panel_layout_file = a fully-tagged layout (palette + grid, load_layout
    #       format) -- every tile carries its block/string AND its position, so
    #       it describes the circuit and the placement together.
    #   layout_file       = a simple 'C' (cell) / '.' (bare) grid; cell optics
    #       come from the cell JSON. Bare tiles never fail.
    # Here we use the tagged 3-block demo layout.
    LAYOUT = str(ROOT / "src" / "powerpy" / "data" / "layouts" / "simple_3block.json")

    # ---- option A: just the numbers --------------------------------------
    data = run_mc_study(
        md,
        panel_layout_file=LAYOUT,   # tagged layout (blocks/strings + placement)
        phase=Phase.END_OF_LIFE, launch_config=LaunchConfig.DUAL, season=0.967,
        t_limit_c=150.0,            # cell temperature limit
        p_fail=0.08,                # each cell fails with 8% probability
        target_se=2.0,              # auto-stop when SE(mean peak) <= 2.0 degC
        max_runs=150,               # safety cap
        max_failures=4,             # worst-case search depth
        workers=4,                  # thread pool for the panel solves
    )
    s = data.summary
    print(f"runs={s['n_runs']} ({s['stopped']})  "
          f"mean peak={s['mean_peak_c']} degC  SE={s['standard_error']}  "
          f"max peak={s['max_peak_c']} degC")
    print(f"P(any cell over {data.t_limit_c:.0f} degC) = {data.p_over_limit*100:.1f}%")
    print(f"worst-case cluster: {data.worst['failed']}  "
          f"-> {data.worst['peak_t_c']} degC")

    # ---- option B: same study, rendered to a PDF -------------------------
    pdf = (MonteCarloReport
           .from_metadata(md, panel_layout_file=LAYOUT, phase=Phase.END_OF_LIFE,
                          launch_config=LaunchConfig.DUAL, season=0.967,
                          t_limit_c=150.0, p_fail=0.08, target_se=2.0,
                          max_runs=150, max_failures=4, workers=4)
           .render(ROOT / "build_montecarlo")
           .compile_pdf(ROOT / "reports" / "MonteCarlo_Report.pdf"))
    print("PDF:", pdf)

    # ---- extras ----------------------------------------------------------
    print()
    demo_iv_engine(md)
    print()
    demo_orbit()


if __name__ == "__main__":
    main()
