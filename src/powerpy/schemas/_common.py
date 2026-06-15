"""Shared label vocabularies + matching helper.

Mission phases, launch configs, flux params and loss levels are **plain
strings** defined by each project's workbook -- NOT enums -- because the
naming convention (BOL/EOL, single/dual, ...) varies from project to project.
The classes below are just convenience constants for the demo workbook; a
project may use any names, and matching across sheets is done with :func:`norm`
so casing/whitespace differences never break a lookup.
"""


def norm(value) -> str:
    """Normalise a label for matching across sheets: stripped, lower-cased."""
    return str(value).strip().lower()


class Phase:
    """Convenience constants for the demo workbook's mission phases (plain str)."""
    BOL_ATC = "BOL_ATC"
    BOL_BC = "BOL_BC"
    END_OF_LEOP = "End_of_LEOP"
    END_OF_ORP = "End_of_ORP"
    END_OF_LIFE = "End_of_Life"


class Level:
    """Convenience constants for the hierarchy level a loss applies at (plain str)."""
    CELL = "cell"
    STRING = "string"
    SECTION = "section"
    PANEL = "panel"
    ARRAY = "array"
