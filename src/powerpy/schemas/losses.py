"""Loss factors: long-format collection with filtering and aggregation."""
import math
from dataclasses import dataclass

from powerpy.schemas._common import norm


@dataclass(frozen=True)
class LossFactor:
    name: str
    phase: str
    value: float
    level: str
    description: str = ""
    source: str = ""


@dataclass(frozen=True)
class LossCollection:
    items: tuple[LossFactor, ...]

    def by_phase(self, phase: str) -> "LossCollection":
        return LossCollection(tuple(l for l in self.items if norm(l.phase) == norm(phase)))

    def by_level(self, level: str) -> "LossCollection":
        return LossCollection(tuple(l for l in self.items if norm(l.level) == norm(level)))

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
