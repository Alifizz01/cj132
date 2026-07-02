"""Phase-4 gate: the CLI's final intent-verb shape.

The behavioural gates (analyse xlsx value-identical, sweep --worst artifacts
byte-identical to the old worst command) were run against captured baselines
during the phase; this file pins the structure.
"""
from pathlib import Path

import pytest

from powerpy.app import build_parser

ROOT = Path(__file__).resolve().parents[1]


def _subcommands(parser):
    for action in parser._actions:
        if hasattr(action, "choices") and action.choices:
            return set(action.choices)
    return set()


def test_parser_has_exactly_the_four_verbs():
    assert _subcommands(build_parser()) == {"run", "sweep", "report", "analyse"}


def test_worst_subcommand_is_gone():
    with pytest.raises(SystemExit):
        build_parser().parse_args(["worst", "x.json"])


def test_every_verb_help_builds():
    parser = build_parser()
    for verb in ("run", "sweep", "report", "analyse"):
        with pytest.raises(SystemExit) as e:
            parser.parse_args([verb, "--help"])
        assert e.value.code == 0


def test_analyse_compute_lives_in_the_package():
    from powerpy.analysis.operating import analyse_operating_point  # noqa: F401
    shim = (ROOT / "scripts" / "write_results.py").read_text(encoding="utf-8")
    assert "analyse_operating_point" not in shim      # script no longer computes
    assert "powerpy.app" in shim                      # it forwards to the CLI


def test_debris_deleted():
    assert not (ROOT / "examples" / "build_noNG_elec_report.py").exists()
    for name in ("add_analysis_sheet", "add_requirement_sheet",
                 "set_mission_orbit", "edit_structure"):
        assert not (ROOT / "scripts" / (name + ".py")).exists(), name
