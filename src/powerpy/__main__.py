# -*- coding: utf-8 -*-
"""Enable ``python -m powerpy ...`` -> the CLI in app.py."""
import sys

from .app import main

if __name__ == "__main__":
    sys.exit(main())
