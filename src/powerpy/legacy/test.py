"""Driver: load a workbook -> simulate every case -> render -> PDF.

THREE-LAYER ARCHITECTURE
=========================

Layer 1: Configuration (Excel)
  └─ params.xlsx is the SINGLE SOURCE OF TRUTH
     Contains all parameters, metadata, and specifications

Layer 2: Transformation (Loader → Simulation → Render)
  
  2a. LOADER (powerpy.loader)
      Input:  params.xlsx + data/
      Output: ReportMetadata (fully validated, immutable)
       └─ Parses & validates all Excel sheets
       └─ Loads external JSON references (cell models, diodes)
       └─ Type conversions & bounds checking
  
  2b. SIMULATION (powerpy.simulation)
      Input:  ReportMetadata + AnalysisCase[] (environmental specs)
      Output: SimulationResults[] (one per case)
       └─ build_from_report() constructs array hierarchy model
       └─ evaluate() runs N cases, returns results
       └─ Pure math: IV curves, losses, temperature, radiation
  
  2c. RENDER (powerpy.render)
      Input:  ReportMetadata + SimulationResults[]
      Output: RenderedReport (LaTeX code + PDF)
       └─ Embeds figures, tables, equations from results
       └─ Filters sections by ReportStructure + audience
       └─ Injects narrative prose
       └─ Compiles to PDF via pdflatex

Layer 3: Output
  └─ PDF report (or .tex if pdflatex unavailable)

SEPARATION OF CONCERNS
  • Loader: "What are the inputs?"    (parse & validate)
  • Simulation: "What are the results?" (compute physics)
  • Render: "How to present results?" (format & style)
  
ARCHITECTURE FLOW IN test.py
  Step [1/4]: LOADER - load_report_data(params.xlsx, data_dir) → metadata
  Step [2/4]: SIMULATION - evaluate(metadata, cases) → results
  Step [3/4]: RENDER - Report.from_results(metadata, results).render() → .tex
  Step [4/4]: COMPILE - report.compile_pdf() → PDF

This file is the orchestration layer meant to be edited by *users* to define
their analysis cases. Everything else stays the same.

Run with::

    python -m powerpy.test path/to/params.xlsx

or, once the package is pip-installed::

    powerpy run path/to/params.xlsx                  # see cli.py
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from powerpy.loader import load_report_data
from powerpy.schemas import Audience, LaunchConfig, Phase
from powerpy.render import Report
from powerpy.simulation import AnalysisCase, evaluate


# ================================================================ USER EDITABLE SECTION
def default_cases() -> list[AnalysisCase]:
    """Define the analysis cases to simulate.

    Edit this freely -- it is the only part of test.py meant to change per study.
    Each case specifies a phase, launch configuration, and environmental conditions.

    A reasonable starting set: BOL & EOL, both launch configs.
    """
    return [
        AnalysisCase(label="BOL_single",
                     phase=Phase.BOL_ATC,
                     launch_config=LaunchConfig.SINGLE,
                     temperature_c=28.0, season=1.0),
        AnalysisCase(label="EOL_single",
                     phase=Phase.END_OF_LIFE,
                     launch_config=LaunchConfig.SINGLE,
                     temperature_c=51.1, season=0.967),
        AnalysisCase(label="EOL_dual",
                     phase=Phase.END_OF_LIFE,
                     launch_config=LaunchConfig.DUAL,
                     temperature_c=51.1, season=0.967),
    ]


# ================================================================ DISPLAY HELPERS
def print_metadata_summary(metadata) -> None:
    """Print a summary of loaded metadata (for verification)."""
    print()
    print("=" * 70)
    print("METADATA LOADED FROM WORKBOOK")
    print("=" * 70)
    print(f"Document    : {metadata.document.doc_title}")
    print(f"Project     : {metadata.document.project}")
    print(f"Doc Number  : {metadata.document.doc_number}")
    print(f"Author      : {metadata.document.author}")
    print(f"Classification: {metadata.document.classification}")
    print(f"Cell        : {metadata.cell.name} ({metadata.cell.manufacturer})")
    print(f"Sections    : {len(metadata.array_layout.physical_sections)} total")
    print(f"Strings     : {metadata.array_layout.n_strings_total}")
    print(f"SCAs        : {metadata.array_layout.n_sca_total}")
    print(f"Mission pts : {len(metadata.mission)} items")
    print(f"Loss factors: {len(metadata.losses)} items")
    print(f"Flux points : {len(metadata.radiation_fluxes)} items")
    print()


def summarise_results_to_stdout(case_results) -> None:
    """Print a summary table of simulation results."""
    print()
    print("=" * 70)
    print("SIMULATION RESULTS")
    print("=" * 70)
    print(f"{'CASE':<14}{'Vmp [V]':>10}{'Imp [A]':>10}"
          f"{'Pmp [W]':>10}{'I@Vbus [A]':>12}{'P@Vbus [W]':>12}")
    print("-" * 70)
    for c in case_results:
        bus_i = c.bus.current_a if c.bus else float("nan")
        bus_p = c.bus.power_w if c.bus else float("nan")
        a = c.results.array
        print(f"{c.case.label:<14}{a.v_mp:>10.2f}{a.i_mp:>10.3f}"
              f"{a.p_mp:>10.1f}{bus_i:>12.3f}{bus_p:>12.1f}")
    print()


# ================================================================ MAIN ENTRY POINT
def main(argv: list[str]) -> int:
    """Load workbook → Simulate cases → Render PDF.

    Returns 0 on success, non-zero on error.
    """
    p = argparse.ArgumentParser(
        prog="powerpy-test",
        description="Load a workbook, simulate every case, render a PDF.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  powerpy test params.xlsx
  powerpy test params.xlsx --workdir ./build --out report.pdf
  powerpy test params.xlsx --no-pdf  # just generate .tex
  powerpy test params.xlsx --audience customer
        """)
    
    p.add_argument("workbook", type=Path,
                   help="path to the input params.xlsx")
    p.add_argument("--data-dir", type=Path, default=None,
                   help="directory containing JSON references "
                        "(cell models, diodes, etc.). "
                        "Default: <workbook>/../data")
    p.add_argument("--workdir", type=Path, default=Path("./build"),
                   help="working directory for .tex and figures "
                        "(default: ./build)")
    p.add_argument("--out", type=Path, default=Path("./report.pdf"),
                   help="output PDF path (default: ./report.pdf)")
    p.add_argument("--requirement-w", type=float, default=None,
                   help="power requirement [W] to overlay on figures")
    p.add_argument("--audience", choices=[a.value for a in Audience],
                   default=None,
                   help="filter report sections by audience "
                        "(customer|engineer|both). "
                        "Default: all included sections")
    p.add_argument("--no-pdf", action="store_true",
                   help="render .tex only, skip pdflatex compilation")
    p.add_argument("--verbose", action="store_true",
                   help="print metadata summary before simulation")
    
    args = p.parse_args(argv)

    # Resolve paths
    data_dir = args.data_dir or (args.workbook.parent / "data")

    # ====== STEP 1: LOAD WORKBOOK ======
    try:
        print()
        print("[1/4] Loading workbook")
        print(f"      params_file : {args.workbook}")
        print(f"      data_dir    : {data_dir}")
        metadata = load_report_data(args.workbook, data_dir)
        print("      ✓ loaded successfully")
    except FileNotFoundError as e:
        print(f"      ✗ File error: {e}")
        return 1
    except ValueError as e:
        print(f"      ✗ Validation error: {e}")
        return 1
    except Exception as e:
        print(f"      ✗ Unexpected error: {type(e).__name__}: {e}")
        return 1

    if args.verbose:
        print_metadata_summary(metadata)

    # ====== STEP 2: SIMULATE CASES ======
    try:
        print("[2/4] Simulating analysis cases")
        cases = default_cases()
        print(f"      {len(cases)} cases defined:")
        for case in cases:
            print(f"        - {case.label}: phase={case.phase.value}, "
                  f"launch_config={case.launch_config.value}, "
                  f"T={case.temperature_c}°C, season={case.season}")
        
        case_results = evaluate(metadata, cases)
        print("      ✓ simulation complete")
    except Exception as e:
        print(f"      ✗ Simulation error: {type(e).__name__}: {e}")
        return 1

    summarise_results_to_stdout(case_results)

    # ====== STEP 3: RENDER LATEX ======
    try:
        print("[3/4] Rendering LaTeX")
        print(f"      workdir  : {args.workdir}")
        
        report = Report.from_results(
            metadata, case_results,
            requirement_w=args.requirement_w,
        ).render(args.workdir, audience=args.audience)
        
        print("      ✓ .tex rendered")
        if args.audience:
            print(f"      ✓ audience filter: {args.audience}")
    except Exception as e:
        print(f"      ✗ Rendering error: {type(e).__name__}: {e}")
        return 1

    # ====== STEP 4: COMPILE PDF (OPTIONAL) ======
    if args.no_pdf:
        print("[4/4] Skipped PDF compilation (--no-pdf)")
        print(f"      LaTeX workspace: {report.workspace}")
        return 0

    try:
        print("[4/4] Compiling PDF")
        pdf = report.compile_pdf(args.out)
        
        if pdf is None:
            print("      ✗ pdflatex not available")
            print(f"      ✓ .tex written to: {report.workspace}")
            return 1
        
        print(f"      ✓ PDF compiled: {pdf}")
        return 0
    except Exception as e:
        print(f"      ✗ PDF compilation error: {type(e).__name__}: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
