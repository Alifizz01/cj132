# PowerPy

Solar Array Analysis Report Generator — Airbus Defence and Space.

## Setup

```bash
pip install -e .
```

## Project structure

```
src/powerpy/
├── schemas/        Typed dataclasses (the in-memory data model)
├── loader/         Excel → dataclasses (one loader per sheet)
├── simulation/     Pure-math analysis layer (to be implemented)
├── render/         LaTeX templates and PDF compilation (to be implemented)
└── data/           Reference files (cell JSON, diode JSON, assets)
```

## Two sheet conventions

**Key-value sheets** (singletons like cell_params, mission_params, document_meta):
```
| param | name | value | unit | type | source |
```

**Long-format sheets** (collections like losses, radiation_fluxes):
```
| <identifier_cols> | value | <context_cols> | description | source | include | notes |
```

The `_common.py` helpers in `loader/` enforce these conventions.

## Entry point

```python
from pathlib import Path
from powerpy.loader.report import load_report_data

data = load_report_data(Path("params.xlsx"), Path("src/powerpy/data"))
print(data.document.doc_number)
print(data.losses.by_phase(Phase.END_OF_LIFE).total_factor())
```
