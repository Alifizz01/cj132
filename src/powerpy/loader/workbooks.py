"""The two-file database front door: which workbook holds which half.

``design.xlsx`` holds the hardware (cell, topology, variance); ``scenario.xlsx``
holds the run (losses, mission, analysis scope, condition layers, report meta).
Legacy single-file mode is a :class:`Workbooks` whose two paths are the same
file, so every existing ``params.xlsx`` workflow keeps working unchanged.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

DESIGN_NAME = "design.xlsx"
SCENARIO_NAME = "scenario.xlsx"
LEGACY_NAME = "params.xlsx"


@dataclass(frozen=True)
class Workbooks:
    """The (design, scenario) workbook pair; equal paths = legacy single file."""
    design: Path
    scenario: Path

    @classmethod
    def legacy(cls, path: Path) -> "Workbooks":
        p = Path(path)
        return cls(design=p, scenario=p)

    @property
    def is_split(self) -> bool:
        return self.design != self.scenario


def _require(path: Path, role: str) -> Path:
    p = Path(path).expanduser().resolve()
    if not p.is_file():
        raise FileNotFoundError("%s workbook not found: %s" % (role, p))
    return p


def find_workbooks(
    design: Path | str | None = None,
    scenario: Path | str | None = None,
    legacy_params: Path | str | None = None,
    search_dirs: Iterable[Path] = (),
) -> Workbooks:
    """Resolve the workbook pair.

    Precedence: an explicit ``design``+``scenario`` pair; a lone ``design`` or
    ``legacy_params`` (legacy single-file mode); otherwise each ``search_dirs``
    entry is checked for ``design.xlsx``+``scenario.xlsx`` together, then for
    ``params.xlsx``. Raises :class:`FileNotFoundError` listing the searched
    locations when nothing is found.
    """
    if design and scenario:
        return Workbooks(design=_require(design, "design"),
                         scenario=_require(scenario, "scenario"))
    if design:
        return Workbooks.legacy(_require(design, "design"))
    if scenario:
        return Workbooks.legacy(_require(scenario, "scenario"))
    if legacy_params:
        return Workbooks.legacy(_require(legacy_params, "params"))

    searched = []
    for d in search_dirs:
        d = Path(d)
        pair = (d / DESIGN_NAME, d / SCENARIO_NAME)
        if pair[0].is_file() and pair[1].is_file():
            return Workbooks(design=pair[0].resolve(), scenario=pair[1].resolve())
        legacy = d / LEGACY_NAME
        if legacy.is_file():
            return Workbooks.legacy(legacy.resolve())
        searched.append(str(d))
    raise FileNotFoundError(
        "no workbooks found: looked for %s+%s (or %s) in: %s"
        % (DESIGN_NAME, SCENARIO_NAME, LEGACY_NAME, ", ".join(searched) or "<no dirs>"))
