# Plan 1: 核心引擎 + 数据模型

## 目标
搭建项目骨架，实现 tick 驱动的模拟循环和 N×N 方格世界。

## 产出文件
```
server/
├── pyproject.toml              # 项目依赖 (fastapi, uvicorn, sqlalchemy, pydantic)
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI 入口，健康检查接口
│   ├── models/
│   │   ├── __init__.py
│   │   ├── base.py             # SQLAlchemy Base, engine, session
│   │   ├── world.py            # World ORM 模型
│   │   ├── location.py         # Location (方格) ORM 模型
│   │   └── agent.py            # Agent ORM 模型（基础字段：name, tier, position 等）
│   ├── simulation/
│   │   ├── __init__.py
│   │   ├── engine.py           # SimulationEngine 类：tick() 主循环
│   │   └── time_system.py      # TimeSystem：tick 推进，12 tick = 1 天
│   └── schemas/
│       ├── __init__.py
│       └── world.py            # Pydantic schemas (WorldState, TickResult)
```

## 详细步骤

### 1.1 初始化 Python 项目
- 创建 `server/pyproject.toml`，依赖：fastapi, uvicorn, sqlalchemy[asyncio], aiosqlite (MVP 阶段用 SQLite), pydantic
- 创建目录结构

### 1.2 数据模型
- **World**: id, name, grid_size (N), current_tick, current_day, status(running/paused), theme
- **Location**: id, world_id, x, y, terrain(plain/mountain/forest/water/building), name, building_type, faction_id
- **Agent**: id, world_id, name, tier(1/2/3), x, y, status(idle/moving/practicing/sleeping/talking), personality, current_plan_json

### 1.3 模拟引擎
- `SimulationEngine` 类：
  - `tick()`: 推进一个 tick
    1. `time_system.advance()` — 更新 tick/day
    2. 遍历所有 agent，执行感知→决策→执行（本阶段用 stub，后续填充）
    3. 返回 `TickResult`（本 tick 所有 agent 的状态变化）
  - `start()`, `pause()`, `set_speed(speed)` 控制方法
- `TimeSystem`：
  - 维护 current_tick, current_day
  - 1 tick = 1 时辰，12 tick = 1 天
  - 提供 `get_time_of_day()` 返回当前时辰名（子、丑、寅...）

### 1.4 FastAPI 入口
- `GET /api/health` — 健康检查
- `GET /api/world/{id}` — 获取世界状态
- `POST /api/world/{id}/tick` — 手动推进一个 tick（调试用）
- `POST /api/world` — 创建世界（传入 grid_size, name）

## 验证
- 启动 FastAPI，POST 创建一个 20×20 的世界
- GET 世界状态返回正确数据
- 手动 POST tick，current_tick 递增，时辰正确轮转
