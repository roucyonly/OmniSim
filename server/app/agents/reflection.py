from dataclasses import dataclass

from .memory import MemoryStream, MemoryEntry


@dataclass
class ReflectionResult:
    content: str
    tick: int


REFLECTION_INTERVAL = 6  # 每6 tick反思一次


class Reflector:
    def should_reflect(self, tick: int) -> bool:
        return tick > 0 and tick % REFLECTION_INTERVAL == 0

    def reflect(self, memories: MemoryStream, current_tick: int) -> ReflectionResult | None:
        recent = memories.recent(10)
        if not recent:
            return None

        summary = self._summarize(recent, current_tick)
        return ReflectionResult(content=summary, tick=current_tick)

    def _summarize(self, memories: list[MemoryEntry], current_tick: int) -> str:
        action_counts: dict[str, int] = {}
        for m in memories:
            action_counts[m.description] = action_counts.get(m.description, 0) + 1

        frequent = [desc for desc, count in action_counts.items() if count >= 2]
        if frequent:
            activities = "、".join(frequent[:3])
            return f"最近经常{activities}，感觉有些心得。"

        last = memories[-1]
        return f"最近经历了{last.description}。"
