# -*- coding: utf-8 -*-
"""Generate the no-ngspice electrical report  ->  reports/_noNG_elec.pdf

Thin wrapper around the same logic the CLI uses (``powerpy report``). Kept as an
example/launcher that needs no install: it puts ``src/`` on the path the way
``run.py`` does, then calls :func:`powerpy.app.build_electrical_report` with the
analytic single-diode engine (NO ngspice, NO legacy cell file -- hence "_noNG").

Usage (from anywhere):
    python examples/build_noNG_elec_report.py                 # find params.xlsx automatically
    python examples/build_noNG_elec_report.py path/to/params.xlsx

Equivalent CLI:
    python run.py report                                      # or: powerpy report
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

# --- zero-install path setup (mirrors run.py): make `import powerpy` work ----
_ROOT = Path(__file__).resolve().parent.parent          # .../powerpy
sys.path.insert(0, str(_ROOT / "src"))

from powerpy.app import build_electrical_report, _find_params   # noqa: E402

OUT_PDF = _ROOT / "reports" / "_noNG_elec.pdf"


def main() -> int:
    warnings.filterwarnings("ignore")
    params = _find_params(sys.argv[1] if len(sys.argv) > 1 else None)
    print(f"[noNG] params : {params}")
    print(f"[noNG] out    : {OUT_PDF}")
    pdf, phases, report = build_electrical_report(params, OUT_PDF, engine="analytic")
    print(f"[noNG] doc    : {getattr(report.document, 'doc_number', '?')}")
    print(f"[noNG] phases : {', '.join(phases)}")
    if pdf is None:
        print("[noNG] pdflatex not found -- wrote the LaTeX workspace only.")
        return 1
    print(f"[noNG] OK -> {pdf}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
