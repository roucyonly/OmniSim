from dataclasses import dataclass, field

from .memory import MemoryStream
from .planner import Planner, PlanAction
from .reflection import Reflector, ReflectionResult
from .decision import DecisionRouter, Decision
from ..core.dice import roll, RollResult


# 骰子判定配置: action -> {attribute字段名, penalty难度惩罚}
DICE_ACTIONS: dict[str, dict] = {
    "练功": {"attribute": "talent", "penalty": 0},
    "起床练剑": {"attribute": "talent", "penalty": 5},
    "练剑": {"attribute": "sword_skill", "penalty": 0},
    "切磋": {"attribute": "sword_skill", "penalty": 10},
    "修炼": {"attribute": "wisdom", "penalty": 15},
    "修炼内功": {"attribute": "wisdom", "penalty": 25},
    "早课": {"attribute": "wisdom", "penalty": 0},
    "授徒": {"attribute": "sword_skill", "penalty": 5},
    "指导弟子": {"attribute": "sword_skill", "penalty": 5},
}

# 骰子结果叙事后缀
DICE_NARRATION: dict[str, str] = {
    "大成功": "，如有神助，状态极佳！",
    "成功": "，颇有收获。",
    "勉强": "，勉强完成。",
    "失败": "，心不在焉，效果不佳。",
    "大失败": "，出了岔子，受了点伤！",
}

# 骰子效果
DICE_EFFECTS: dict[str, dict] = {
    "大成功": {"energy": -5, "sword_skill": 1},
    "成功": {"energy": -3},
    "勉强": {"energy": -5},
    "失败": {"energy": -8},
    "大失败": {"energy": -10, "health": -5},
}

# 动作→状态映射
ACTION_STATUS_MAP: dict[str, str] = {
    "睡觉": "sleeping",
    "午饭": "eating",
    "晚饭": "eating",
    "练功": "practicing",
    "起床练剑": "practicing",
    "练剑": "practicing",
    "切磋": "practicing",
    "修炼": "practicing",
    "修炼内功": "practicing",
}


@dataclass
class AgentState:
    id: str
    name: str
    tier: int
    faction: str = ""
    role: str = ""
    template: str = ""
    x: int = 0
    y: int = 0
    location_name: str = ""
    status: str = "idle"
    personality: str = ""
    core_motivation: str = ""
    initial_memory: str = ""

    # YAML 维度
    health: int = 100
    inner_power: int = 50
    sword_skill: int = 50

    # 骰子维度
    talent: int = 50
    wisdom: int = 50
    charisma: int = 50
    perception: int = 50
    luck: int = 50

    energy: int = 100
    hunger: int = 0
    speed: float = 2.0
    last_action_desc: str = ""


@dataclass
class StepResult:
    agent_id: str
    name: str
    x: int
    y: int
    status: str
    action_desc: str
    memories_written: list[str] = field(default_factory=list)
    reflection: str | None = None
    dice_result: RollResult | None = None


class AgentBase:
    def __init__(self, state: AgentState):
        self.state = state
        self.memory = MemoryStream()
        self.planner = Planner()
        self.reflector = Reflector()
        self.router = DecisionRouter()

        self.plan: list[PlanAction] = []
        self.reflections: list[ReflectionResult] = []
        self._plan_initialized = False

        if state.initial_memory:
            self.memory.write(state.initial_memory, 8, 0)

    def init_daily_plan(self):
        self.plan = self.planner.generate_plan(self.state.template, self.state.name)
        self._plan_initialized = True

    def step(self, tick: int, nearby_agents: list["AgentBase"] | None = None) -> StepResult:
        if not self._plan_initialized:
            self.init_daily_plan()

        action = self.planner.get_action_for_tick(self.plan, tick)
        if action is None:
            action = PlanAction(tick=tick, action="无所事事")

        # 决策路由
        involves_other = action.target_id is not None
        decision = self.router.route(action.action, self.state.tier, involves_other)

        # 执行
        self.state.status = ACTION_STATUS_MAP.get(action.action, "idle")
        if action.location:
            self.state.location_name = action.location

        # 骰子判定
        dice_result = None
        if self.state.tier <= 2 and action.action in DICE_ACTIONS:
            dice_result = self._roll_for_action(action.action, nearby_agents)

        # 记忆
        desc = self._describe_action(action, nearby_agents, dice_result)
        importance = self._estimate_importance(action, decision, dice_result)
        self.memory.write(desc, importance, tick)

        # 骰子结果影响状态
        if dice_result:
            self._apply_dice_effect(dice_result)

        # 反思
        reflection_text = None
        if self.reflector.should_reflect(tick):
            result = self.reflector.reflect(self.memory, tick)
            if result:
                self.reflections.append(result)
                reflection_text = result.content
                self.memory.write(f"反思：{result.content}", 7, tick)

        self.state.last_action_desc = desc

        return StepResult(
            agent_id=self.state.id,
            name=self.state.name,
            x=self.state.x,
            y=self.state.y,
            status=self.state.status,
            action_desc=desc,
            dice_result=dice_result,
            reflection=reflection_text
        )

    def _roll_for_action(self, action: str, nearby: list["AgentBase"] | None) -> RollResult:
        config = DICE_ACTIONS[action]
        attr_name = config["attribute"]
        attribute_value = getattr(self.state, attr_name, 50)
        penalty = config["penalty"]

        bonus = 0.0
        if nearby:
            bonus += 5
        if self.state.energy < 30:
            bonus -= 10
        if self.state.inner_power > 70:
            bonus += 5

        return roll(attribute_value, penalty, bonus)

    def _apply_dice_effect(self, dice: RollResult):
        effects = DICE_EFFECTS.get(dice.degree, {})
        for attr, delta in effects.items():
            cur = getattr(self.state, attr, 0)
            if delta > 0:
                setattr(self.state, attr, min(100, cur + delta))
            else:
                setattr(self.state, attr, max(0, cur + delta))

    def _describe_action(self, action: PlanAction, nearby: list["AgentBase"] | None, dice: RollResult | None) -> str:
        loc = f"在{action.location}" if action.location else f"在{self.state.location_name}" if self.state.location_name else "在附近"
        desc = f"{loc}{action.action}"

        if nearby:
            names = [a.state.name for a in nearby[:3]]
            if names:
                desc += f"，与{'、'.join(names)}在一起"

        if dice and dice.degree in DICE_NARRATION:
            desc += DICE_NARRATION[dice.degree]

        return desc

    def _estimate_importance(self, action: PlanAction, decision: Decision, dice: RollResult | None = None) -> int:
        base = 3
        if decision.needs_llm:
            base += 2
        if action.priority >= 7:
            base += 2
        if dice and dice.degree in ("大成功", "大失败"):
            base += 3
        elif dice and dice.degree == "成功":
            base += 1
        return min(base, 10)