from pydantic import BaseModel


class WorldCreate(BaseModel):
    name: str = "未命名世界"
    grid_size: int = 16
    theme: str = "custom"


class WorldState(BaseModel):
    id: str
    name: str
    grid_size: int
    current_tick: int
    current_day: int
    status: str
    theme: str
    time_of_day: str = ""
    period: str = ""


class LocationOut(BaseModel):
    id: str
    world_id: str
    x: int
    y: int
    terrain: str
    name: str | None
    building_type: str | None


class AgentOut(BaseModel):
    id: str
    world_id: str
    name: str
    tier: int
    x: int
    y: int
    status: str
    personality: str
    role: str
    energy: int
    hp: int
    speed: float
    action_desc: str = ""


class TickResultOut(BaseModel):
    tick: int
    day: int
    time_of_day: str
    period: str
    agent_updates: list[AgentOut]
