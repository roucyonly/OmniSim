from dataclasses import dataclass, field

from .time_system import TimeSystem
from ..agents.base import AgentBase, AgentState, StepResult
from ..agents.planner import Planner, PlanAction


class SimulationEngine:
    def __init__(self, current_tick: int = 0, current_day: int = 1):
        self.time_system = TimeSystem(current_tick, current_day)
        self.agents: dict[str, AgentBase] = {}

    def add_agent(self, state: AgentState):
        self.agents[state.id] = AgentBase(state)

    def tick(self) -> list[StepResult]:
        day, tick = self.time_system.advance()

        if tick == 0:
            for agent in self.agents.values():
                agent.init_daily_plan()

        agent_list = list(self.agents.values())
        planner = Planner()

        # 确保所有 agent 都已初始化日程
        for agent in agent_list:
            if not agent._plan_initialized:
                agent.init_daily_plan()

        # Pass 1: 先统一更新所有 agent 的 location_name，避免顺序处理导致 nearby 不一致
        for agent in agent_list:
            action = planner.get_action_for_tick(agent.plan, tick)
            if action and action.location:
                agent.state.location_name = action.location

        # Pass 2: 基于统一的 location 判定 nearby，再执行 step
        results = []
        for agent in agent_list:
            loc = agent.state.location_name
            nearby = [
                a for a in agent_list
                if a.state.id != agent.state.id
                and loc and a.state.location_name == loc
            ]
            result = agent.step(tick, nearby)
            results.append(result)

        return results
