from __future__ import annotations

from dataclasses import dataclass

from .memory import MemoryStream, MemoryEntry
from .relationship import Relationship


@dataclass
class ReflectionResult:
    content: str
    tick: int
    impression_updates: dict[str, str] | None = None  # {target_id: new_impression}


REFLECTION_INTERVAL = 6


class Reflector:
    def should_reflect(self, tick: int) -> bool:
        return tick > 0 and tick % REFLECTION_INTERVAL == 0

    def reflect(
        self,
        memories: MemoryStream,
        current_tick: int,
        relationships: dict[str, Relationship] | None = None,
    ) -> ReflectionResult | None:
        recent = memories.recent(10)
        if not recent:
            return None

        summary = self._summarize(recent, current_tick)
        impression_updates = self._update_impressions(recent, relationships)

        return ReflectionResult(
            content=summary,
            tick=current_tick,
            impression_updates=impression_updates or None,
        )

    def _summarize(self, memories: list[MemoryEntry], current_tick: int) -> str:
        # 按情绪分组统计
        emotion_counts: dict[str, int] = {}
        for m in memories:
            emotion_counts[m.emotion_tag] = emotion_counts.get(m.emotion_tag, 0) + 1

        dominant_emotion = max(emotion_counts, key=emotion_counts.get, default="平静")

        # 按描述去重统计高频行为
        action_counts: dict[str, int] = {}
        for m in memories:
            action_counts[m.description] = action_counts.get(m.description, 0) + 1

        frequent = [desc for desc, count in action_counts.items() if count >= 2]

        parts = []
        if frequent:
            activities = "、".join(frequent[:2])
            parts.append(f"最近经常{activities}")
        else:
            last = memories[-1]
            parts.append(f"最近经历了{last.description}")

        if dominant_emotion != "平静":
            parts.append(f"心情总体偏{dominant_emotion}")

        return "，".join(parts) + "。"

    def _update_impressions(
        self,
        memories: list[MemoryEntry],
        relationships: dict[str, Relationship] | None,
    ) -> dict[str, str]:
        if not relationships:
            return {}

        updates: dict[str, str] = {}
        # 找最近涉及他人的记忆
        for m in reversed(memories):
            for agent_id in m.involved_agents:
                rel = relationships.get(agent_id)
                if not rel:
                    continue
                # 根据记忆情绪生成印象
                new_impression = self._generate_impression(m, rel)
                if new_impression and new_impression != rel.impression:
                    rel.impression = new_impression
                    updates[agent_id] = new_impression

        return updates

    def _generate_impression(self, memory: MemoryEntry, rel: Relationship) -> str:
        emotion = memory.emotion_tag
        if emotion in ("开心", "信任"):
            return f"最近相处愉快"
        if emotion in ("愤怒", "厌恶"):
            return f"最近有些不愉快"
        if emotion == "悲伤":
            return f"最近让人有些担心"
        if rel.interaction_count > 5 and rel.trust > 50:
            return f"交往颇多，关系不错"
        return ""
