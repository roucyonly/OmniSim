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
├── core/
│   ├── __init__.py
│   └── dice.py             # 骰子系统：T2+ Agent 判定核心
├── models/
│   ├── memory.py           # Memory ORM 模型
│   └── reflection.py       # Reflection ORM 模型
```

## 详细步骤

### 2.0 骰子系统 (dice.py) — T2+ Agent 判定核心

所有 T2 以上 Agent 在需要判定的场景下，通过骰子 roll 点决定结果，而非固定公式。

**核心设计**：
```python
# dice.py

@dataclass
class RollResult:
    raw: int              # 原始骰子点数 1-100
    modifier: float       # 属性加成后的修正值
    total: float          # 最终得分 = raw + modifier
    difficulty: int       # 难度等级
    success: bool         # total >= difficulty
    degree: str           # "大成功/成功/勉强/失败/大失败"

def roll(attribute_value: float, difficulty: int, bonus: float = 0) -> RollResult:
    """
    attribute_value: 相关属性值（天赋、技能等级、好感度等）
    difficulty:      难度阈值（越高越难）
    bonus:           额外加成（天气、道具、状态等）
    """
    raw = random.randint(1, 100)
    modifier = attribute_value + bonus
    total = raw + modifier
    ...
```

**判定场景**（T2+ Agent 适用）：

| 场景 | 判定属性 | 难度参考 | 大成功效果 | 大失败效果 |
|------|---------|---------|-----------|-----------|
| 修炼突破 | 天赋 + 当前熟练度 | 60-90 | 跳级突破，领悟新招 | 走火入魔，受伤/倒退 |
| 招式学习 | 悟性 + 师父好感 | 50-80 | 自创变招 | 误入歧途 |
| 说服/社交 | 魅力 + 关系值 | 40-70 | 获得额外好感/秘密 | 惹怒对方，关系下降 |
| 战斗命中 | 武功等级 + 速度 | 对手闪避值 | 暴击/破绽 | 露出破绽 |
| 战斗闪避 | 轻功 + 敏捷 | 对手攻击值 | 反击机会 | 被击中要害 |
| 发现/感知 | 感知 + 经验 | 40-80 | 发现隐藏信息 | 错过线索 |
| 偶遇/缘分 | 运势 | 30-60 | 结识重要人物 | 无事发生 |
| 情绪波动 | 性格倾向 + 事件强度 | 50-80 | 产生强烈记忆/反思 | 情绪平淡 |

**属性面板按层级区分**：

| 维度 | T1 (令狐冲、岳不群) | T2 (掌柜、弟子) | T3 (路人、农夫) |
|------|---------------------|-----------------|-----------------|
| 武功/攻击/防御 | 完整 | 有，简化 | 无 |
| 天赋/悟性 | 有 | 有，偏低 | 无 |
| 魅力 | 有 | 有 | 无 |
| 感知 | 有 | 无 | 无 |
| 运势 | 有 | 无 | 无 |
| 性格倾向 | 有 | 有，简略 | 无 |
| 轻功/速度 | 有 | 有 | 无 |
| 骰子判定 | 全场景 | 仅社交+战斗 | 不走骰子，纯行为树 |

- 大成功/大失败（raw=100/raw=1）不受 modifier 影响，必定触发
- 骰子结果写入记忆，影响后续反思（"今日练剑侥幸突破，感觉运气不错"）
- **骰子→叙事流程**：dice.roll() 得到结果 → {故事背景 + 人物状态 + 骰子结果} → 发给 LLM → 生成后续叙事内容

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

### 2.2.1 计划冲突解决

当 Agent A 的计划涉及 Agent B，但两人计划不一致时的处理：

```
令狐冲 tick2 = "找小师妹练剑"
岳灵珊 tick2 = "下山买糖葫芦"
```

**执行流程**：
1. tick2 开始时，令狐冲执行"前往练剑场找小师妹"
2. **距离检查**：令狐冲到达练剑场，检查岳灵珊是否在场
3. **在场** → 触发社交骰子判定（令狐冲魅力 + 关系值 vs 岳灵珊当前计划优先级）→ 成功则岳灵珊改计划一起练剑，失败则各做各的
4. **不在场** → 令狐冲独自执行替代行为（独自练剑 / 追去找她 / 放弃），触发重规划
5. 结果写入双方记忆：
   - 令狐冲："到了练剑场，小师妹不知去了哪里，有些失落"
   - 岳灵珊：不受影响，照常下山（但后续可能从别人处听说大师兄找她）

**关键原则**：
- 冲突本身就是故事素材，不强制协调
- 错过的遗憾、独自的等待 → 情绪波动 → 写入记忆 → 影响反思
- 同一地点的冲突用骰子判定，不同地点的错过用记忆记录

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
