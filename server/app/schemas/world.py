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
    faction: str = ""
    role: str = ""
    template: str = ""
    x: int
    y: int
    location_name: str = ""
    status: str = ""
    personality: str = ""
    core_motivation: str = ""
    initial_memory: str = ""
    health: int = 100
    inner_power: int = 50
    sword_skill: int = 50
    talent: int = 50
    wisdom: int = 50
    charisma: int = 50
    perception: int = 50
    luck: int = 50
    energy: int = 100
    speed: float = 2.0
    action_desc: str = ""
    emotion: str = "平静"


class TickResultOut(BaseModel):
    tick: int
    day: int
    time_of_day: str
    period: str
    agent_updates: list[AgentOut]
