"""DEPRECATED shim -- the flow lives at ``powerpy analyse`` since P4.

Kept so existing invocations and tests keep working:
    python scripts/write_results.py --blocks 1 --parallel 4 --series 10
is forwarded verbatim to
    powerpy analyse --blocks 1 --parallel 4 --series 10
(the legacy ``--params X`` option is rewritten to the positional argument).
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))

from powerpy.app import main as _app_main


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--params" in argv:                       # legacy option -> positional
        i = argv.index("--params")
        argv[i:i + 2] = [argv[i + 1]]
    return _app_main(["analyse", *argv])


if __name__ == "__main__":
    raise SystemExit(main())
