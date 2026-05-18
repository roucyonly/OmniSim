# Plan 2: Agent 系统（记忆流 + 规划）

## 前置
Plan 1 完成后，有 Agent ORM 模型和模拟引擎骨架。

## 目标
实现斯坦福 AI 小镇 核心的 Agent 决策架构：记忆流、规划、反思。

## 产出文件
```
server/app/
├── agents/
│   ├── __init__.py
│   ├── base.py             # AgentBase 类（不依赖 ORM，纯逻辑）
│   ├── memory.py           # MemoryStream 记忆流
│   ├── planner.py          # 规划器（生成/修订每日计划）
│   ├── reflection.py       # 反思系统
│   └── decision.py         # 决策路由：判断走规则引擎还是 LLM
├── models/
│   ├── memory.py           # Memory ORM 模型
│   └── reflection.py       # Reflection ORM 模型
```

## 详细步骤

### 2.1 记忆流 (MemoryStream)
- **Memory ORM**: id, agent_id, tick, description, importance(1-10), embedding(预留)
- **MemoryStream 类**:
  - `write(description, importance)` — 写入一条记忆
  - `query(context, limit=10)` — 检索相关记忆，按 相关性×重要性×时效性 排序
  - MVP 阶段：相关性用关键词匹配，后续可换 embedding
  - 时效性衰减函数：`score = recency_decay ^ (current_tick - memory_tick)`，recency_decay = 0.995

### 2.2 规划器 (Planner)
- **DailyPlan**: 每日 12 tick 的计划，格式为 `[{tick: 0, action: "晨练"}, {tick: 1, action: "与师妹切磋"}, ...]`
- `generate_plan(agent, memories, reflections)`:
  - MVP 阶段：用模板 + 简单规则生成（如"弟子型"角色：晨练→午饭→练功→晚饭→休息）
  - 后续接入 LLM 生成个性化计划
- `revise_plan(agent, event)` — 遇到突发事件时重新规划剩余 tick

### 2.3 反思系统 (Reflection)
- **Reflection ORM**: id, agent_id, tick, content
- 每 6 tick（半天）触发一次反思
- `reflect(agent, recent_memories)`:
  - MVP 阶段：用规则总结（如"最近 3 次练剑 → 剑法熟练度提升"）
  - 后续接入 LLM 生成自然语言反思

### 2.4 AgentBase
- 整合以上模块，提供 `step(tick, world_state)` 方法：
  1. `perceive()` — 收集周围环境
  2. `decide()` — 查看当前计划，决策路由
  3. `act()` — 执行动作，更新状态
  4. `remember()` — 写入记忆

### 2.5 决策路由 (DecisionRouter)
- 根据 action 类型判断：
  - 日常（睡觉、吃饭、巡逻）→ 规则引擎直接执行
  - 对话、规划、反思 → 标记为 LLM 待处理
  - MVP 阶段：对话用模板回复，先不调 LLM

## 验证
- 创建一个 Agent，手动写入若干记忆
- query 检索返回按评分排序的结果
- generate_plan 生成一天的日程
- agent.step() 完成一个 tick 的完整流程
