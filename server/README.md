# OmniSim Server

造物主模拟器后端，基于 FastAPI + SQLAlchemy。

## 启动

```bash
# 安装依赖
pip install -e ".[dev]"

# 启动开发服务器
uvicorn app.main:app --reload
```

启动后访问 http://localhost:8000/docs 查看自动生成的 API 文档。

## API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/health` | 健康检查 |
| POST | `/api/worlds` | 创建世界 |
| GET | `/api/worlds` | 列出所有世界 |
| GET | `/api/worlds/{id}` | 世界详情 |
| GET | `/api/worlds/{id}/locations` | 世界地点列表 |
| GET | `/api/worlds/{id}/agents` | 世界角色列表 |
| POST | `/api/worlds/{id}/tick` | 手动推进一个 tick |

## 项目结构

```
app/
├── main.py           # FastAPI 入口 + 路由
├── models/           # SQLAlchemy ORM 模型
│   ├── base.py       # 数据库引擎 + 会话
│   ├── world.py      # World
│   ├── location.py   # Location (方格)
│   └── agent.py      # Agent
├── simulation/       # 模拟引擎
│   ├── engine.py     # SimulationEngine (tick 主循环)
│   └── time_system.py # TimeSystem (12时辰)
└── schemas/          # Pydantic 请求/响应模型
    └── world.py
```
