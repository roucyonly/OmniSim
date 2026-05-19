import json
import uuid
from contextlib import asynccontextmanager

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
from .agents.base import AgentState

engines: dict[str, SimulationEngine] = {}

AGENT_FIELDS = [
    "faction", "role", "template", "x", "y", "location_name",
    "personality", "core_motivation", "initial_memory", "personality_vector",
    "health", "inner_power", "sword_skill",
    "talent", "wisdom", "charisma", "perception", "luck",
    "energy", "hunger", "speed",
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="OmniSim", lifespan=lifespan)


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

@app.post("/api/worlds/{world_id}/agents", response_model=AgentOut)
async def create_agent(
    world_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    await _get_world_or_404(db, world_id)

    agent_id = uuid.uuid4().hex[:12]
    kwargs = {
        "id": agent_id,
        "world_id": world_id,
        "name": body.get("name", ""),
        "tier": body.get("tier", 2),
    }
    for f in AGENT_FIELDS:
        if f in body:
            kwargs[f] = body[f]

    agent = Agent(**kwargs)
    # personality_vector 存为 JSON 字符串
    pv = body.get("personality_vector")
    if pv and isinstance(pv, dict):
        agent.personality_vector = json.dumps(pv, ensure_ascii=False)
    db.add(agent)
    await db.commit()
    await db.refresh(agent)

    engine = _get_engine(world_id, None)
    state_kwargs = {"id": agent.id, "name": agent.name, "tier": agent.tier}
    for f in AGENT_FIELDS:
        val = getattr(agent, f, None)
        if val is not None:
            if f == "personality_vector" and isinstance(val, str) and val:
                state_kwargs[f] = json.loads(val)
            else:
                state_kwargs[f] = val
    if "template" not in state_kwargs:
        state_kwargs["template"] = body.get("template", "")
    if "initial_memory" in body:
        state_kwargs["initial_memory"] = body["initial_memory"]
    if not state_kwargs.get("personality_vector"):
        state_kwargs["personality_vector"] = body.get("personality_vector", {})

    initial_rels = body.get("initial_relationships")
    engine.add_agent(AgentState(**state_kwargs), initial_relationships=initial_rels)

    return _agent_to_out(agent, world_id)


@app.get("/api/worlds/{world_id}/agents", response_model=list[AgentOut])
async def list_agents(world_id: str, db: AsyncSession = Depends(get_db)):
    await _get_world_or_404(db, world_id)
    result = await db.execute(
        select(Agent).where(Agent.world_id == world_id)
    )
    return [_agent_to_out(a, world_id) for a in result.scalars().all()]


@app.get("/api/worlds/{world_id}/agents/{agent_id}", response_model=AgentOut)
async def get_agent(world_id: str, agent_id: str, db: AsyncSession = Depends(get_db)):
    await _get_world_or_404(db, world_id)
    agent = await db.get(Agent, agent_id)
    if not agent or agent.world_id != world_id:
        raise HTTPException(status_code=404, detail="Agent not found")
    return _agent_to_out(agent, world_id)


@app.patch("/api/worlds/{world_id}/agents/{agent_id}", response_model=AgentOut)
async def update_agent(
    world_id: str,
    agent_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    await _get_world_or_404(db, world_id)
    agent = await db.get(Agent, agent_id)
    if not agent or agent.world_id != world_id:
        raise HTTPException(status_code=404, detail="Agent not found")

    for f in AGENT_FIELDS:
        if f in body:
            setattr(agent, f, body[f])
    await db.commit()
    await db.refresh(agent)

    # 同步到内存引擎
    engine = _get_engine(world_id, None)
    if agent_id in engine.agents:
        ag = engine.agents[agent_id]
        for f in AGENT_FIELDS:
            if f in body:
                setattr(ag.state, f, body[f])

    return _agent_to_out(agent, world_id)


@app.delete("/api/worlds/{world_id}/agents/{agent_id}")
async def delete_agent(world_id: str, agent_id: str, db: AsyncSession = Depends(get_db)):
    await _get_world_or_404(db, world_id)
    agent = await db.get(Agent, agent_id)
    if not agent or agent.world_id != world_id:
        raise HTTPException(status_code=404, detail="Agent not found")

    await db.delete(agent)
    await db.commit()

    engine = _get_engine(world_id, None)
    engine.agents.pop(agent_id, None)

    return {"detail": "deleted"}


@app.delete("/api/worlds/{world_id}/agents")
async def delete_all_agents(world_id: str, db: AsyncSession = Depends(get_db)):
    await _get_world_or_404(db, world_id)
    result = await db.execute(
        select(Agent).where(Agent.world_id == world_id)
    )
    count = 0
    for a in result.scalars().all():
        await db.delete(a)
        count += 1
    await db.commit()

    engine = _get_engine(world_id, None)
    engine.agents.clear()

    return {"detail": f"deleted {count} agents"}


# ─── Simulation Control ───

@app.get("/api/worlds/{world_id}/tick", response_model=TickResultOut)
async def get_current_tick(world_id: str, db: AsyncSession = Depends(get_db)):
    world = await _get_world_or_404(db, world_id)
    engine = _get_engine(world_id, world)

    # 恢复 agent（重启后）
    if not engine.agents:
        result = await db.execute(
            select(Agent).where(Agent.world_id == world_id)
        )
        for a in result.scalars().all():
            state_kwargs = {"id": a.id, "name": a.name, "tier": a.tier}
            for f in AGENT_FIELDS:
                val = getattr(a, f, None)
                if val is not None:
                    if f == "personality_vector" and isinstance(val, str) and val:
                        state_kwargs[f] = json.loads(val)
                    else:
                        state_kwargs[f] = val
            engine.add_agent(AgentState(**state_kwargs))

    agent_list = []
    for ag in engine.agents.values():
        agent_list.append(AgentOut(
            id=ag.state.id,
            world_id=world_id,
            name=ag.state.name,
            tier=ag.state.tier,
            faction=ag.state.faction,
            role=ag.state.role,
            template=ag.state.template,
            x=ag.state.x,
            y=ag.state.y,
            location_name=ag.state.location_name,
            status=ag.state.status,
            personality=ag.state.personality,
            core_motivation=ag.state.core_motivation,
            initial_memory=ag.state.initial_memory,
            health=ag.state.health,
            inner_power=ag.state.inner_power,
            sword_skill=ag.state.sword_skill,
            talent=ag.state.talent,
            wisdom=ag.state.wisdom,
            charisma=ag.state.charisma,
            perception=ag.state.perception,
            luck=ag.state.luck,
            energy=ag.state.energy,
            speed=ag.state.speed,
            action_desc=ag.state.last_action_desc,
            emotion=ag.emotion.dominant_emotion,
        ))

    return TickResultOut(
        tick=engine.time_system.current_tick,
        day=engine.time_system.current_day,
        time_of_day=engine.time_system.time_of_day,
        period=engine.time_system.period,
        status=world.status,
        agent_updates=agent_list,
    )


@app.post("/api/worlds/{world_id}/tick", response_model=TickResultOut)
async def manual_tick(world_id: str, db: AsyncSession = Depends(get_db)):
    world = await _get_world_or_404(db, world_id)

    engine = _get_engine(world_id, world)

    if not engine.agents:
        result = await db.execute(
            select(Agent).where(Agent.world_id == world_id)
        )
        for a in result.scalars().all():
            state_kwargs = {"id": a.id, "name": a.name, "tier": a.tier}
            for f in AGENT_FIELDS:
                val = getattr(a, f, None)
                if val is not None:
                    if f == "personality_vector" and isinstance(val, str) and val:
                        state_kwargs[f] = json.loads(val)
                    else:
                        state_kwargs[f] = val
            engine.add_agent(AgentState(**state_kwargs))

    step_results = engine.tick()

    world.current_tick = engine.time_system.current_tick
    world.current_day = engine.time_system.current_day
    await db.commit()

    agent_updates = []
    for r in step_results:
        ag = engine.agents.get(r.agent_id)
        agent_updates.append(AgentOut(
            id=r.agent_id,
            world_id=world_id,
            name=r.name,
            tier=ag.state.tier if ag else 0,
            faction=ag.state.faction if ag else "",
            role=ag.state.role if ag else "",
            template=ag.state.template if ag else "",
            x=r.x,
            y=r.y,
            location_name=ag.state.location_name if ag else "",
            status=r.status,
            personality=ag.state.personality if ag else "",
            core_motivation=ag.state.core_motivation if ag else "",
            initial_memory=ag.state.initial_memory if ag else "",
            health=ag.state.health if ag else 100,
            inner_power=ag.state.inner_power if ag else 50,
            sword_skill=ag.state.sword_skill if ag else 50,
            talent=ag.state.talent if ag else 50,
            wisdom=ag.state.wisdom if ag else 50,
            charisma=ag.state.charisma if ag else 50,
            perception=ag.state.perception if ag else 50,
            luck=ag.state.luck if ag else 50,
            energy=ag.state.energy if ag else 100,
            speed=ag.state.speed if ag else 2.0,
            action_desc=r.action_desc,
            emotion=r.emotion if hasattr(r, "emotion") else "平静",
        ))

    return TickResultOut(
        tick=engine.time_system.current_tick,
        day=engine.time_system.current_day,
        time_of_day=engine.time_system.time_of_day,
        period=engine.time_system.period,
        agent_updates=agent_updates,
    )


# ─── Agent Memory ───

@app.get("/api/worlds/{world_id}/agents/{agent_id}/memories")
async def get_agent_memories(world_id: str, agent_id: str):
    engine = _get_engine(world_id)
    agent = engine.agents.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found in engine")

    return [
        {
            "id": m.id,
            "tick": m.tick,
            "description": m.description,
            "importance": m.importance,
            "emotion_tag": m.emotion_tag,
            "involved_agents": m.involved_agents,
            "location": m.location,
            "gossip_worthy": m.gossip_worthy,
        }
        for m in agent.memory.entries
    ]


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


def _get_engine(world_id: str, world: World | None = None) -> SimulationEngine:
    if world_id not in engines:
        tick = world.current_tick if world else 0
        day = world.current_day if world else 1
        engines[world_id] = SimulationEngine(current_tick=tick, current_day=day)
    return engines[world_id]


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


def _agent_to_out(agent: Agent, world_id: str) -> AgentOut:
    return AgentOut(
        id=agent.id,
        world_id=world_id,
        name=agent.name,
        tier=agent.tier,
        faction=agent.faction,
        role=agent.role,
        template=agent.template,
        x=agent.x,
        y=agent.y,
        location_name=agent.location_name,
        status=agent.status,
        personality=agent.personality,
        core_motivation=agent.core_motivation,
        initial_memory=agent.initial_memory,
        health=agent.health,
        inner_power=agent.inner_power,
        sword_skill=agent.sword_skill,
        talent=agent.talent,
        wisdom=agent.wisdom,
        charisma=agent.charisma,
        perception=agent.perception,
        luck=agent.luck,
        energy=agent.energy,
        speed=agent.speed,
    )
