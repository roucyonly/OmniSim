# Plan 3: 规则引擎

## 前置
Plan 1 + Plan 2 完成，有方格地图和 Agent 决策骨架。

## 目标
实现不依赖 LLM 的确定性规则系统：移动、日常行为、战斗骨架、社交互动。

## 产出文件
```
server/app/
├── rules/
│   ├── __init__.py
│   ├── movement.py         # 方格移动 + 行进速度
│   ├── daily.py            # 日常行为（睡觉、吃饭、练功、巡逻）
│   ├── combat.py           # 战斗骨架
│   ├── social.py           # 社交互动（打招呼、对话触发）
│   └── scheduler.py        # 行为调度器：统一执行 action
```

## 详细步骤

### 3.1 移动系统 (Movement)
- **TerrainSpeed**: 不同地形的速度系数
  ```python
  TERRAIN_SPEED = {
      "plain": 1.0,
      "mountain": 0.5,
      "forest": 0.7,
      "water": 0.3,
      "building": 0.8,
  }
  ```
- 每个 tick 的移动格数 = `base_speed × skill_bonus × terrain_speed × weather_modifier`
  - base_speed: T1=3, T2=2, T3=1
  - skill_bonus: 轻功等级加成（1.0~2.0）
- `move(agent, target_x, target_y)`:
  - 用 BFS/A* 找最短路径
  - 每 tick 沿路径移动若干格
  - 更新 agent.x, agent.y
  - 写入记忆 "从(x1,y1)向(x2,y2)行进"

### 3.2 日常行为 (Daily)
- 每种日常行为定义：名称、消耗 tick、前置条件、效果
  ```python
  DAILY_ACTIONS = {
      "sleep":      {"ticks": 2, "time": "night",     "effect": {"energy": +30}},
      "eat":        {"ticks": 1, "location": "食堂",   "effect": {"hunger": -20}},
      "practice":   {"ticks": 1, "time": "day",        "effect": {"skill_exp": +5}},
      "patrol":     {"ticks": 2, "location": "外围",    "effect": {"faction_rep": +1}},
      "teach":      {"ticks": 1, "requires": "师父",   "effect": {"student_exp": +3}},
  }
  ```
- `execute_daily(agent, action_name)`:
  - 检查前置条件
  - 执行效果，更新 agent 状态
  - 写入记忆

### 3.3 战斗骨架 (Combat)
- MVP 只做最简判定，不深入
- **属性**: 攻击力, 防御力, 内力, 招式列表
- `resolve_combat(attacker, defender)`:
  - 伤害 = max(攻击力 - 防御力, 1) + random
  - 回合制：每 tick 一回合
  - 血量归零则战败
- 战斗结果写入双方记忆

### 3.4 社交互动 (Social)
- `greet(agent_a, agent_b)` — 打招呼，轻微增加好感
- `chat(agent_a, agent_b)` — 触发对话（MVP 用模板，后续 LLM）
- `train_together(agent_a, agent_b)` — 一起练功，增加技能经验和好感
- 社交结果写入记忆和关系

### 3.5 行为调度器 (Scheduler)
- 统一入口 `execute_action(agent, action)`:
  ```python
  def execute_action(agent, action):
      match action.type:
          case "move"      → movement.move(agent, action.target)
          case "daily"     → daily.execute_daily(agent, action.name)
          case "combat"    → combat.resolve_combat(agent, action.target)
          case "social"    → social.handle(agent, action.target, action.social_type)
      agent.remember(action)
  ```

## 验证
- Agent 在 20×20 地图上从 A 点移动到 B 点，路径合理，速度受地形影响
- Agent 执行"练功"行为，技能经验增加
- 两个 Agent 交互（打招呼），双方记忆和好感变化
