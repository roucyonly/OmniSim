import uuid

from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models.base import init_db, get_db
from .models.world import World
from .models.location import Location
from .models.agent import Agent
from .schemas.world import WorldCreate, WorldState, LocationOut, AgentOut, TickResultOut
from .simulation.time_system import SHICHEN_NAMES
from .simulation.engine import SimulationEngine

app = FastAPI(title="OmniSim")

engines: dict[str, SimulationEngine] = {}


@app.on_event("startup")
async def startup():
    await init_db()


# ─── World CRUD ───

@app.post("/api/worlds", response_model=WorldState)
async def create_world(body: WorldCreate, db: AsyncSession = Depends(get_db)):
    world_id = uuid.uuid4().hex[:12]
    world = World(
        id=world_id,
        name=body.name,
        grid_size=body.grid_size,
        theme=body.theme,
    )
    db.add(world)
    await db.commit()
    await db.refresh(world)

    engines[world_id] = SimulationEngine()

    return _world_to_state(world)


@app.get("/api/worlds/{world_id}", response_model=WorldState)
async def get_world(world_id: str, db: AsyncSession = Depends(get_db)):
    world = await _get_world_or_404(db, world_id)
    return _world_to_state(world)


@app.get("/api/worlds", response_model=list[WorldState])
async def list_worlds(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(World))
    worlds = result.scalars().all()
    return [_world_to_state(w) for w in worlds]


# ─── Locations ───

@app.get("/api/worlds/{world_id}/locations", response_model=list[LocationOut])
async def list_locations(world_id: str, db: AsyncSession = Depends(get_db)):
    await _get_world_or_404(db, world_id)
    result = await db.execute(
        select(Location).where(Location.world_id == world_id)
    )
    return result.scalars().all()


# ─── Agents ───

@app.get("/api/worlds/{world_id}/agents", response_model=list[AgentOut])
async def list_agents(world_id: str, db: AsyncSession = Depends(get_db)):
    await _get_world_or_404(db, world_id)
    result = await db.execute(
        select(Agent).where(Agent.world_id == world_id)
    )
    return result.scalars().all()


# ─── Simulation Control ───

@app.post("/api/worlds/{world_id}/tick", response_model=TickResultOut)
async def manual_tick(world_id: str, db: AsyncSession = Depends(get_db)):
    world = await _get_world_or_404(db, world_id)

    engine = engines.get(world_id)
    if not engine:
        engine = SimulationEngine(world.current_tick, world.current_day)
        engines[world_id] = engine

    result = await db.execute(
        select(Agent).where(Agent.world_id == world_id)
    )
    agents = result.scalars().all()
    agent_dicts = [
        {"id": a.id, "name": a.name, "x": a.x, "y": a.y, "status": a.status}
        for a in agents
    ]

    tick_result = engine.tick(agent_dicts)

    world.current_tick = tick_result.tick
    world.current_day = tick_result.day
    await db.commit()

    agent_updates = []
    for u in tick_result.agent_updates:
        agent_updates.append(AgentOut(
            id=u.agent_id,
            world_id=world_id,
            name=u.name,
            tier=0,
            x=u.x,
            y=u.y,
            status=u.status,
            personality="",
            role="",
            energy=100,
            hp=100,
            speed=2.0,
            action_desc=u.action_desc,
        ))

    return TickResultOut(
        tick=tick_result.tick,
        day=tick_result.day,
        time_of_day=tick_result.time_of_day,
        period=tick_result.period,
        agent_updates=agent_updates,
    )


# ─── Health ───

@app.get("/api/health")
async def health():
    return {"status": "ok"}


# ─── Helpers ───

async def _get_world_or_404(db: AsyncSession, world_id: str) -> World:
    world = await db.get(World, world_id)
    if not world:
        raise HTTPException(status_code=404, detail="World not found")
    return world


def _world_to_state(world: World) -> WorldState:
    tick = world.current_tick
    return WorldState(
        id=world.id,
        name=world.name,
        grid_size=world.grid_size,
        current_tick=tick,
        current_day=world.current_day,
        status=world.status,
        theme=world.theme,
        time_of_day=SHICHEN_NAMES[tick],
    )
