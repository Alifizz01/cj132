"""Load a free-form circuit JSON into a CircuitLayout."""
from __future__ import annotations

import json
from pathlib import Path

from powerpy.schemas.circuit import CircuitLayout, CircuitSection, CircuitString


def load_circuit(json_path: Path) -> CircuitLayout:
    json_path = Path(json_path)
    if not json_path.exists():
        raise FileNotFoundError("circuit file not found: %s" % json_path)
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    sections = []
    for sec in data.get("sections", []):
        strings = tuple(
            CircuitString(
                id=str(s["id"]),
                n_series=int(s["n_series"]),
                series_resistance_ohm=float(s.get("series_resistance_ohm", 0.0)),
                block_diode_v_drop=float(s.get("block_diode_v_drop", 0.6)),
                n_block_diodes=int(s.get("n_block_diodes", 1)),
                string_shunt_diode=bool(s.get("string_shunt_diode", True)),
            )
            for s in sec.get("strings", [])
        )
        sections.append(CircuitSection(
            id=str(sec["id"]),
            strings=strings,
            panel=str(sec.get("panel", "panel_1")),
            resistance_ohm=float(sec.get("resistance_ohm", 0.0)),
        ))
    return CircuitLayout(name=str(data.get("name", json_path.stem)),
                         sections=tuple(sections))
