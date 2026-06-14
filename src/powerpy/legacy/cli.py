"""Command-line entry point.

Activates after::

    pip install -e .                # in C:\\Users\\Nitrox\\Downloads\\powerpy\\powerpy
    powerpy run path/to/params.xlsx

The CLI is intentionally thin -- it delegates straight to
``powerpy.test.main`` so there is one source of truth for the driver.
"""
from __future__ import annotations

import sys

from powerpy.test import main as _main


def main() -> int:
    return _main(sys.argv[1:])


if __name__ == "__main__":
    sys.exit(main())
