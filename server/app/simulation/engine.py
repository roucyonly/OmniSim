from dataclasses import dataclass, field

from .time_system import TimeSystem


@dataclass
class AgentUpdate:
    agent_id: str
    name: str
    x: int
    y: int
    status: str
    action_desc: str = ""


@dataclass
class TickResult:
    tick: int
    day: int
    time_of_day: str
    period: str
    agent_updates: list[AgentUpdate] = field(default_factory=list)
    events: list[str] = field(default_factory=list)


class SimulationEngine:
    def __init__(self, current_tick: int = 0, current_day: int = 1):
        self.time_system = TimeSystem(current_tick, current_day)
        self.agent_actions: dict[str, str] = {}  # agent_id -> action stub

    def tick(self, agents: list[dict]) -> TickResult:
        day, tick = self.time_system.advance()

        updates = []
        for agent in agents:
            action_desc = self._decide_action(agent)
            updates.append(AgentUpdate(
                agent_id=agent["id"],
                name=agent["name"],
                x=agent["x"],
                y=agent["y"],
                status=agent["status"],
                action_desc=action_desc,
            ))

        return TickResult(
            tick=tick,
            day=day,
            time_of_day=self.time_system.time_of_day,
            period=self.time_system.period,
            agent_updates=updates,
        )

    def _decide_action(self, agent: dict) -> str:
        period = self.time_system.period
        status = agent.get("status", "idle")

        if status == "sleeping":
            return "正在睡觉"
        if period in ("深夜", "凌晨") and status == "idle":
            return "正在睡觉"
        if period == "上午":
            return "在附近活动"
        if period == "中午":
            return "正在吃午饭"
        if period in ("下午",):
            return "正在练功"
        if period == "傍晚":
            return "正在吃晚饭"
        if period == "夜间":
            return "在休息"
        return "无所事事"
