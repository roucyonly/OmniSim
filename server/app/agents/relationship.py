from dataclasses import dataclass, field


# 骰子结果 → 关系变化映射
DICE_RELATIONSHIP_MAP: dict[str, dict[str, float]] = {
    "大成功": {"trust": 5, "intimacy": 5},
    "成功":  {"trust": 2, "intimacy": 2},
    "失败":  {"trust": -2, "intimacy": -1},
    "大失败": {"trust": -5, "intimacy": -3},
}


@dataclass
class Relationship:
    target_id: str
    target_name: str
    relation_type: str = "陌生人"       # 师徒/同门/恋人/敌对/陌生人
    trust: float = 0.0                 # [-100, 100]
    intimacy: float = 0.0              # [0, 100]
    impression: str = ""               # 一句话印象
    last_interaction_tick: int = 0
    interaction_count: int = 0

    def update(self, trust_delta: float = 0, intimacy_delta: float = 0):
        self.trust = max(-100, min(100, self.trust + trust_delta))
        self.intimacy = max(0, min(100, self.intimacy + intimacy_delta))

    def record_interaction(self, tick: int):
        self.last_interaction_tick = tick
        self.interaction_count += 1

    def decay_intimacy(self, current_tick: int, threshold: int = 12):
        if current_tick - self.last_interaction_tick >= threshold:
            self.intimacy = max(0, self.intimacy - 1)
