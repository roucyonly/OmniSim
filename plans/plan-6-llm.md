# Plan 6: LLM 集成

## 前置
Plan 2（Agent 系统）+ Plan 3（规则引擎）完成，Agent 能用模板运行一天。

## 目标
接入 LLM API，让 Agent 的规划、对话、反思从模板升级为个性化生成。

## 产出文件
```
server/app/
├── llm/
│   ├── __init__.py
│   ├── gateway.py           # LLM 调用网关（统一接口，支持 Claude/GPT）
│   ├── prompts/
│   │   ├── planning.py      # 规划 prompt 模板
│   │   ├── dialogue.py      # 对话 prompt 模板
│   │   ├── reflection.py    # 反思 prompt 模板
│   │   └── narrative.py     # 每日纪事 prompt 模板
│   ├── cache.py             # 响应缓存（相同上下文不重复调用）
│   └── config.py            # LLM 配置（API key, model, temperature）
```

## 详细步骤

### 6.1 LLM Gateway
- 统一调用接口：
  ```python
  async def call_llm(prompt: str, system: str, temperature: float = 0.7) -> str
  ```
- 支持多 provider（Claude API 为主，OpenAI 为备）
- 请求日志：记录每次调用的时间、token 数、用途（用于成本监控）
- 速率限制：每分钟最多 N 次调用

### 6.2 Prompt 模板设计

#### 规划 Prompt
```
你是一个武侠世界中的角色。
姓名：{name}
身份：{role}
性格：{personality}
当前位置：{location}
近期经历：{recent_memories}
当前认知：{reflections}

请为今天制定计划，共12个时辰。
输出 JSON 格式：
[{"tick": 0, "action": "...", "target": "...", "reason": "..."}]
```

#### 对话 Prompt
```
你是{name}，{personality}。
你正在{location}与{other_name}({other_personality})交谈。
你们的关系：{relationship}
最近发生的事：{recent_context}

请以你的口吻回应对方说的话。保持角色性格一致。
```

#### 反思 Prompt
```
你是{name}。
请回顾最近的经历：
{recent_memories}

提炼出2-3个最重要的认知或感悟。
```

#### 每日纪事 Prompt
```
你是华山派的史官。
今天发生了以下事件：
{major_events}

请写一篇简短的每日纪事（100字以内），只记录重大事件。
如果全是日常琐事，输出"今日平静无事"。
```

### 6.3 缓存策略
- 相同 agent_id + 相同 tick 上下文 → 返回缓存结果
- 缓存 key = hash(agent_id + recent_memory_ids + current_plan_hash)
- Redis 存储，TTL = 1 小时

### 6.4 成本控制
- **批量处理**：同一 tick 内所有 agent 的反思请求合并为一次 LLM 调用
- **分级调用**：
  - T1 角色对话 → LLM 生成
  - T2 角色对话 → 模板 + LLM 微调
  - T3 角色 → 不调 LLM
- **降级策略**：API 额度用尽时自动回退到模板模式

### 6.5 对接 Agent 系统
- 修改 `planner.py`：`generate_plan()` 优先用 LLM，失败时回退模板
- 修改 `reflection.py`：`reflect()` 用 LLM 生成反思
- 修改 `rules/social.py`：`chat()` 用 LLM 生成对话内容
- 新增 `narrative.py`：每天结束时生成每日纪事

## 验证
- 令狐冲生成的一天计划不再是固定模板，而是基于性格和记忆的个性化计划
- 令狐冲与岳灵珊对话内容自然、符合角色性格
- 反思内容有深度（"岳不群师父今日对我的态度有些微妙..."）
- 每天结束生成一篇纪事，日常天跳过
