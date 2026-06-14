"""Free-form prose, keyed by id, that the structure sheet refers to.

The ``narrative`` sheet has two columns -- ``id`` and ``paragraph``.
Many rows may share an ``id``; they are joined into the section in
sheet order.  Whenever a ``structure`` row of type ``section`` is
rendered, the renderer looks up every paragraph with the same id and
emits them in order.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NarrativeParagraph:
    id: str
    paragraph: str
    row_index: int = 0


@dataclass(frozen=True)
class NarrativeBook:
    """An ordered collection of paragraphs, lookup-by-id."""

    paragraphs: tuple[NarrativeParagraph, ...]

    def by_id(self, id: str) -> tuple[str, ...]:
        """Return every paragraph for this id, in sheet order."""
        return tuple(p.paragraph for p in self.paragraphs if p.id == id)

    def ids(self) -> tuple[str, ...]:
        """Unique ids, in first-seen order."""
        seen: list[str] = []
        for p in self.paragraphs:
            if p.id not in seen:
                seen.append(p.id)
        return tuple(seen)

    def __iter__(self):
        return iter(self.paragraphs)

    def __len__(self):
        return len(self.paragraphs)

    def __bool__(self):
        return bool(self.paragraphs)

    @classmethod
    def empty(cls) -> "NarrativeBook":
        return cls(())
