import math
import uuid
from dataclasses import dataclass, field

RECENCY_DECAY = 0.995


@dataclass
class MemoryEntry:
    id: str
    tick: int
    description: str
    importance: int  # 1-10


class MemoryStream:
    def __init__(self):
        self.entries: list[MemoryEntry] = []

    def write(self, description: str, importance: int, tick: int) -> MemoryEntry:
        entry = MemoryEntry(
            id=uuid.uuid4().hex[:12],
            tick=tick,
            description=description,
            importance=importance,
        )
        self.entries.append(entry)
        return entry

    def query(self, context: str, current_tick: int, limit: int = 10) -> list[MemoryEntry]:
        scored = []
        for entry in self.entries:
            relevance = self._relevance(entry.description, context)
            recency = RECENCY_DECAY ** (current_tick - entry.tick)
            score = relevance * entry.importance * recency
            scored.append((score, entry))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [entry for _, entry in scored[:limit]]

    def recent(self, n: int = 10) -> list[MemoryEntry]:
        return self.entries[-n:]

    def _relevance(self, text: str, context: str) -> float:
        keywords = set(context.split())
        words = set(text.split())
        overlap = keywords & words
        if not keywords:
            return 1.0
        return len(overlap) / len(keywords) if keywords else 0.0
