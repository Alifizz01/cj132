# -*- coding: utf-8 -*-
"""Command-line interface for the panel thermal framework.

    powerpy run   LAYOUT.json [--fail I ...] [--g-lat W/K] [--report out.html]
    powerpy worst LAYOUT.json --max-failures K   [--report out.html]
    powerpy sweep LAYOUT.json [--p-fail P] [--target-se C] [--max-runs N]

One command to: load a grid+palette layout, solve it (optionally with lateral
conduction and injected failures), and write the HTML heat-map + JSON report --
or hunt the worst-case failure cluster, or run an auto-stopping Monte-Carlo.

Pure stdlib ``argparse`` (no extra deps). Installed as the ``powerpy`` console
script (see pyproject) and runnable as ``python -m powerpy``.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config.layout import load_layout
from .config.substrate import load_substrate
from .solve.thermal import solve_panel
from .reporting.report import panel_report
from .analysis.study import (make_pe, worst_case_search, auto_monte_carlo, cell_indices)


def _add_common(p):
    p.add_argument("layout", help="path to a layout JSON (grid + palette)")
    p.add_argument("--substrate", default="msro_case2", help="substrate name for c_cond (default: msro_case2)")
    p.add_argument("--area", type=float, default=None, help="tile area m^2 (default: from layout pitch)")
    p.add_argument("--p-sun", type=float, default=1367.0, dest="p_sun", help="solar flux W/m^2")
    p.add_argument("--albedo", type=float, default=0.0, dest="p_albedo", help="albedo flux W/m^2")
    p.add_argument("--ir", type=float, default=0.0, dest="p_ir", help="planetary IR flux W/m^2")
    p.add_argument("--g-lat", type=float, default=0.0, dest="g_lat", help="lateral conductance W/K (0 = independent)")
    p.add_argument("--t-limit", type=float, default=150.0, dest="t_limit", help="melt limit degC")
    p.add_argument("--healthy-w", type=float, default=1.1, dest="healthy_w", help="healthy cell extracted power W")
    p.add_argument("--reverse-w", type=float, default=-9.6, dest="reverse_w", help="failed cell dissipated power W")
    p.add_argument("--workers", type=int, default=1, help="thread workers for sweeps")


def _solve_kwargs(args):
    c_cond = load_substrate(args.substrate).c_cond
    return dict(p_sun=args.p_sun, p_albedo=args.p_albedo, p_ir=args.p_ir,
                c_cond=c_cond, g_lat=args.g_lat, area=args.area)


def _cmd_run(args) -> int:
    layout = load_layout(args.layout)
    failed = [int(i) for i in (args.fail or [])]
    pe = make_pe(layout, failed, healthy_w=args.healthy_w, reverse_w=args.reverse_w)
    res = solve_panel(layout, p_elec=pe, **_solve_kwargs(args))
    peak = float(res.t_front_c.max())
    verdict = "FAIL" if peak >= args.t_limit else "PASS"
    print("layout %s : %dx%d, %d cells, %d failed"
          % (layout.name or args.layout, layout.n_rows, layout.n_cols,
             len(cell_indices(layout)), len(failed)))
    print("peak %.1f degC  (limit %.1f)  ->  %s   [g_lat=%.4g, converged=%s]"
          % (peak, args.t_limit, verdict, args.g_lat, res.converged))
    if args.report or args.json:
        panel_report(layout, res, t_limit_c=args.t_limit,
                     out_html=args.report or (args.json + ".html"), out_json=args.json)
        if args.report:
            print("wrote %s" % args.report)
        if args.json:
            print("wrote %s" % args.json)
    return 0


def _cmd_worst(args) -> int:
    layout = load_layout(args.layout)
    out = worst_case_search(layout, max_failures=args.max_failures, t_limit_c=args.t_limit,
                            solve_kwargs=_solve_kwargs(args), healthy_w=args.healthy_w,
                            reverse_w=args.reverse_w, workers=args.workers)
    print("worst-case %d failures -> peak %.1f degC at cells %s"
          % (len(out["failed"]), out["peak_t_c"], out["failed"]))
    for t in out["trajectory"]:
        print("  step %d: + cell %d -> peak %.1f degC (%d over limit)"
              % (t["step"], t["added"], t["peak_t_c"], t["n_over_limit"]))
    if args.report or args.json:
        pe = make_pe(layout, out["failed"], healthy_w=args.healthy_w, reverse_w=args.reverse_w)
        res = solve_panel(layout, p_elec=pe, **_solve_kwargs(args))
        panel_report(layout, res, t_limit_c=args.t_limit,
                     out_html=args.report or (args.json + ".html"), out_json=args.json)
        if args.report:
            print("wrote %s" % args.report)
    return 0


# ---------------------------------------------------------------- electrical report
# Phases are ordered begin-of-life -> end-of-life for a readable report; any phase
# the workbook defines but isn't listed here is appended afterwards (alphabetical).
_PHASE_ORDER = ["BOL_ATC", "BOL_BC", "End_of_LEOP", "End_of_ORP", "End_of_Life"]


def _repo_root() -> Path:
    """The project root (this file is at <root>/src/powerpy/app.py)."""
    return Path(__file__).resolve().parents[2]


def _find_params(explicit: str | None = None) -> Path:
    """Locate params.xlsx: an explicit path wins; else CWD, examples/, repo root."""
    if explicit:
        p = Path(explicit).expanduser().resolve()
        if not p.is_file():
            raise SystemExit("ERROR: params file not found: %s" % p)
        return p
    root = _repo_root()
    for cand in (Path.cwd() / "params.xlsx",
                 root / "examples" / "params.xlsx",
                 root / "params.xlsx"):
        if cand.is_file():
            return cand
    raise SystemExit("ERROR: could not find params.xlsx (looked in the current "
                     "directory, examples/ and the repo root). Pass its path: "
                     "powerpy report <params.xlsx>")


def build_electrical_report(params, out_pdf, *, data_dir=None,
                            engine: str = "analytic", workdir=None):
    """Build the whole-array electrical report PDF from a params workbook.

    Uses the analytic single-diode engine by default (``engine="analytic"``) so it
    needs neither ngspice nor a legacy cell file. Returns
    ``(pdf_path_or_None, phases, report_metadata)``. ``pdf_path`` is None only if
    pdflatex is unavailable (the LaTeX workspace is still written).
    """
    # heavy imports are local so `powerpy run/worst/sweep` don't pay for them
    import dataclasses
    from .loader.report import load_report_data
    from .loader.analysis import load_analysis_scope
    from .simulation.pipeline import (
        AnalysisCase, CaseResult, CompliancePoint, environment_for_phase, run, evaluate)
    from .simulation.array_level import build_from_report
    from .render import Report

    params = Path(params)
    data_dir = Path(data_dir) if data_dir else Path(__file__).parent / "data"
    out_pdf = Path(out_pdf).resolve()
    workdir = Path(workdir) if workdir else out_pdf.parent / ("_build_" + out_pdf.stem)

    report = load_report_data(params, data_dir)
    scope = load_analysis_scope(params)

    if scope:
        # SCOPE-DRIVEN: investigate exactly the configs the `analysis` sheet lists,
        # in its order, each at its own operating conditions.
        array = build_from_report(report, iv_engine=engine)
        case_results = []
        for cfg in scope:
            env = environment_for_phase(
                report, phase=cfg.phase, launch_config=cfg.launch,
                temperature_c=cfg.temperature_c, season=cfg.season,
                angle_alpha_deg=cfg.sun_angle_deg)
            if cfg.string_loss != 1.0:        # extra string-level current loss
                env = dataclasses.replace(
                    env, current_loss=env.current_loss * cfg.string_loss)
            res = run(array, env)
            bus = None
            if cfg.v_operating is not None:
                i_bus = array.current_at_voltage(cfg.v_operating)
                bus = CompliancePoint(bus_voltage_v=cfg.v_operating,
                                      current_a=float(i_bus),
                                      power_w=float(cfg.v_operating * i_bus))
            case = AnalysisCase(label=cfg.label, phase=cfg.phase,
                                launch_config=cfg.launch,
                                temperature_c=cfg.temperature_c, season=cfg.season)
            case_results.append(CaseResult(case=case, environment=env,
                                          results=res, bus=bus))
        labels = [c.label for c in scope]
        rpt = Report.from_results(report, case_results, array=array, iv_engine=engine)
        rpt.render(workdir)
        return rpt.compile_pdf(out_pdf), labels, report

    # FALLBACK (no analysis sheet): one case per phase found in the loss table.
    present = {f.phase for f in report.losses}
    if not present:
        raise SystemExit("ERROR: no phases found and no `analysis` sheet in the workbook.")
    phases = [p for p in _PHASE_ORDER if p in present]
    phases += sorted(p for p in present if p not in _PHASE_ORDER)
    cases = [AnalysisCase(label=ph, phase=ph) for ph in phases]
    case_results = evaluate(report, cases, build_kwargs={"iv_engine": engine})
    rpt = Report.from_results(report, case_results, build_array=True, iv_engine=engine)
    rpt.render(workdir)
    return rpt.compile_pdf(out_pdf), phases, report


def _cmd_report(args) -> int:
    import warnings
    warnings.filterwarnings("ignore")        # mute legacy pkg_resources / FP noise
    params = _find_params(args.params)
    out = Path(args.out).resolve()
    print("report: %s  ->  %s   [engine=%s]" % (params, out, args.engine))
    pdf, phases, report = build_electrical_report(
        params, out, data_dir=args.data_dir, engine=args.engine)
    print("  doc    : %s" % getattr(report.document, "doc_number", "?"))
    print("  phases : %s" % ", ".join(phases))
    if pdf is None:
        print("  pdflatex not found; wrote the LaTeX workspace only.")
        return 1
    print("  OK -> %s" % pdf)
    return 0


def _cmd_sweep(args) -> int:
    layout = load_layout(args.layout)
    a = auto_monte_carlo(layout, t_limit_c=args.t_limit, solve_kwargs=_solve_kwargs(args),
                         p_fail=args.p_fail, target_se=args.target_se, batch=args.batch,
                         max_runs=args.max_runs, seed=args.seed, healthy_w=args.healthy_w,
                         reverse_w=args.reverse_w, workers=args.workers)
    print("auto Monte-Carlo: %s after %d runs" % (a["stopped"], a["n_runs"]))
    print("  mean peak %.1f degC, max peak %.1f degC, standard error %.2f"
          % (a["mean_peak_c"], a["max_peak_c"], a["standard_error"]))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="powerpy", description="Solar-array panel thermal analysis")
    sub = parser.add_subparsers(dest="cmd", required=True)

    pr = sub.add_parser("run", help="solve one panel + write report")
    _add_common(pr)
    pr.add_argument("--fail", nargs="*", default=[], help="flat tile indices to fail (reverse-biased)")
    pr.add_argument("--report", default=None, help="HTML report output path")
    pr.add_argument("--json", default=None, help="JSON results output path")
    pr.set_defaults(func=_cmd_run)

    pw = sub.add_parser("worst", help="greedy worst-case failure search")
    _add_common(pw)
    pw.add_argument("--max-failures", type=int, default=3, dest="max_failures")
    pw.add_argument("--report", default=None)
    pw.add_argument("--json", default=None)
    pw.set_defaults(func=_cmd_worst)

    ps = sub.add_parser("sweep", help="auto-stopping Monte-Carlo failure sweep")
    _add_common(ps)
    ps.add_argument("--p-fail", type=float, default=0.05, dest="p_fail")
    ps.add_argument("--target-se", type=float, default=2.0, dest="target_se")
    ps.add_argument("--batch", type=int, default=50)
    ps.add_argument("--max-runs", type=int, default=2000, dest="max_runs")
    ps.add_argument("--seed", type=int, default=0)
    ps.set_defaults(func=_cmd_sweep)

    prp = sub.add_parser("report", help="electrical report PDF from params.xlsx (no ngspice)")
    prp.add_argument("params", nargs="?", default=None,
                     help="path to params.xlsx (default: auto-find in CWD/examples/root)")
    prp.add_argument("--out", default="reports/_noNG_elec.pdf", help="output PDF path")
    prp.add_argument("--engine", choices=["analytic", "ngspice"], default="analytic",
                     help="IV engine (default: analytic = no ngspice)")
    prp.add_argument("--data-dir", default=None, dest="data_dir",
                     help="reference data dir (default: packaged powerpy/data)")
    prp.set_defaults(func=_cmd_report)
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
