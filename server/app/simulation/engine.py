from dataclasses import dataclass, field

from .time_system import TimeSystem
from ..agents.base import AgentBase, AgentState, StepResult
from ..agents.planner import Planner, PlanAction
from ..agents.relationship import Relationship


class SimulationEngine:
    def __init__(self, current_tick: int = 0, current_day: int = 1):
        self.time_system = TimeSystem(current_tick, current_day)
        self.agents: dict[str, AgentBase] = {}

    def add_agent(
        self,
        state: AgentState,
        initial_relationships: list[dict] | None = None,
    ):
        self.agents[state.id] = AgentBase(state, initial_relationships)

    def tick(self) -> list[StepResult]:
        day, tick = self.time_system.advance()

        is_new_day = tick == 0

        if is_new_day:
            for agent in self.agents.values():
                agent.init_daily_plan()
            # 每天衰减关系亲密度
            self._decay_relationships()

        agent_list = list(self.agents.values())
        planner = Planner()

        for agent in agent_list:
            if not agent._plan_initialized:
                agent.init_daily_plan()

        # Pass 1: 统一更新 location_name
        for agent in agent_list:
            action = planner.get_action_for_tick(agent.plan, tick)
            if action and action.location:
                agent.state.location_name = action.location

        # Pass 2: 基于 location 判定 nearby，执行 step
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

    def _decay_relationships(self):
        current_tick = self.time_system.current_tick
        for agent in self.agents.values():
            for rel in agent.relationships.values():
                rel.decay_intimacy(current_tick, threshold=12)
