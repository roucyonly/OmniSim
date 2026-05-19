import uuid
from dataclasses import dataclass, field

RECENCY_DECAY = 0.995


@dataclass
class MemoryEntry:
    id: str
    tick: int
    description: str
    importance: int = 3                  # 1-10
    # 增强字段
    emotion_tag: str = "平静"            # 开心/愤怒/悲伤/恐惧/惊讶/平静
    involved_agents: list[str] = field(default_factory=list)
    location: str = ""
    # 传播字段（Plan 3 gossip 用）
    gossip_worthy: bool = False
    source_id: str | None = None
    hops: int = 0
    is_secondhand: bool = False
    known_by: list[str] = field(default_factory=list)


class MemoryStream:
    def __init__(self):
        self.entries: list[MemoryEntry] = []

    def write(
        self,
        description: str,
        importance: int,
        tick: int,
        *,
        emotion: str = "平静",
        involved_agents: list[str] | None = None,
        location: str = "",
        source_id: str | None = None,
        hops: int = 0,
    ) -> MemoryEntry:
        entry = MemoryEntry(
            id=uuid.uuid4().hex[:12],
            tick=tick,
            description=description,
            importance=importance,
            emotion_tag=emotion,
            involved_agents=involved_agents or [],
            location=location,
            gossip_worthy=importance >= 7,
            source_id=source_id,
            hops=hops,
            is_secondhand=source_id is not None,
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

    def query_by_agents(self, agent_ids: list[str], limit: int = 5) -> list[MemoryEntry]:
        results = [
            e for e in self.entries
            if any(aid in e.involved_agents for aid in agent_ids)
        ]
        results.sort(key=lambda e: e.importance, reverse=True)
        return results[:limit]

    def query_by_emotion(self, emotion: str, limit: int = 5) -> list[MemoryEntry]:
        results = [e for e in self.entries if e.emotion_tag == emotion]
        results.sort(key=lambda e: e.importance, reverse=True)
        return results[:limit]

    def get_gossipworthy(
        self,
        exclude_known_by: str | None = None,
        limit: int = 2,
    ) -> list[MemoryEntry]:
        results = []
        for e in reversed(self.entries):
            if not e.gossip_worthy:
                continue
            if exclude_known_by and exclude_known_by in e.known_by:
                continue
            results.append(e)
            if len(results) >= limit:
                break
        return results

    def _relevance(self, text: str, context: str) -> float:
        keywords = set(context.split())
        words = set(text.split())
        overlap = keywords & words
        if not keywords:
            return 1.0
        return len(overlap) / len(keywords) if keywords else 0.0
