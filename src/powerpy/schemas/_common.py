"""Shared enums used across multiple schema modules."""
from enum import Enum


class Phase(str, Enum):
    """Mission phase. Used by losses and radiation fluxes."""
    BOL_ATC = "BOL_ATC"
    BOL_BC = "BOL_BC"
    END_OF_LEOP = "End_of_LEOP"
    END_OF_ORP = "End_of_ORP"
    END_OF_LIFE = "End_of_Life"


class Level(str, Enum):
    """Hierarchy level at which a loss factor applies."""
    CELL = "cell"
    STRING = "string"
    SECTION = "section"
    PANEL = "panel"
    ARRAY = "array"
