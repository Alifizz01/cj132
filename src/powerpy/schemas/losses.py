"""Loss factors: long-format collection with filtering and aggregation."""
import math
from dataclasses import dataclass

from powerpy.schemas._common import Phase, Level


@dataclass(frozen=True)
class LossFactor:
    name: str
    phase: Phase
    value: float
    level: Level
    description: str = ""
    source: str = ""


@dataclass(frozen=True)
class LossCollection:
    items: tuple[LossFactor, ...]

    def by_phase(self, phase: Phase) -> "LossCollection":
        return LossCollection(tuple(l for l in self.items if l.phase == phase))

    def by_level(self, level: Level) -> "LossCollection":
        return LossCollection(tuple(l for l in self.items if l.level == level))

    def by_name(self, name: str) -> "LossCollection":
        return LossCollection(tuple(l for l in self.items if l.name == name))

    def total_factor(self) -> float:
        """Product of all loss values. Returns 1.0 for an empty collection."""
        if not self.items:
            return 1.0
        return math.prod(l.value for l in self.items)

    def __iter__(self):
        return iter(self.items)

    def __len__(self):
        return len(self.items)

    def __bool__(self):
        return bool(self.items)
