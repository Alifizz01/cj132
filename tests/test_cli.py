# -*- coding: utf-8 -*-
"""Tests for the powerpy CLI (app.py). Imports the package (src on path)."""
import os
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "src"))   # works without pip install

import powerpy                                          # noqa: E402
import powerpy.app as app                               # noqa: E402

LAYOUT = os.path.join(powerpy.power_path, "data", "layouts", "example_panel.json")


def test_run_writes_report_and_returns_zero():
    d = tempfile.mkdtemp()
    h = os.path.join(d, "r.html"); j = os.path.join(d, "r.json")
    rc = app.main(["run", LAYOUT, "--fail", "20", "--g-lat", "0.04",
                   "--report", h, "--json", j])
    assert rc == 0
    assert os.path.getsize(h) > 500 and os.path.getsize(j) > 100


def test_worst_subcommand():
    rc = app.main(["worst", LAYOUT, "--max-failures", "2", "--g-lat", "0.04"])
    assert rc == 0


def test_sweep_subcommand_autostop():
    rc = app.main(["sweep", LAYOUT, "--p-fail", "0.3", "--target-se", "1e6",
                   "--batch", "4", "--max-runs", "8", "--seed", "1"])
    assert rc == 0


def test_parser_requires_subcommand():
    import argparse
    try:
        app.build_parser().parse_args([])     # no subcommand -> SystemExit
        assert False, "expected SystemExit"
    except SystemExit:
        pass


if __name__ == "__main__":
    passed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn(); print("PASS", name); passed += 1
    print("\n%d/%d tests passed" % (passed, passed))
