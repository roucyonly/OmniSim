from __future__ import annotations

from dataclasses import dataclass, field

from .memory import MemoryStream
from .emotion import EmotionalState
from .relationship import Relationship, DICE_RELATIONSHIP_MAP
from .planner import Planner, PlanAction
from .reflection import Reflector, ReflectionResult
from .decision import DecisionRouter, Decision
from ..core.dice import roll, RollResult


# ── 配置表 ──────────────────────────────────────────────────────────────────

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

DICE_NARRATION: dict[str, str] = {
    "大成功": "，如有神助，状态极佳！",
    "成功": "，颇有收获。",
    "失败": "，心不在焉，效果不佳。",
    "大失败": "，出了岔子，受了点伤！",
}

DICE_EFFECTS: dict[str, dict] = {
    "大成功": {"energy": -5, "sword_skill": 1},
    "成功": {"energy": -3},
    "失败": {"energy": -8},
    "大失败": {"energy": -10, "health": -5},
}

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
    "打招呼": "socializing",
    "闲聊": "socializing",
}

FREE_TIME_TICKS = {6, 9}  # 午时、酉时 = 自由活动


# ── 数据类 ──────────────────────────────────────────────────────────────────

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
    personality_vector: dict = field(default_factory=dict)

    # 数值属性
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
    emotion: str = "平静"
    memories_written: list[str] = field(default_factory=list)
    reflection: str | None = None
    dice_result: RollResult | None = None


# ── Agent 核心 ─────────────────────────────────────────────────────────────

class AgentBase:
    def __init__(
        self,
        state: AgentState,
        initial_relationships: list[dict] | None = None,
    ):
        self.state = state
        self.memory = MemoryStream()
        self.emotion = EmotionalState()
        self.relationships: dict[str, Relationship] = {}
        self.planner = Planner()
        self.reflector = Reflector()
        self.router = DecisionRouter()

        self.plan: list[PlanAction] = []
        self.reflections: list[ReflectionResult] = []
        self._plan_initialized = False
        self._nearby_cache: list[AgentBase] = []

        # 初始化关系
        if initial_relationships:
            for r in initial_relationships:
                tid = r.get("target_id") or r["target"]
                self.relationships[tid] = Relationship(
                    target_id=tid,
                    target_name=r.get("target_name", tid),
                    relation_type=r.get("relation_type", r.get("type", "陌生人")),
                    trust=r.get("trust", 0),
                    intimacy=r.get("intimacy", 0),
                )

        # 初始记忆
        if state.initial_memory:
            self.memory.write(state.initial_memory, 8, 0, location=state.location_name)

    # ── 属性便捷访问 ────────────────────────────────────────────────────

    @property
    def pv(self) -> dict:
        """personality_vector 快捷访问"""
        return self.state.personality_vector

    def _pv(self, key: str, default: float = 0.5) -> float:
        return self.pv.get(key, default)

    # ── 每日计划 ────────────────────────────────────────────────────────

    def init_daily_plan(self):
        self.plan = self.planner.generate_plan(
            self.state.template,
            self.state.name,
            emotion_valence=self.emotion.valence,
        )
        self._plan_initialized = True

    # ── 核心 step ──────────────────────────────────────────────────────

    def step(self, tick: int, nearby_agents: list[AgentBase] | None = None) -> StepResult:
        if not self._plan_initialized:
            self.init_daily_plan()

        self._nearby_cache = nearby_agents or []

        # 1. 情感衰减
        decay_rate = 0.1 * (1.5 - self._pv("stability", 0.5))
        self.emotion.decay(rate=max(0.02, decay_rate))

        # 2. 获取计划
        action = self.planner.get_action_for_tick(self.plan, tick)
        if action is None:
            action = PlanAction(tick=tick, action="无所事事")

        # 3. 主动行为判定（自由时间）
        if tick in FREE_TIME_TICKS and nearby_agents:
            proactive = self._check_proactive_intent(nearby_agents, tick)
            if proactive:
                action = proactive

        # 4. 决策路由
        involves_other = action.target_id is not None
        decision = self.router.route(action.action, self.state.tier, involves_other)

        # 5. 执行
        self.state.status = ACTION_STATUS_MAP.get(action.action, "idle")
        if action.location:
            self.state.location_name = action.location

        # 6. 骰子判定
        dice_result = None
        if self.state.tier <= 2 and action.action in DICE_ACTIONS:
            dice_result = self._roll_for_action(action.action, nearby_agents)
            self.emotion.apply_dice(dice_result.degree, tick)
            if nearby_agents:
                self._apply_dice_relationship(dice_result, nearby_agents, tick)

        # 7. 写入增强记忆
        desc = self._describe_action(action, nearby_agents, dice_result)
        importance = self._estimate_importance(action, decision, dice_result)
        involved = [a.state.id for a in (nearby_agents or [])]
        self.memory.write(
            desc, importance, tick,
            emotion=self.emotion.dominant_emotion,
            involved_agents=involved,
            location=self.state.location_name,
        )

        # 8. 骰子效果
        if dice_result:
            self._apply_dice_effect(dice_result)

        # 9. 关系互动记录
        if nearby_agents:
            for other in nearby_agents:
                rel = self.relationships.get(other.state.id)
                if rel:
                    rel.record_interaction(tick)

        # 10. 反思
        reflection_text = None
        if self.reflector.should_reflect(tick):
            result = self.reflector.reflect(
                self.memory, tick,
                relationships=self.relationships,
            )
            if result:
                self.reflections.append(result)
                reflection_text = result.content
                self.memory.write(
                    f"反思：{result.content}", 7, tick,
                    emotion=self.emotion.dominant_emotion,
                    location=self.state.location_name,
                )

        self.state.last_action_desc = desc

        return StepResult(
            agent_id=self.state.id,
            name=self.state.name,
            x=self.state.x,
            y=self.state.y,
            status=self.state.status,
            action_desc=desc,
            emotion=self.emotion.dominant_emotion,
            dice_result=dice_result,
            reflection=reflection_text,
        )

    # ── 主动行为 ───────────────────────────────────────────────────────

    def _check_proactive_intent(self, nearby: list[AgentBase], tick: int) -> PlanAction | None:
        extraversion = self._pv("extraversion", 0.5)

        for other in nearby:
            rel = self.relationships.get(other.state.id)
            if not rel:
                # 陌生人：高外向 + 心情好 → 打招呼
                if extraversion > 0.7 and self.emotion.valence > 0:
                    return PlanAction(
                        tick=tick, action="打招呼",
                        target_id=other.state.id,
                        location=self.state.location_name,
                        priority=3,
                    )
                continue

            # 熟人
            if rel.intimacy > 60 and self.emotion.valence > 0.3:
                return PlanAction(
                    tick=tick, action="闲聊",
                    target_id=other.state.id,
                    location=self.state.location_name,
                    priority=4,
                )
            if rel.intimacy > 40 and extraversion > 0.6:
                return PlanAction(
                    tick=tick, action="打招呼",
                    target_id=other.state.id,
                    location=self.state.location_name,
                    priority=3,
                )

        return None

    # ── 骰子 ───────────────────────────────────────────────────────────

    def _roll_for_action(self, action: str, nearby: list[AgentBase] | None) -> RollResult:
        config = DICE_ACTIONS[action]
        attr_name = config["attribute"]
        attribute_value = getattr(self.state, attr_name, 50)
        penalty = config["penalty"]

        bonus = self.emotion.bonus_for_dice()

        if nearby:
            best_rel = max(
                (self.relationships.get(a.state.id) for a in nearby),
                key=lambda r: r.trust if r else 0,
                default=None,
            )
            if best_rel and best_rel.trust > 50:
                bonus += 3

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

    def _apply_dice_relationship(
        self, dice: RollResult, nearby: list[AgentBase], tick: int,
    ):
        deltas = DICE_RELATIONSHIP_MAP.get(dice.degree)
        if not deltas:
            return
        for other in nearby:
            rel = self.relationships.get(other.state.id)
            if rel:
                rel.update(**deltas)
                rel.record_interaction(tick)

    # ── 辅助 ───────────────────────────────────────────────────────────

    def _describe_action(self, action: PlanAction, nearby: list[AgentBase] | None,
                         dice: RollResult | None) -> str:
        loc = (f"在{action.location}" if action.location
               else f"在{self.state.location_name}" if self.state.location_name
               else "在附近")
        desc = f"{loc}{action.action}"

        if action.target_id and nearby:
            target = next((a for a in nearby if a.state.id == action.target_id), None)
            if target:
                desc += f"，主动找{target.state.name}"

        if nearby and not action.target_id:
            names = [a.state.name for a in nearby[:3]]
            if names:
                desc += f"，与{'、'.join(names)}在一起"

        if dice and dice.degree in DICE_NARRATION:
            desc += DICE_NARRATION[dice.degree]

        return desc

    def _estimate_importance(self, action: PlanAction, decision: Decision,
                             dice: RollResult | None = None) -> int:
        base = 3
        if decision.needs_llm:
            base += 2
        if action.priority >= 7:
            base += 2
        if action.target_id:
            base += 1
        if dice and dice.degree in ("大成功", "大失败"):
            base += 3
        elif dice and dice.degree == "成功":
            base += 1
        return min(base, 10)
