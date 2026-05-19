# Plan 2: Agent 系统（记忆流 + 情感 + 关系 + 规划）

> **v2 更新**：基于逆水寒 AI NPC 技术实践（详见 [ref-nishuihan-ai-npc.md](ref-nishuihan-ai-npc.md)），新增情感系统、关系图谱、记忆增强、性格结构化、主动行为。

## 前置
Plan 1 完成后，有 Agent ORM 模型和模拟引擎骨架。

## 目标
实现斯坦福 AI 小镇 核心的 Agent 决策架构，并融入情感驱动和关系网络。

## 产出文件
```
server/app/
├── agents/
│   ├── __init__.py
│   ├── base.py             # AgentBase 类（不依赖 ORM，纯逻辑）
│   ├── memory.py           # MemoryStream 记忆流（增强版）
│   ├── emotion.py          # 情感系统 [新增]
│   ├── relationship.py     # 关系图谱 [新增]
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
@dataclass
class RollResult:
    raw: int              # 原始骰子点数 1-100
    target: int           # 目标值（属性 - 难度 + 加成），clamp [5, 95]
    success: bool         # raw <= target
    degree: str           # "大成功/成功/失败/大失败"

def roll(attribute_value: float, difficulty: int, bonus: float = 0) -> RollResult:
    """
    百分比 roll-under 系统。
    target = clamp(attribute_value - difficulty + bonus, 5, 95)
    raw = randint(1, 100)
    raw <= target//5 或 raw<=5 → 大成功
    raw <= target → 成功
    raw <= target+10 → 失败
    else → 大失败
    """
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

- 大成功/大失败（raw<=5 / raw>=96）不受 modifier 影响，必定触发
- 骰子结果写入记忆，影响后续反思（"今日练剑侥幸突破，感觉运气不错"）
- **骰子→情感联动**：骰子结果触发情感变化（大成功 → valence +0.3，大失败 → valence -0.4）
- **骰子→关系联动**：社交骰子结果影响关系值（成功 → trust +3，失败 → trust -2）

### 2.1 记忆流 (MemoryStream) — 增强版

- **Memory ORM**: id, agent_id, tick, description, importance(1-10), emotion_tag, involved_agents(JSON), location
- **MemoryEntry 数据类**:
  ```python
  @dataclass
  class MemoryEntry:
      id: str
      tick: int
      description: str
      importance: float         # 1-10
      emotion_tag: str          # "开心/愤怒/悲伤/恐惧/惊讶/平静"
      involved_agents: list[str]  # 涉及的其他角色 id
      location: str             # 发生地点
      created_at: float
      # 传播相关（详见 Plan 3.7 江湖事件传播）
      gossip_worthy: bool       # importance >= 7 自动标记
      source_id: str | None     # 谁告诉我的（二手记忆有值）
      hops: int                 # 传播轮次（0=一手目击）
      is_secondhand: bool       # 是否二手记忆
      known_by: list[str]       # 已被告知此消息的人（防重复传播）
  ```
- **MemoryStream 类**:
  - `write(description, importance, emotion="平静", involved_agents=[], location="", source_id=None, hops=0)` — 写入一条记忆
  - `query(context, limit=10)` — 检索相关记忆，按 相关性×重要性×时效性 排序
  - `query_by_agents(agent_ids, limit=5)` — 查询涉及特定角色的记忆 [新增]
  - `query_by_emotion(emotion, limit=5)` — 查询特定情绪的记忆 [新增]
  - `get_gossipworthy(exclude_known_by=None, limit=2)` — 取出可传播的八卦记忆 [新增]
  - MVP 阶段：相关性用关键词匹配，后续可换 embedding
  - 时效性衰减函数：`score = recency_decay ^ (current_tick - memory_tick)`，recency_decay = 0.995

### 2.2 情感系统 (emotion.py) [新增]

每个 Agent 维护一个情感状态，影响行为决策、骰子判定和对话风格。

```python
@dataclass
class EmotionalState:
    """情感状态"""
    valence: float           # 效价 [-1.0, 1.0]：负面 → 正面
    arousal: float           # 唤醒度 [0.0, 1.0]：平静 → 激动
    dominant_emotion: str    # 主导情绪：开心/愤怒/悲伤/恐惧/惊讶/厌恶/信任/平静
    emotion_log: list        # [(tick, 触发事件, valence变化值)]

    def shift(self, event: str, delta: float, tick: int):
        """情感偏移"""
        self.valence = max(-1.0, min(1.0, self.valence + delta))
        self.emotion_log.append((tick, event, delta))

    def decay(self, rate: float = 0.1):
        """每 tick 自然衰减，回归中性"""
        self.valence *= (1 - rate)
        self.arousal *= (1 - rate)

    def update_dominant(self):
        """根据 valence/arousal 推导主导情绪"""
        # 高正效价 + 高唤醒 → 开心
        # 高负效价 + 高唤醒 → 愤怒
        # 高负效价 + 低唤醒 → 悲伤
        # ...
```

**情感影响链**：
```
事件发生 → emotion.shift() 更新情感
         → 骰子判定：正面情绪 bonus +arousal*5，负面情绪 penalty +|valence|*3
         → 计划偏好：valence<−0.5 时倾向独处行为，valence>0.5 时倾向社交
         → 对话风格：LLM prompt 注入当前情绪（Plan 6）
         → 每 tick 衰减 → 回归中性
```

**事件→情感映射表**：

| 事件类型 | valence 变化 | arousal 变化 |
|---------|-------------|-------------|
| 骰子大成功 | +0.3 ~ +0.5 | +0.3 |
| 骰子成功 | +0.1 ~ +0.2 | +0.1 |
| 骰子失败 | −0.1 ~ −0.2 | +0.1 |
| 骰子大失败 | −0.3 ~ −0.5 | +0.3 |
| 社交正面（被赞美、帮助） | +0.2 | +0.1 |
| 社交负面（被拒绝、批评） | −0.2 | +0.2 |
| 孤独（计划涉及的人不在场） | −0.1 | −0.1 |
| 基本需求满足（吃饱、睡好） | +0.1 | −0.1 |
| 基本需求未满足（饥饿、疲劳） | −0.1 | +0.1 |

### 2.3 关系图谱 (relationship.py) [新增]

Agent 之间的关系网络，影响交互意愿和效果。

```python
@dataclass
class Relationship:
    """两个 Agent 之间的关系"""
    target_id: str
    target_name: str
    relation_type: str       # 师徒/同门/恋人/敌对/陌生人
    trust: float             # 信任度 [-100, 100]
    intimacy: float          # 亲密值 [0, 100]
    impression: str          # 一句话印象（由反思生成/更新）
    last_interaction_tick: int
    interaction_count: int
```

**关系变化规则**：

| 触发条件 | trust | intimacy | 说明 |
|---------|-------|----------|------|
| 同地点社交（普通） | +1 | +2 | 日常积累 |
| 社交骰子成功 | +3 | +3 | 积极互动 |
| 社交骰子大成功 | +5 | +5 | 深刻印象 |
| 社交骰子失败 | −2 | −1 | 不愉快 |
| 社交骰子大失败 | −5 | −3 | 严重冲突 |
| 一起练功/切磋 | +1 | +2 | 共同经历 |
| 12+ tick 无互动 | 0 | −1 | 疏远衰减 |
| impression 更新 | — | — | 每 12 tick（一天）反思时可能更新 |

**关系→行为影响**：
- trust > 50 → 对话更开放，社交骰子 bonus +3
- trust < −30 → 可能回避或敌对
- intimacy > 60 → 主动行为概率提升
- relation_type 为"师徒" → 掌门型角色计划中更关注对方

### 2.4 性格结构化

在现有自由文本 personality 基础上，增加性格维度向量：

```python
@dataclass
class PersonalityVector:
    """性格维度 — 影响行为偏好"""
    extraversion: float     # 外向性 [0, 1]：社交主动性
    agreeableness: float    # 宜人性 [0, 1]：合作/冲突倾向
    conscientious: float    # 尽责性 [0, 1]：计划执行稳定性
    openness: float         # 开放性 [0, 1]：冒险/探索意愿
    stability: float        # 情绪稳定性 [0, 1]：情感波动幅度
```

**华山派角色性格向量预设**：

| 角色 | extraversion | agreeableness | conscientious | openness | stability |
|------|-------------|--------------|--------------|---------|-----------|
| 令狐冲 | 0.9 | 0.8 | 0.3 | 0.9 | 0.7 |
| 岳灵珊 | 0.8 | 0.7 | 0.5 | 0.7 | 0.6 |
| 岳不群 | 0.4 | 0.3 | 0.9 | 0.4 | 0.8 |
| 宁中则 | 0.6 | 0.9 | 0.8 | 0.5 | 0.7 |
| 劳德诺 | 0.4 | 0.4 | 0.7 | 0.3 | 0.6 |

**性格→行为映射**：
- extraversion > 0.7 → 更可能在自由时间主动社交
- agreeableness < 0.4 → 更容易产生冲突
- conscientious < 0.4 → 偶尔偏离计划（重规划概率 +20%）
- openness > 0.7 → 遇到新事物时探索概率更高
- stability < 0.4 → 情感衰减更慢（情绪持续更久）

### 2.5 规划器 (Planner)

- **DailyPlan**: 每日 12 tick 的计划，格式为 `[{tick: 0, action: "晨练", location: "练武场"}, ...]`
- `generate_plan(agent, memories, reflections)`:
  - MVP 阶段：用模板 + 简单规则生成
  - 后续接入 LLM 生成个性化计划
- `revise_plan(agent, event)` — 遇到突发事件时重新规划剩余 tick
- **计划偏好受情感影响**：
  - valence < −0.3 时，优先选择"独处"类行为
  - valence > 0.3 时，优先选择"社交"类行为
  - arousal > 0.7 时，可能偏离计划做冲动行为

### 2.5.1 计划冲突解决

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
5. 结果写入双方记忆 + 情感变化：
   - 令狐冲："到了练剑场，小师妹不知去了哪里，有些失落" → valence −0.1
   - 岳灵珊：不受影响，照常下山（但后续可能从别人处听说大师兄找她）

### 2.6 反思系统 (Reflection)
- **Reflection ORM**: id, agent_id, tick, content
- 每 6 tick（半天）触发一次反思
- `reflect(agent, recent_memories, relationships)`:
  - MVP 阶段：用规则总结（如"最近 3 次练剑 → 剑法熟练度提升"）
  - 反思时会更新 **relationship.impression**（对某人的印象）
  - 后续接入 LLM 生成自然语言反思

### 2.7 主动行为判定 [新增]

在 `step()` 中，当当前计划允许自由度时（自由活动 tick），检查是否主动发起交互：

```python
def _check_proactive_intent(self, nearby_agents, current_tick):
    """检查是否主动发起交互"""
    # 只在自由活动时间触发
    if not self._is_free_time(current_tick):
        return None

    for agent in nearby_agents:
        rel = self.relationships.get(agent.id)
        if not rel:
            # 陌生人：高外向性 → 可能打招呼
            if self.personality.extraversion > 0.7 and self.emotion.valence > 0:
                return ("greet", agent)
            continue

        # 熟人：根据关系和情绪决定
        if rel.intimacy > 60 and self.emotion.valence > 0.3:
            return ("chat", agent)       # 心情好 + 关系好 → 主动聊天
        if rel.intimacy > 40 and self.personality.extraversion > 0.6:
            return ("greet", agent)      # 外向 + 有关系 → 打招呼
        if rel.trust < -30:
            return ("confront", agent)   # 敌对关系 → 可能挑衅

    return None
```

### 2.8 AgentBase — 完整 step 流程

```python
class AgentBase:
    def step(self, tick, nearby_agents):
        # 1. 情感衰减
        self.emotion.decay(rate=0.1)

        # 2. 获取当前计划
        plan_action = self.planner.get_action_for_tick(tick)

        # 3. 主动行为判定（自由时间）
        proactive = self._check_proactive_intent(nearby_agents, tick)
        if proactive:
            plan_action = self._override_with_proactive(proactive)

        # 4. 决策路由
        decision = self.decision_router.route(plan_action, nearby_agents)

        # 5. 执行动作 + 骰子判定（如需要）
        dice_result = None
        if plan_action.action in DICE_ACTIONS:
            dice_result = roll(...)
            # 骰子结果 → 情感变化
            self._apply_dice_emotion(dice_result)
            # 骰子结果 → 关系变化（如果有 nearby）
            self._apply_dice_relationship(dice_result, nearby_agents)

        # 6. 写入记忆（增强版：带情绪标签和涉及角色）
        self.memory.write(
            description=self._describe_action(plan_action, dice_result),
            importance=self._score_importance(plan_action, dice_result),
            emotion=self.emotion.dominant_emotion,
            involved_agents=[a.id for a in nearby_agents],
            location=self.state.location_name
        )

        # 7. 反思（每 6 tick）
        if tick % 6 == 0:
            self.reflect()

        return StepResult(...)
```

### 2.9 决策路由 (DecisionRouter)
- 根据 action 类型判断：
  - 日常（睡觉、吃饭、巡逻）→ 规则引擎直接执行
  - 对话、规划、反思 → 标记为 LLM 待处理
  - 主动社交行为 → 标记为 LLM 待处理
  - MVP 阶段：对话用模板回复，先不调 LLM

## 验证
- 创建一个 Agent，手动写入若干记忆（带 emotion_tag 和 involved_agents）
- query_by_agents 检索返回正确结果
- generate_plan 生成一天的日程
- emotion.shift() 正确更新情感状态
- relationship 在社交互动后正确变化
- agent.step() 完成一个 tick 的完整流程（含情感衰减 + 关系更新）

## 文件变更清单（v2 新增/修改）

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `agents/emotion.py` | **新增** | EmotionalState 数据类 + 情感逻辑 |
| `agents/relationship.py` | **新增** | Relationship 数据类 + 关系管理 |
| `agents/memory.py` | **修改** | MemoryEntry 增加 emotion_tag, involved_agents, location 字段 |
| `agents/base.py` | **修改** | AgentState 增加 emotion, relationships, personality_vector；step() 融入情感/关系/主动行为 |
| `agents/planner.py` | **微调** | 计划生成考虑情感偏好 |
| `agents/reflection.py` | **微调** | 反思时更新 relationship.impression |
| `simulation/engine.py` | **修改** | tick 后更新 agent 间关系 |
