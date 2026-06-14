# Running PowerPy without `pip install` (vendored-dependency workflow)

The office environment does **not** allow `pip install`, so PowerPy is designed to
run **straight from source** with its third-party SPICE binding **vendored** in the
repo. No installation step is required.

## How to run

**Option A — the launcher (simplest):**
```
python run.py run   data/layouts/example_panel.json --g-lat 0.045 --report out.html
python run.py worst data/layouts/example_panel.json --max-failures 3
python run.py sweep data/layouts/example_panel.json --p-fail 0.05
```
`run.py` just puts `src/` on the import path and calls the CLI — nothing is installed.

**Option B — module form:**
```
# Windows:  set PYTHONPATH=src
# bash:     export PYTHONPATH=src
python -m powerpy run data/layouts/example_panel.json ...
```

**In code (scripts / notebooks):**
```python
import sys; sys.path.insert(0, "src")
from powerpy.solve import solve_panel, solve_transient
from powerpy.config import load_layout
```
(The test-suite uses the same "add src / load by file path" approach — it never installs.)

## Dependencies

| Dependency | How it's provided | Notes |
|---|---|---|
| **ngspice / PySpice** | **vendored** at `src/powerpy/ngspice/` | imported as `powerpy.ngspice`; the electrical solver's default backend uses it. **Do not remove it.** Still needs the `libngspice` shared library present on the machine (system-provided). |
| numpy, scipy | expected pre-installed | core math; scipy used for the sparse lateral solver |
| pandas, openpyxl | expected pre-installed (lazy) | only the `reporting.store` Parquet/HDF5/Excel paths import them |

If a machine lacks numpy/scipy and cannot `pip install`, those must be provided by
the base Python (e.g. a scientific distribution) — they contain compiled C
extensions and cannot simply be copied into the repo like a pure-Python package.

## Adding a future vendored (pure-Python) dependency
Drop the package's source folder under `src/powerpy/` (or a `src/powerpy/_vendor/`)
and import it relatively (`from .._vendor.<pkg> import ...`), exactly as `ngspice`
is done. Keep it out of `.gitignore` so it travels with the repo.

> `pip install -e .` and the `powerpy` console-script (see `pyproject.toml`) are a
> convenience for machines that *do* allow installs; they are **not required** —
> `run.py` / `PYTHONPATH=src` give the identical functionality with zero install.
