"""CLI entry point and example usage.

Run with:
    python -m powerpy.main path/to/params.xlsx
"""
from __future__ import annotations

import sys
from pathlib import Path

from powerpy.loader import load_report_data
from powerpy.schemas import Phase, Level


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("Usage: python -m powerpy.main <params.xlsx> [data_dir]")
        return 1

    params_file = Path(argv[1])
    data_dir = Path(argv[2]) if len(argv) > 2 else params_file.parent / "data"

    print(f"Loading {params_file} ...")
    data = load_report_data(params_file, data_dir)

    # Quick summary so you can verify the load worked
    print()
    print("=" * 60)
    print(f"Document: {data.document.doc_number}, Issue {data.document.issue}")
    print(f"Title:    {data.document.doc_title}")
    print(f"Customer: {data.document.customer}")
    print()
    print(f"Cell:     {data.cell.name} ({data.cell.manufacturer})")
    print(f"Area:     {data.cell.cell_area_cm2} cm² ({data.cell.cell_area_m2:.4e} m²)")
    print()
    print(f"Mission:  {len(data.mission)} operating points")
    print()
    print(f"Array:    {data.array_layout.topology.n_wings} wings × "
          f"{data.array_layout.topology.n_panels_per_wing} panels/wing")
    print(f"          {data.array_layout.n_sections_total} physical sections")
    print(f"          {data.array_layout.n_strings_total} strings")
    print(f"          {data.array_layout.n_sca_total} SCAs total")
    print()
    print(f"Losses:   {len(data.losses)} entries")
    eol_cell = data.losses.by_phase(Phase.END_OF_LIFE).by_level(Level.CELL)
    print(f"          EOL cell-level total factor: {eol_cell.total_factor():.4f}")
    print()
    print(f"Fluxes:   {len(data.radiation_fluxes)} entries")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
