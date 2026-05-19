from dataclasses import dataclass

# 不需要 LLM 的日常动作
ROUTINE_ACTIONS = {"睡觉", "吃饭", "午饭", "晚饭", "休息", "巡逻", "自由活动"}


@dataclass
class Decision:
    action: str
    needs_llm: bool
    reason: str = ""


class DecisionRouter:
    def route(self, action: str, tier: int, involves_other: bool = False) -> Decision:
        if action in ROUTINE_ACTIONS:
            return Decision(action=action, needs_llm=False, reason="日常行为")

        if tier >= 2 and involves_other:
            return Decision(action=action, needs_llm=True, reason="涉及其他角色，需要LLM")

        if tier == 1:
            return Decision(action=action, needs_llm=True, reason="T1角色复杂决策")

        return Decision(action=action, needs_llm=False, reason="低级角色走规则引擎")
