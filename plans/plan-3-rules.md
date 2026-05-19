# Plan 3: 规则引擎

## 前置
Plan 1 + Plan 2 完成，有方格地图和 Agent 决策骨架。

## 目标
实现不依赖 LLM 的确定性规则系统：移动、日常行为、战斗骨架、社交互动、江湖事件传播、世界黑板、多人群聊、行为触发。

## 产出文件
```
server/app/
├── rules/
│   ├── __init__.py
│   ├── movement.py         # 方格移动 + 行进速度
│   ├── daily.py            # 日常行为（睡觉、吃饭、练功、巡逻）
│   ├── combat.py           # 战斗骨架
│   ├── social.py           # 社交互动（打招呼、对话触发、小道消息传播）
│   ├── gossip.py           # 江湖事件传播引擎
│   ├── blackboard.py       # 世界黑板（全局事件池 + Pub-Sub）
│   ├── group_chat.py       # 多人场景对话（AOI 群聊路由）
│   ├── triggers.py         # 行为触发引擎（阈值→引擎动作）
│   ├── event_chains.py     # 事件链引擎（统一事件→结果→连锁）[新增]
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

**依赖 Plan 2 的情感系统和关系图谱。**

- `greet(agent_a, agent_b)` — 打招呼
  - 双方 intimacy += 1
  - agent_a.emotion.shift("打招呼", +0.05)
  - 写入双方记忆（emotion_tag 按当前情绪）
- `chat(agent_a, agent_b)` — 触发对话（MVP 用模板，后续 LLM）
  - 社交骰子判定（魅力 + 关系 trust vs 难度 40）
  - 成功 → 双方 trust += 2, intimacy += 2
  - 失败 → trust -= 1
  - 大成功 → trust += 5, intimacy += 5, 产生"印象深刻"记忆
  - 大失败 → trust -= 3, 可能产生负面情绪
- `train_together(agent_a, agent_b)` — 一起练功
  - 双方 intimacy += 2
  - 各自获得技能经验
  - 写入记忆（involved_agents 标记对方）
- `confront(agent_a, agent_b)` — 对峙/冲突
  - 当 trust < -30 时可能触发
  - 社交骰子判定（意志力 + 愤怒情绪 vs 对方威慑）
  - 失败 → 道歉，trust 小幅恢复
  - 大失败 → 升级为战斗
- 社交结果写入记忆（带 emotion_tag + involved_agents）并更新关系
- **每次社交互动后自动触发小道消息传播**（见 3.7）

### 3.5 行为调度器 (Scheduler)
- 统一入口 `execute_action(agent, action)`:
  ```python
  def execute_action(agent, action, nearby_agents):
      match action.type:
          case "move"      → movement.move(agent, action.target)
          case "daily"     → daily.execute_daily(agent, action.name)
          case "combat"    → combat.resolve_combat(agent, action.target)
          case "social"    → social.handle(agent, action.target, action.social_type)
      # 写入增强记忆（带情绪和涉及角色）
      agent.remember(action, nearby_agents)
      # 更新情感状态
      agent.emotion.shift(action.description, EMOTION_DELTA[action.type])
  ```

### 3.6 共享事件记忆

当多个 Agent 在同一地点经历同一事件时，写入共享记忆：

```python
def record_shared_event(agents, event_desc, tick, location):
    """为所有在场 Agent 写入同一条事件的记忆"""
    agent_ids = [a.id for a in agents]
    for agent in agents:
        agent.memory.write(
            description=event_desc,
            importance=score_event(event_desc),
            emotion=agent.emotion.dominant_emotion,
            involved_agents=[aid for aid in agent_ids if aid != agent.id],
            location=location
        )
```

这样 Agent 事后可以通过 `query_by_agents` 查到"当时谁也在场"。

### 3.7 江湖事件传播引擎 (Gossip) [新增]

**核心模型：记忆即信息源，社交即传播链，关系即带宽。**

事件不靠 LLM 传播，全靠规则引擎 + 记忆系统 + 关系图谱，**0 token 消耗**。

#### 3.7.1 事件分级

只有 importance >= 7 的记忆才标记为 `gossip_worthy`，进入传播候选池：

```python
# 记忆写入时自动判定
def write(self, description, importance, tick, ...):
    gossip_worthy = importance >= 7
    ...
```

| 事件 | importance | gossip_worthy |
|------|-----------|---------------|
| 骰子大成功/大失败 | 8-10 | ✓ |
| 人际冲突 | 8 | ✓ |
| 师父训话 | 7 | ✓ |
| 剧本事件（桃谷六仙闯山） | 9 | ✓ |
| 普通练功 | 3-4 | ✗ |
| 吃饭睡觉 | 1-2 | ✗ |

#### 3.7.2 传播触发

社交互动（greet/chat/train_together）结束时自动触发：

```python
def share_gossip(sharer: AgentBase, listener: AgentBase, tick: int):
    """两人相遇时交换小道消息"""
    rel = sharer.relationships.get(listener.id)
    if not rel or rel.trust < 20:
        return  # 不信任就不说

    # 取出 sharer 的一手/二手八卦，排除 listener 已经知道的
    gossips = sharer.memory.get_gossipworthy(
        exclude_already_known_by=listener.id,
        limit=2
    )

    for mem in gossips:
        # 关系控制传播细节
        detail = filter_detail(mem.description, rel.trust)
        # 失真处理
        distorted = distort(detail, mem.hops)

        listener.memory.write(
            description=f"听{sharer.state.name}说，{distorted}",
            importance=max(mem.importance - 1, 1),  # 每传一手降1
            emotion="惊讶",
            involved_agents=mem.involved_agents,
            location=mem.location,
            source_id=sharer.id,        # 谁告诉我的
            hops=mem.hops + 1,          # 传播轮次
            is_secondhand=True
        )
```

#### 3.7.3 关系控制传播粒度

```python
def filter_detail(description: str, trust: float) -> str:
    """根据信任度决定说多少"""
    if trust >= 70:
        return description  # 全盘托出
    elif trust >= 40:
        return simplify(description)  # 省略敏感细节
    else:
        return vague(description)  # 含糊其辞

def should_share(sharer, listener, mem) -> bool:
    """是否值得告诉对方"""
    rel = sharer.relationships.get(listener.id)
    # 涉及对方的八卦更容易被分享
    if listener.id in mem.involved_agents:
        return rel.trust >= 30
    # 和自己无关的事，只告诉亲密的人
    return rel.intimacy >= 40
```

**关系→传播行为表**：

| 关系 | trust | 传播行为 |
|------|-------|---------|
| 亲密（>70） | 高 | 全盘托出，主动分享 |
| 一般（40-70） | 中 | 挑重要的说，省略细节 |
| 疏远（20-40） | 低 | 只说大事，点到为止 |
| 敌对（<20） | 负 | 不说，或故意歪曲 |
| 关系类型=师徒 | — | 师父的事弟子会传，弟子的事师娘会关心 |
| 事件涉及对方 | — | 更容易传播（"你知道吗，令狐冲今天说你了..."） |

#### 3.7.4 信息失真

每传一手，信息会失真一次：

```python
# 失真模板表：按事件类型 + 传播轮次
DISTORTION_TEMPLATES = {
    "大成功": [
        "{name}在{location}表现出色，令人刮目相看",  # hop 1
        "听说{name}最近状态不错",                      # hop 2
        "好像有人最近运气挺好的",                       # hop 3+
    ],
    "大失败": [
        "{name}在{location}出了点状况",
        "听说{name}最近不太顺",
        "似乎有人遇到了麻烦",
    ],
    "冲突": [
        "{name_a}和{name_b}在{location}起了争执",
        "听说{name_a}和{name_b}有些矛盾",
        "好像有两个人关系不太好",
    ],
    "师训": [
        "{master}在{location}严厉训斥了{disciple}",
        "听说{master}对{disciple}不太满意",
        "好像{disciple}最近惹师父生气了",
    ],
}

# 情感夸大：传播者的情绪会影响失真方向
# 传播者对事件主角有好感 → 弱化负面消息
# 传播者对事件主角有敌意 → 强化负面消息
def apply_emotion_bias(text: str, emotion: EmotionalState, target_id: str, rel: Relationship) -> str:
    if rel.trust > 60 and emotion.valence > 0:
        return text  # 好心情 + 好关系 = 如实传达
    if rel.trust < -20:
        return exaggerate_negative(text)  # 敌对关系 = 添油加醋
    return text
```

#### 3.7.5 传播上限

防止信息无限扩散：

```python
MAX_HOPS = 3  # 最多传 3 手，之后 importance 衰减到 1 不再传播
GOSSIP_COOLDOWN_TICKS = 6  # 同一条八卦 6 tick 内不会重复传播给同一人
```

#### 3.7.6 传播链示例

```
tick 4: 令狐冲在练武场切磋 → 骰子大成功
        → 令狐冲记忆: "在练武场切磋大成功，与岳灵珊在一起" (一手, imp=8, hops=0)
        → 岳灵珊记忆: "与令狐冲切磋，他状态极佳" (一手, imp=7, hops=0)

tick 6: 岳灵珊（自由活动）遇到宁中则 → 社交 → 触发 gossip
        → 宁中则 trust=85 → 分享详细
        → 宁中则获得: "听岳灵珊说，令狐冲在练武场切磋表现出色，令人刮目相看"
          (二手, imp=6, hops=1, source=岳灵珊)

tick 9: 宁中则遇到岳不群 → 社交 → 触发 gossip
        → 岳不群 trust=70 → 告知
        → 岳不群获得: "听宁中则说，听说令狐冲最近状态不错"
          (三手, imp=4, hops=2, source=宁中则)
        → 岳不群反思时可能更新对令狐冲的 impression:
          "冲儿虽然顽劣，剑法确实有天赋..."

tick 9: 梁发在弟子精舍遇到高克明 → gossip
        → 梁发 trust=55 with 高克明 → 挑重点说
        → 高克明获得: "听梁发说，令狐冲今天练剑还不错"
          (三手, imp=4, hops=2)
        → 高克明 personality.agreeableness=0.3, 对令狐冲 trust=40
          → 反思: "又有什么了不起的..." (负面情绪微升)
```

#### 3.7.7 MemoryEntry 新增字段

```python
@dataclass
class MemoryEntry:
    # ... 现有字段 ...
    source_id: str | None = None      # 谁告诉我的（二手记忆有值）
    hops: int = 0                     # 传播轮次（0=一手）
    is_secondhand: bool = False       # 是否二手记忆
    known_by: list[str] = field(default_factory=list)  # 已知情的人（防重复传播）
```

### 3.8 世界黑板系统 (Blackboard) [新增]

> 参考《逆水寒》的"大宋头条"架构。全局事件池 + 发布订阅模式，让 Agent 通过共享数据间接通信，而非实时对话。

#### 3.8.1 设计理念

逆水寒的核心经验：**NPC 不需要真正聊天，只需要读写同一块黑板**。

```
Agent A 做了一件事 → 写入 Blackboard（结构化事件）
                    → 系统异步推送给相关 Agent 的记忆
                    → Agent B 下次反思时读到 → 改变对 A 的看法
                    → 玩家看到 B 对 A 的态度变了，以为他们"私下聊过"
```

#### 3.8.2 结构化事件

事件不是文本字符串，而是结构化数据，方便引擎处理和传播：

```python
@dataclass
class WorldEvent:
    id: str
    tick: int
    day: int
    event_type: str          # "combat" / "social" / "breakthrough" / "scripted" / "conflict" / "gossip"
    actors: list[str]        # 涉及的 agent id 列表
    location: str            # 发生地点
    description: str         # 人类可读描述（用于记忆写入）
    data: dict               # 结构化数据（引擎用）
    importance: int          # 1-10
    tags: list[str]          # 标签：["华山派", "剑法", "师徒", "冲突"]
    faction_scope: str       # 传播范围：/"all"/"faction:华山派"/"location:华山大殿"

    # data 结构示例：
    # 战斗事件: {"winner": "令狐冲", "loser": "高克明", "damage": 15, "weapon": "剑"}
    # 突破事件: {"agent": "令狐冲", "skill": "华山剑法", "old_level": 55, "new_level": 60}
    # 社交事件: {"initiator": "岳灵珊", "target": "令狐冲", "action": "切磋", "dice_result": "大成功"}
```

#### 3.8.3 Blackboard 类

```python
class Blackboard:
    """全局事件黑板 — 所有 Agent 的间接通信介质"""

    def __init__(self):
        self.events: list[WorldEvent] = []
        self.subscriptions: dict[str, list[str]] = {}  # agent_id → [event_types]
        self.event_log: list[WorldEvent] = []  # 历史存档（不衰减）

    def publish(self, event: WorldEvent):
        """发布事件到黑板"""
        self.events.append(event)
        self.event_log.append(event)
        # 通知订阅者
        self._notify_subscribers(event)

    def subscribe(self, agent_id: str, event_types: list[str]):
        """Agent 订阅感兴趣的事件类型"""
        self.subscriptions[agent_id] = event_types

    def query(self, event_type: str = None, tags: list[str] = None,
              since_tick: int = 0, faction: str = None, limit: int = 10) -> list[WorldEvent]:
        """查询事件（Agent 反思/规划时调用）"""
        results = [e for e in self.events
                   if e.tick >= since_tick
                   and (not event_type or e.event_type == event_type)
                   and (not faction or e.faction_scope in ("all", f"faction:{faction}"))
                   and (not tags or any(t in e.tags for t in tags))]
        return sorted(results, key=lambda e: e.importance, reverse=True)[:limit]

    def tick_cleanup(self, current_tick: int):
        """清理过期事件（保留 event_log）"""
        # importance < 3 且超过 12 tick 的事件从活跃池移除
        self.events = [e for e in self.events
                       if e.importance >= 3 or current_tick - e.tick < 12]

    def _notify_subscribers(self, event: WorldEvent):
        """将事件推送到订阅者的记忆（异步，不阻塞 tick）"""
        # 具体实现在 gossip.py 中，通过 blackboard → gossip 联动
        pass

    def get_daily_digest(self, day: int) -> list[WorldEvent]:
        """获取某天的重大事件（用于每日纪事生成）"""
        return [e for e in self.event_log if e.day == day and e.importance >= 7]
```

#### 3.8.4 事件自动发布

Agent 在以下时机自动往黑板发布事件：

```python
# base.py 的 step() 中，骰子判定后：
if dice_result and dice_result.degree in ("大成功", "大失败"):
    blackboard.publish(WorldEvent(
        tick=tick, day=day,
        event_type="breakthrough" if dice_result.degree == "大成功" else "accident",
        actors=[self.state.id] + [a.state.id for a in nearby_agents],
        location=self.state.location_name,
        description=self.state.last_action_desc,
        data={"dice_result": dice_result.degree, "action": action.action},
        importance=8 if dice_result.degree == "大成功" else 9,
        tags=[self.state.faction, action.action],
        faction_scope=f"faction:{self.state.faction}"
    ))

# combat.py 中，战斗结束时：
def resolve_combat(attacker, defender, result):
    blackboard.publish(WorldEvent(
        ...event_type="combat",
        actors=[attacker.id, defender.id],
        data={"winner": result.winner, "damage": result.damage},
        importance=8, ...
    ))
```

#### 3.8.5 Blackboard → Gossip 联动

黑板事件和 3.7 的 gossip 系统双向联动：

```
一手事件发生 → 同时写入 Agent 记忆 + Blackboard
Blackboard 事件 → 被 gossip 系统读取 → 生成江湖传闻 → 推送给相关 Agent
Agent 社交时 → 也能从 Blackboard 查询对方近期事件（"听说你最近..."）
```

```python
# gossip.py 中增加黑板联动
def share_gossip_from_blackboard(sharer, listener, tick, blackboard):
    """从黑板读取对方相关事件，补充口头八卦的不足"""
    # 查询与 listener 相关的近期黑板事件
    events = blackboard.query(
        tags=[listener.state.id],
        since_tick=tick - 6,
        limit=1
    )
    for event in events:
        if listener.state.id not in event.actors:  # 当事人不需要被告知
            listener.memory.write(
                description=f"听{sharer.state.name}说，{event.description}",
                importance=event.importance - 2,
                source_id=sharer.id,
                hops=1,
                is_secondhand=True,
                ...
            )
```

#### 3.8.6 引擎集成

```python
# engine.py 中初始化黑板
class SimulationEngine:
    def __init__(self):
        self.time_system = TimeSystem()
        self.agents = {}
        self.blackboard = Blackboard()  # 全局唯一黑板

    def tick(self):
        current_tick = self.time_system.advance()
        # ... 现有逻辑 ...

        # tick 结束后清理黑板
        self.blackboard.tick_cleanup(current_tick)
```

#### 3.8.7 场景示例

```
tick 4: 令狐冲在练武场切磋大成功
        → 写入令狐冲/岳灵珊记忆 (一手)
        → blackboard.publish(WorldEvent(
              event_type="breakthrough", actors=["令狐冲", "岳灵珊"],
              importance=8, tags=["华山派", "剑法"],
              faction_scope="faction:华山派"))

tick 6: 岳灵珊遇到宁中则 → 社交 → gossip 从黑板和个人记忆双源获取
        → 宁中则获得二手记忆

tick 8: 劳德诺（嵩山卧底）计划"在弟子精舍休息"
        → 劳德诺主动查询黑板: blackboard.query(tags=["华山派", "剑法"], since_tick=2)
        → 发现令狐冲突破事件 → 写入记忆 → 反思："得把这个消息传给左盟主..."
        → 劳德诺对令狐冲的 impression 更新

tick 24: 一天结束
        → blackboard.get_daily_digest(day=1) → 返回今天 importance>=7 的事件
        → 纪事生成: "今日令狐冲在练武场切磋大成功，岳灵珊在场旁观..."
```

### 3.9 多人场景对话 (Group Chat) [新增]

> 参考《逆水寒》的 AOI（Area of Interest）群聊空间。当多个 Agent 在同一地点时，建立临时"对话气泡"。

#### 3.9.1 触发条件

```python
def check_group_chat(agents_at_location: list[AgentBase], tick: int) -> bool:
    """判断是否触发群聊"""
    # 条件1: 至少 3 人在同一地点
    if len(agents_at_location) < 3:
        return False
    # 条件2: 至少有 1 个 T1（T1 是叙事核心）
    if not any(a.state.tier == 1 for a in agents_at_location):
        return False
    # 条件3: 当前是"自由活动"或社交类 tick
    if tick not in (6, 9):  # 午时、酉时
        return False
    # 条件4: 有可聊的话题（黑板事件或共享记忆）
    # ...
    return True
```

#### 3.9.2 群聊路由

```python
@dataclass
class ChatTurn:
    speaker_id: str
    speaker_name: str
    content: str
    emotion: str
    reply_to: str | None  # 回复谁

@dataclass
class GroupConversationResult:
    topic: str
    turns: list[ChatTurn]
    participants: list[str]
    summary: str  # 一句话总结
    importance: int

class GroupChatRouter:
    """多人场景对话路由"""

    def run(self, participants: list[AgentBase], tick: int,
            blackboard: Blackboard) -> GroupConversationResult:
        # Step 1: 确定话题
        topic = self._pick_topic(participants, tick, blackboard)

        # Step 2: 排序发言顺序（按 extraversion 降序）
        ordered = sorted(participants,
                         key=lambda a: a.personality.extraversion, reverse=True)

        # Step 3: 生成对话轮次
        turns = []
        for i, speaker in enumerate(ordered):
            turn = self._generate_turn(speaker, topic, ordered, turns, tick)
            if turn:
                turns.append(turn)
            if len(turns) >= 6:  # 最多 6 轮，防止无限聊
                break

        # Step 4: 生成总结
        summary = self._summarize(topic, turns)

        return GroupConversationResult(
            topic=topic["description"],
            turns=turns,
            participants=[p.state.id for p in participants],
            summary=summary,
            importance=topic.get("importance", 5)
        )
```

#### 3.9.3 话题选择

```python
def _pick_topic(self, participants, tick, blackboard):
    """从黑板和共享记忆中选择话题"""

    # 优先级 1: 黑板上涉及在场某人的重大事件
    for agent in participants:
        events = blackboard.query(tags=[agent.state.id], since_tick=tick - 6)
        if events:
            return {
                "type": "recent_event",
                "description": events[0].description,
                "importance": events[0].importance,
                "about_agent": agent.state.name,
            }

    # 优先级 2: 在场人员之间的共同记忆
    common = self._find_common_memory(participants)
    if common:
        return {"type": "shared_memory", "description": common, "importance": 5}

    # 优先级 3: 日常话题模板
    return {
        "type": "casual",
        "description": random.choice(CASUAL_TOPICS),
        "importance": 2,
    }

CASUAL_TOPICS = [
    "今天的饭菜味道怎么样",
    "最近练功有什么进展",
    "听说山下新开了一家酒楼",
    "天气真不错，适合练剑",
]
```

#### 3.9.4 发言生成（模板）

```python
def _generate_turn(self, speaker, topic, participants, prev_turns, tick):
    """为 speaker 生成一轮发言"""

    # 判断是否参与（内向的人可能沉默）
    if not prev_turns:  # 第一轮
        # 外向性越高越先说
        pass
    else:
        # 已有几轮对话，内向性高的人可能选择不说话
        if speaker.personality.extraversion < 0.3:
            if random.random() > 0.5:
                return None  # 沉默

    # 根据话题类型 + 性格生成发言
    templates = TOPIC_RESPONSE_TEMPLATES[topic["type"]]
    # 根据性格选模板
    if speaker.personality.agreeableness > 0.7:
        attitude = "supportive"   # 赞同
    elif speaker.personality.agreeableness < 0.4:
        attitude = "critical"     # 挑刺
    else:
        attitude = "neutral"      # 中立

    content = templates[attitude].format(
        name=speaker.state.name,
        topic_agent=topic.get("about_agent", ""),
        location=speaker.state.location_name,
    )

    return ChatTurn(
        speaker_id=speaker.id,
        speaker_name=speaker.name,
        content=content,
        emotion=speaker.emotion.dominant_emotion,
        reply_to=prev_turns[-1].speaker_id if prev_turns else None,
    )
```

**话题回应模板表**：

```python
TOPIC_RESPONSE_TEMPLATES = {
    "recent_event": {
        "supportive": [
            "{topic_agent}确实厉害，我们要向他学习。",
            "了不起，{topic_agent}的勤奋有了回报。",
        ],
        "critical": [
            "不过是运气好罢了，有什么好大惊小怪的。",
            "哼，一次大成功不代表什么。",
        ],
        "neutral": [
            "是吗？我也听说了。",
            "原来如此。",
        ],
    },
    "shared_memory": {
        "supportive": ["那次确实印象深刻。", "是啊，那天真的很特别。"],
        "critical": ["我不想提这件事。", "过去的事就别提了。"],
        "neutral": ["嗯。", "记得。"],
    },
    "casual": {
        "supportive": ["可不是嘛！", "哈哈，说得对。"],
        "critical": ["无聊。", "说点有意义的吧。"],
        "neutral": ["嗯，说得也是。", "还好吧。"],
    },
}
```

#### 3.9.5 结果写入

```python
def _write_to_memories(self, result: GroupConversationResult, participants, tick):
    """将群聊结果写入所有参与者的记忆"""
    participant_names = [p.state.name for p in participants]

    for agent in participants:
        other_names = [n for n in participant_names if n != agent.state.name]
        desc = f"在{agent.state.location_name}与{'、'.join(other_names)}闲聊"
        if result.topic:
            desc += f"，话题是{result.topic}"

        # 找到自己的发言
        my_turns = [t.content for t in result.turns if t.speaker_id == agent.id]
        if my_turns:
            desc += f"，我说了"{my_turns[0]}""

        agent.memory.write(
            description=desc,
            importance=result.importance,
            emotion=agent.emotion.dominant_emotion,
            involved_agents=[p.state.id for p in participants if p.state.id != agent.state.id],
            location=agent.state.location_name,
        )

    # 同时发布到黑板
    blackboard.publish(WorldEvent(
        tick=tick,
        event_type="group_chat",
        actors=[p.state.id for p in participants],
        location=participants[0].state.location_name,
        description=result.summary,
        data={"topic": result.topic, "turn_count": len(result.turns)},
        importance=result.importance,
        tags=["闲聊", participants[0].state.faction],
        faction_scope=f"faction:{participants[0].state.faction}",
    ))
```

#### 3.9.6 场景示例

```
tick 6 (午时, 自由活动): 令狐冲、岳灵珊、梁发在食堂
→ check_group_chat: 3人, 有T1(令狐冲), tick=6 ✓
→ 话题: 黑板上令狐冲今天的突破事件 (importance=8)
→ 发言顺序: 令狐冲(extraversion=0.9) → 岳灵珊(0.8) → 梁发(0.3)

Turn 1 - 令狐冲(supportive): "今天练剑感觉确实不错，多亏了小师妹陪我切磋。"
Turn 2 - 岳灵珊(supportive): "大师哥的剑法越来越厉害了！"
Turn 3 - 梁发(neutral): "嗯。"
  → 梁发 extraversion=0.3, 随机沉默 → 但还是说了一句短的

→ 写入三人记忆:
  令狐冲: "在食堂与岳灵珊、梁发闲聊，话题是今天练剑的事"
  岳灵珊: "在食堂与令狐冲、梁发闲聊..."
  梁发: "在食堂听令狐冲吹嘘..."

→ 发布到黑板: WorldEvent(event_type="group_chat", importance=5)
```

### 3.10 行为触发引擎 (Triggers) [新增]

> 参考《逆水寒》的 LLM Tool Call 机制。当 Agent 状态突破阈值时，自动触发游戏引擎动作。

#### 3.10.1 设计理念

逆水寒的经验：NPC 的大模型在愤怒值冲破阈值时，会调用游戏引擎的"悬赏接口"。OmniSim 不用 LLM，但可以用规则引擎实现同样的效果——**状态阈值 → 触发引擎动作**。

```
Agent 状态变化 → 检查是否触碰阈值
               → 触发预定义的引擎动作
               → 动作改变世界状态 / 其他 Agent 状态
               → 写入黑板 + 记忆
```

#### 3.10.2 触发规则表

```python
@dataclass
class TriggerRule:
    id: str
    name: str
    condition: callable       # 检查是否触发
    action: str               # 触发什么动作
    cooldown_ticks: int       # 冷却时间，防止重复触发
    priority: int             # 优先级（高优先级先检查）
    description: str          # 触发描述（用于记忆和叙事）

TRIGGER_RULES: list[TriggerRule] = [
    # ===== 情感触发 =====
    TriggerRule(
        id="rage_outburst",
        name="暴怒失控",
        condition=lambda agent: agent.emotion.valence < -0.7 and agent.emotion.arousal > 0.7,
        action="rage_outburst",
        cooldown_ticks=12,
        priority=9,
        description="{name}怒不可遏，当众发泄不满"
    ),
    TriggerRule(
        id="sad_withdraw",
        name="悲伤回避",
        condition=lambda agent: agent.emotion.valence < -0.5 and agent.emotion.arousal < 0.3,
        action="withdraw",
        cooldown_ticks=6,
        priority=7,
        description="{name}心情低落，独自离开"
    ),
    TriggerRule(
        id="joy_share",
        name="喜悦分享",
        condition=lambda agent: agent.emotion.valence > 0.7 and agent.emotion.arousal > 0.5,
        action="share_joy",
        cooldown_ticks=6,
        priority=5,
        description="{name}心情极好，主动找人分享"
    ),

    # ===== 关系触发 =====
    TriggerRule(
        id="report_betrayal",
        name="举报背叛",
        condition=lambda agent: any(
            r.trust < -60 and r.relation_type in ("师徒", "同门")
            for r in agent.relationships.values()
        ),
        action="report_to_authority",
        cooldown_ticks=24,
        priority=8,
        description="{name}发现{target}背叛师门，决定向掌门报告"
    ),
    TriggerRule(
        id="seek_revenge",
        name="寻仇",
        condition=lambda agent: any(
            r.trust < -80 and r.interaction_count > 3
            for r in agent.relationships.values()
        ),
        action="seek_revenge",
        cooldown_ticks=24,
        priority=10,
        description="{name}对{target}恨之入骨，伺机报复"
    ),

    # ===== 身体状态触发 =====
    TriggerRule(
        id="health_critical",
        name="重伤求医",
        condition=lambda agent: agent.state.health < 20,
        action="seek_medical",
        cooldown_ticks=6,
        priority=10,
        description="{name}伤势严重，急需治疗"
    ),
    TriggerRule(
        id="exhaustion",
        name="精疲力竭",
        condition=lambda agent: agent.state.energy < 10,
        action="forced_rest",
        cooldown_ticks=12,
        priority=9,
        description="{name}体力耗尽，不得不停下休息"
    ),
    TriggerRule(
        id="starving",
        name="饥肠辘辘",
        condition=lambda agent: agent.state.hunger > 70,
        action="seek_food",
        cooldown_ticks=6,
        priority=8,
        description="{name}饿得前胸贴后背，必须找吃的"
    ),

    # ===== 门派事件触发 =====
    TriggerRule(
        id="discipline_challenge",
        name="门派挑战",
        condition=lambda agent: (
            agent.state.tier == 1
            and agent.state.sword_skill > 70
            and any(r.trust < -40 for r in agent.relationships.values())
        ),
        action="challenge_rival",
        cooldown_ticks=36,
        priority=7,
        description="{name}决定公开向{target}发起挑战"
    ),
]
```

#### 3.10.3 触发动作执行

```python
class TriggerEngine:
    """行为触发引擎"""

    def __init__(self, blackboard: Blackboard):
        self.blackboard = blackboard
        self.cooldowns: dict[str, dict[str, int]] = {}  # agent_id → {rule_id → last_trigger_tick}

    def check_and_fire(self, agent: AgentBase, tick: int) -> list[str]:
        """检查所有触发规则，执行命中的动作"""
        triggered = []

        for rule in sorted(TRIGGER_RULES, key=lambda r: r.priority, reverse=True):
            # 冷却检查
            if self._on_cooldown(agent.state.id, rule.id, tick):
                continue

            # 条件检查
            if rule.condition(agent):
                self._execute_action(agent, rule, tick)
                self._set_cooldown(agent.state.id, rule.id, tick, rule.cooldown_ticks)
                triggered.append(rule.id)

        return triggered

    def _execute_action(self, agent: AgentBase, rule: TriggerRule, tick: int):
        """执行触发动作"""
        # 找到动作涉及的目标（关系触发需要）
        target = self._find_target(agent, rule)

        # 生成描述
        desc = rule.description.format(
            name=agent.state.name,
            target=target.state.name if target else "某人"
        )

        match rule.action:
            case "rage_outburst":
                self._rage_outburst(agent, target, tick, desc)
            case "withdraw":
                self._withdraw(agent, tick, desc)
            case "share_joy":
                self._share_joy(agent, tick, desc)
            case "report_to_authority":
                self._report(agent, target, tick, desc)
            case "seek_revenge":
                self._seek_revenge(agent, target, tick, desc)
            case "seek_medical":
                self._seek_medical(agent, tick, desc)
            case "forced_rest":
                self._forced_rest(agent, tick, desc)
            case "seek_food":
                self._seek_food(agent, tick, desc)
            case "challenge_rival":
                self._challenge(agent, target, tick, desc)
```

#### 3.10.4 动作实现

```python
    def _rage_outburst(self, agent, target, tick, desc):
        """暴怒失控：当场发泄"""
        # 修改计划为"发泄"
        agent.plan = agent.planner.revise_plan(agent.plan, tick, "发泄愤怒", agent.state.location_name)
        # 在场所有人 trust -= 3
        for nearby in agent._nearby_cache:
            rel = agent.relationships.get(nearby.id)
            if rel:
                rel.trust -= 3
        # 写入记忆和黑板
        agent.memory.write(desc, 8, tick, emotion="愤怒")
        self.blackboard.publish(WorldEvent(
            tick=tick, event_type="conflict",
            actors=[agent.state.id] + ([target.state.id] if target else []),
            location=agent.state.location_name,
            description=desc, data={"type": "rage"},
            importance=8, tags=["冲突", agent.state.faction],
            faction_scope=f"faction:{agent.state.faction}"
        ))
        # 消耗能量
        agent.state.energy = max(0, agent.state.energy - 15)

    def _withdraw(self, agent, tick, desc):
        """悲伤回避：离开人群，找安静地方"""
        agent.plan = agent.planner.revise_plan(agent.plan, tick, "独自沉思", "思过崖")
        agent.memory.write(desc, 5, tick, emotion="悲伤")

    def _share_joy(self, agent, tick, desc):
        """喜悦分享：主动找最近的人聊天"""
        # 找 trust 最高的 nearby
        best = max(agent._nearby_cache, key=lambda a: agent.relationships.get(a.id, Relationship("", "", "陌生人")).trust, default=None)
        if best:
            agent.plan = agent.planner.revise_plan(agent.plan, tick, f"找{best.state.name}分享喜悦", agent.state.location_name)
            agent.memory.write(desc, 5, tick, emotion="开心")
        else:
            agent.memory.write(f"{desc}，但周围没人", 4, tick, emotion="开心")

    def _report(self, agent, target, tick, desc):
        """向上级报告"""
        # 找门派中 role 包含"掌门"的 Agent
        # 发布到黑板，标记为"门派事务"
        self.blackboard.publish(WorldEvent(
            tick=tick, event_type="report",
            actors=[agent.state.id, target.state.id],
            description=desc,
            data={"reporter": agent.state.id, "suspect": target.state.id, "reason": "trust<-60"},
            importance=9, tags=["门派事务", "背叛"],
            faction_scope=f"faction:{agent.state.faction}"
        ))
        agent.memory.write(desc, 9, tick, emotion="愤怒")

    def _seek_medical(self, agent, tick, desc):
        """求医：改为前往药园"""
        agent.plan = agent.planner.revise_plan(agent.plan, tick, "寻求治疗", "药园")
        agent.memory.write(desc, 7, tick, emotion="恐惧")
        # 药园有治疗效果
        agent.state.health = min(100, agent.state.health + 20)

    def _forced_rest(self, agent, tick, desc):
        """强制休息"""
        agent.plan = agent.planner.revise_plan(agent.plan, tick, "休息", "弟子精舍")
        agent.state.energy = min(100, agent.state.energy + 30)
        agent.memory.write(desc, 5, tick, emotion="疲惫")

    def _seek_food(self, agent, tick, desc):
        """找吃的"""
        agent.plan = agent.planner.revise_plan(agent.plan, tick, "吃饭", "食堂")
        agent.state.hunger = max(0, agent.state.hunger - 30)
        agent.memory.write(desc, 5, tick, emotion="饥饿")

    def _challenge(self, agent, target, tick, desc):
        """发起挑战"""
        if target:
            # 触发战斗
            self.blackboard.publish(WorldEvent(
                tick=tick, event_type="challenge",
                actors=[agent.state.id, target.state.id],
                description=desc,
                data={"challenger": agent.state.id, "challenged": target.state.id},
                importance=9, tags=["挑战", agent.state.faction],
                faction_scope=f"faction:{agent.state.faction}"
            ))
            agent.memory.write(desc, 9, tick, emotion="愤怒")
```

#### 3.10.5 引擎集成

```python
# engine.py 的 tick() 中增加触发检查
class SimulationEngine:
    def tick(self):
        current_tick = self.time_system.advance()
        # ... 现有 Pass 1 / Pass 2 ...

        # Pass 3: 触发检查（在所有 agent 行动完成后）
        for agent in self.agents.values():
            triggered = self.trigger_engine.check_and_fire(agent, current_tick)
            if triggered:
                # 触发后可能需要重新执行受影响 agent 的 step
                pass

        # 清理黑板
        self.blackboard.tick_cleanup(current_tick)
```

#### 3.10.6 场景示例

```
场景: 劳德诺的信任崩塌触发

背景: 劳德诺(嵩山卧底)与令狐冲多次冲突
  - 劳德诺对令狐冲 trust: 45 → 40 → 35 → ... → -65 (多轮负面互动)

tick 7: 劳德诺 step 完成
  → trigger_engine.check_and_fire(劳德诺, 7)
  → "report_betrayal" 条件: trust < -60, relation_type="同门" → 命中! (priority=8)
  → 但劳德诺是卧底，report_to_authority 是报告给嵩山派
  → 黑板发布: WorldEvent(event_type="report", actors=["劳德诺", "令狐冲"],
      data={"reporter": "劳德诺", "suspect": "令狐冲"}, importance=9)
  → 劳德诺记忆: "决定向左盟主报告令狐冲背叛师门" (实际是倒打一耙)
  → 冷却 24 tick

场景: 令狐冲暴怒

tick 9: 令狐冲被岳不群当众训斥 → 连续负面事件
  → emotion: valence=-0.8, arousal=0.8
  → trigger_engine.check_and_fire(令狐冲, 9)
  → "rage_outburst" 条件命中
  → 令狐冲修改计划为"发泄愤怒"
  → 在场所有人 trust -= 3
  → 黑板发布冲突事件
  → energy -= 15
```

### 3.11 事件链引擎 (Event Chains) [新增]

> 当前系统的问题：战斗、社交、触发是三条独立的逻辑线，缺少统一的"事件→结果→连锁反应"链。
> 事件链引擎将所有事件统一为数据驱动的声明式定义，确保世界在没有 LLM 的情况下也能动态运转。

#### 3.11.1 核心数据结构

```python
from enum import Enum
from dataclasses import dataclass, field

class EventCategory(Enum):
    COMBAT = "combat"           # 武斗类
    SOCIAL = "social"           # 社交类
    TRAINING = "training"       # 修炼类
    POLITICAL = "political"     # 权谋类
    HEALTH = "health"           # 身体类
    ENVIRONMENT = "environment" # 环境类
    ROMANCE = "romance"         # 情感类

@dataclass
class Outcome:
    """一个可能的结果"""
    id: str
    label: str                              # 结果名：胜/负/平/重伤/战死...
    weight: float                           # 权重（非概率，根据属性动态调整）
    effects: dict                           # 状态变化 {"health": -20, "trust": +5}
    emotion_delta: dict                     # 情感变化 {"valence": +0.3, "arousal": +0.2}
    relationship_delta: dict                # 关系变化 {"trust": +5, "intimacy": +3}
    narrative: str                          # 叙事模板 "{winner}击败了{loser}，..."
    cascade: list[str] = field(default_factory=list)  # 连锁触发的事件 id

@dataclass
class EventTemplate:
    """事件模板 — 声明式定义"""
    id: str
    name: str
    category: EventCategory
    description: str                        # 事件描述模板
    preconditions: list[dict]               # 触发前置条件
    participants: dict                      # {"initiator": str, "target": str, "witnesses": str}
    resolution: dict                        # 判定方式 {"method": "dice"/"attribute_compare"/"weighted_random", ...}
    outcomes: list[Outcome]                 # 所有可能结果
    importance: int                         # 默认重要度
    cooldown_ticks: int = 6                 # 同类事件冷却

@dataclass
class ResolvedEvent:
    """一次已解决的事件实例"""
    template_id: str
    tick: int
    participants: dict                      # {role: agent_id}
    outcome: Outcome
    narrative: str                          # 填充后的叙事文本
    effects_applied: bool = False
```

#### 3.11.2 事件链引擎

```python
class EventChainEngine:
    """统一事件解析引擎"""

    def __init__(self, templates: list[EventTemplate]):
        self.templates: dict[str, EventTemplate] = {t.id: t for t in templates}
        self.cooldowns: dict[str, dict[str, int]] = {}  # agent_id → {template_id → last_tick}
        self.history: list[ResolvedEvent] = []

    def try_trigger(self, template_id: str, participants: dict,
                    tick: int, agents: dict) -> ResolvedEvent | None:
        """尝试触发一个事件"""
        tmpl = self.templates.get(template_id)
        if not tmpl:
            return None

        # 检查冷却
        if self._on_cooldown(tmpl, participants, tick):
            return None

        # 检查前置条件
        if not self._check_preconditions(tmpl, participants, agents):
            return None

        # 解析结果
        outcome = self._resolve(tmpl, participants, agents)

        # 应用效果
        self._apply_effects(outcome, participants, agents)

        # 生成叙事
        narrative = self._fill_narrative(outcome, participants, agents)

        # 记录
        resolved = ResolvedEvent(
            template_id=template_id,
            tick=tick,
            participants=participants,
            outcome=outcome,
            narrative=narrative,
        )
        self.history.append(resolved)
        self._set_cooldown(tmpl, participants, tick)

        # 连锁触发
        for cascade_id in outcome.cascade:
            self.try_trigger(cascade_id, participants, tick, agents)

        return resolved

    def _resolve(self, tmpl: EventTemplate, participants: dict, agents: dict) -> Outcome:
        """根据 resolution 配置判定结果"""
        method = tmpl.resolution["method"]

        if method == "dice":
            # 取发起者属性 roll 点
            initiator = agents[participants["initiator"]]
            attr = tmpl.resolution["attribute"]
            attr_val = getattr(initiator.state, attr, 50)
            penalty = tmpl.resolution.get("penalty", 0)
            result = roll(attr_val, penalty)
            return self._map_dice_to_outcome(result, tmpl.outcomes)

        elif method == "versus":
            # 双方对抗：各自 roll，比较结果
            a = agents[participants["initiator"]]
            b = agents[participants["target"]]
            a_val = getattr(a.state, tmpl.resolution["attribute_a"], 50)
            b_val = getattr(b.state, tmpl.resolution["attribute_b"], 50)
            result_a = roll(a_val, 0)
            result_b = roll(b_val, 0)
            return self._map_versus_to_outcome(result_a, result_b, a_val, b_val, tmpl.outcomes)

        elif method == "weighted_random":
            # 加权随机（受属性影响）
            weights = self._compute_weights(tmpl.outcomes, participants, agents)
            return random.choices(tmpl.outcomes, weights=weights, k=1)[0]

    def _map_dice_to_outcome(self, dice_result, outcomes: list[Outcome]) -> Outcome:
        """骰子结果映射到 Outcome"""
        mapping = {"大成功": 0, "成功": 1, "失败": -1, "大失败": -2}
        # 按 outcome 的 weight 排序，weight 正=好结果，负=坏结果
        sorted_outcomes = sorted(outcomes, key=lambda o: o.weight, reverse=True)
        # 大成功取最好的，大失败取最差的
        degree = dice_result.degree
        if degree == "大成功":
            return sorted_outcomes[0]
        elif degree == "成功":
            return sorted_outcomes[1] if len(sorted_outcomes) > 1 else sorted_outcomes[0]
        elif degree == "失败":
            return sorted_outcomes[-2] if len(sorted_outcomes) > 1 else sorted_outcomes[-1]
        else:  # 大失败
            return sorted_outcomes[-1]

    def _map_versus_to_outcome(self, dice_a, dice_b, val_a, val_b, outcomes) -> Outcome:
        """对抗结果映射"""
        score_a = val_a - (dice_a.raw if dice_a.raw > dice_a.target else 0)
        score_b = val_b - (dice_b.raw if dice_b.raw > dice_b.target else 0)
        sorted_outcomes = sorted(outcomes, key=lambda o: o.weight, reverse=True)

        diff = score_a - score_b
        if diff > 20:
            return sorted_outcomes[0]   # 压倒性胜利
        elif diff > 0:
            return sorted_outcomes[1] if len(sorted_outcomes) > 2 else sorted_outcomes[0]  # 艰难胜利
        elif diff > -20:
            return sorted_outcomes[-2] if len(sorted_outcomes) > 2 else sorted_outcomes[-1]  # 惜败
        else:
            return sorted_outcomes[-1]  # 惨败
```

#### 3.11.3 完整事件表

##### A. 武斗事件 (COMBAT)

**A1. 切磋 (spar)**

```python
EventTemplate(
    id="combat_spar",
    name="切磋",
    category=EventCategory.COMBAT,
    description="{initiator}与{target}在{location}切磋武艺",
    preconditions=[
        {"check": "same_location"},
        {"check": "relationship.trust", "min": 10},
        {"check": "location.allows", "action": "spar"},
    ],
    participants={"initiator": "发起者", "target": "对手", "witnesses": "旁观者"},
    resolution={"method": "versus", "attribute_a": "sword_skill", "attribute_b": "sword_skill"},
    outcomes=[
        Outcome(id="spar_win", label="胜", weight=10,
                effects={"energy": -5, "sword_skill": 1},
                emotion_delta={"valence": 0.2},
                relationship_delta={"trust": 2, "intimacy": 3},
                narrative="{initiator}技高一筹，{target}心服口服",
                cascade=[]),
        Outcome(id="spar_close", label="势均力敌", weight=5,
                effects={"energy": -8},
                emotion_delta={"valence": 0.1},
                relationship_delta={"intimacy": 2},
                narrative="两人旗鼓相当，难分伯仲",
                cascade=[]),
        Outcome(id="spar_lose", label="负", weight=1,
                effects={"energy": -10},
                emotion_delta={"valence": -0.15},
                relationship_delta={"trust": 1, "intimacy": 2},
                narrative="{target}技高一筹，{initiator}虽败犹荣",
                cascade=[]),
        Outcome(id="spar_injury", label="意外受伤", weight=-5,
                effects={"energy": -15, "health": -10},
                emotion_delta={"valence": -0.3, "arousal": 0.2},
                relationship_delta={"trust": -3, "intimacy": -2},
                narrative="切磋中{target}失手，{initiator}受了伤",
                cascade=["health_injury"]),
    ],
    importance=5,
    cooldown_ticks=3,
)
```

**A2. 决斗 (duel)**

```python
EventTemplate(
    id="combat_duel",
    name="决斗",
    category=EventCategory.COMBAT,
    description="{initiator}向{target}发起正式决斗！",
    preconditions=[
        {"check": "relationship.trust", "max": -30},
        {"check": "location.allows", "action": "spar"},
        {"check": "initiator.energy", "min": 30},
    ],
    participants={"initiator": "挑战方", "target": "应战方", "witnesses": "旁观者"},
    resolution={"method": "versus", "attribute_a": "sword_skill", "attribute_b": "sword_skill"},
    outcomes=[
        Outcome(id="duel_win_decisive", label="压倒性胜利", weight=10,
                effects={"energy": -10, "sword_skill": 2},
                emotion_delta={"valence": 0.4, "arousal": 0.3},
                relationship_delta={"trust": 10},
                narrative="{initiator}一剑封喉，{target}毫无还手之力，当众认输",
                cascade=["social_humiliation"]),
        Outcome(id="duel_win_close", label="险胜", weight=5,
                effects={"energy": -20, "health": -5},
                emotion_delta={"valence": 0.2, "arousal": 0.2},
                relationship_delta={"trust": 5},
                narrative="激战数十回合后，{initiator}侥幸获胜",
                cascade=[]),
        Outcome(id="duel_lose", label="败北", weight=-5,
                effects={"energy": -25, "health": -15},
                emotion_delta={"valence": -0.4, "arousal": 0.3},
                relationship_delta={"trust": -5, "intimacy": -5},
                narrative="{initiator}不敌{target}，败下阵来",
                cascade=[]),
        Outcome(id="duel_severe_injury", label="重伤", weight=-10,
                effects={"energy": -30, "health": -35},
                emotion_delta={"valence": -0.6, "arousal": 0.4},
                relationship_delta={"trust": -10, "intimacy": -8},
                narrative="{target}一招得手，{initiator}重伤倒地！",
                cascade=["health_severe_injury"]),
        Outcome(id="duel_death", label="战死", weight=-20,
                effects={"health": -100},
                emotion_delta={},
                relationship_delta={"trust": -50, "intimacy": -50},
                narrative="{target}失手将{initiator}击杀！一条人命就此消逝！",
                cascade=["political_death_aftermath"]),
        Outcome(id="duel_flee", label="落荒而逃", weight=-15,
                effects={"energy": -15},
                emotion_delta={"valence": -0.5, "arousal": 0.5},
                relationship_delta={"trust": -15, "intimacy": -10},
                narrative="{initiator}见势不妙，转身逃走，颜面尽失",
                cascade=["social_humiliation", "political_seeking_revenge"]),
    ],
    importance=9,
    cooldown_ticks=24,
)
```

**A3. 偷袭 (ambush)**

```python
EventTemplate(
    id="combat_ambush",
    name="偷袭",
    category=EventCategory.COMBAT,
    description="{initiator}在{location}对{target}发动偷袭！",
    preconditions=[
        {"check": "relationship.trust", "max": -50},
        {"check": "target.perception", "condition": "lower_than_initiator"},
    ],
    participants={"initiator": "偷袭者", "target": "受害者"},
    resolution={"method": "dice", "attribute": "perception", "penalty": 20},
    outcomes=[
        Outcome(id="ambush_success", label="偷袭成功", weight=10,
                effects={"health": -25},
                emotion_delta={"valence": -0.5, "arousal": 0.6},
                relationship_delta={"trust": -30, "intimacy": -20},
                narrative="{initiator}暗中出手，{target}猝不及防，身受重伤！",
                cascade=["health_severe_injury", "political_seeking_revenge"]),
        Outcome(id="ambush_dodged", label="被躲开", weight=0,
                effects={"energy": -10},
                emotion_delta={"valence": -0.2, "arousal": 0.4},
                relationship_delta={"trust": -20, "intimacy": -15},
                narrative="{target}察觉到杀意，堪堪躲过偷袭！",
                cascade=["combat_duel"]),
        Outcome(id="ambush_countered", label="反杀", weight=-10,
                effects={"health": -20},
                emotion_delta={"valence": -0.4, "arousal": 0.5},
                relationship_delta={"trust": -25},
                narrative="{target}早有防备，反将{initiator}制服！",
                cascade=["political_arrest"]),
    ],
    importance=9,
    cooldown_ticks=36,
)
```

##### B. 社交事件 (SOCIAL)

**B1. 争吵 (argument)**

```python
EventTemplate(
    id="social_argument",
    name="争吵",
    category=EventCategory.SOCIAL,
    description="{initiator}与{target}在{location}发生激烈争吵",
    preconditions=[
        {"check": "same_location"},
        {"check": "relationship.trust", "max": 40},
        {"check": "emotion.valence", "max": -0.2},  # 至少有一方心情不好
    ],
    participants={"initiator": "挑起者", "target": "对方", "witnesses": "旁观者"},
    resolution={"method": "versus", "attribute_a": "charisma", "attribute_b": "charisma"},
    outcomes=[
        Outcome(id="arg_reconcile", label="和解", weight=5,
                effects={},
                emotion_delta={"valence": 0.1},
                relationship_delta={"trust": 3, "intimacy": 2},
                narrative="两人争执一番后，各退一步，握手言和",
                cascade=[]),
        Outcome(id="arg_cold_war", label="冷战", weight=0,
                effects={},
                emotion_delta={"valence": -0.15},
                relationship_delta={"trust": -5, "intimacy": -3},
                narrative="双方互不相让，不欢而散",
                cascade=[]),
        Outcome(id="arg_rift", label="决裂", weight=-10,
                effects={},
                emotion_delta={"valence": -0.3, "arousal": 0.3},
                relationship_delta={"trust": -15, "intimacy": -10},
                narrative="争执升级，{initiator}与{target}当众翻脸！",
                cascade=["political_seeking_revenge"]),
        Outcome(id="arg_physical", label="动武", weight=-15,
                effects={"energy": -10},
                emotion_delta={"valence": -0.4, "arousal": 0.5},
                relationship_delta={"trust": -20, "intimacy": -15},
                narrative="言语不合，{initiator}对{target}动了手！",
                cascade=["combat_duel"]),
    ],
    importance=7,
    cooldown_ticks=6,
)
```

**B2. 交心 (heart_to_heart)**

```python
EventTemplate(
    id="social_heart_to_heart",
    name="交心",
    category=EventCategory.SOCIAL,
    description="{initiator}与{target}在{location}倾心交谈",
    preconditions=[
        {"check": "same_location"},
        {"check": "relationship.intimacy", "min": 50},
        {"check": "location.allows", "action": "secret_chat"},
    ],
    participants={"initiator": "主动方", "target": "倾诉对象"},
    resolution={"method": "dice", "attribute": "charisma", "penalty": 10},
    outcomes=[
        Outcome(id="hth_bond", label="关系深化", weight=10,
                effects={},
                emotion_delta={"valence": 0.3},
                relationship_delta={"trust": 10, "intimacy": 10},
                narrative="两人推心置腹，{target}对{initiator}更加信任",
                cascade=[]),
        Outcome(id="hth_secret", label="吐露秘密", weight=5,
                effects={},
                emotion_delta={"valence": 0.2},
                relationship_delta={"trust": 8, "intimacy": 8},
                narrative="{initiator}向{target}吐露了一个深藏已久的秘密",
                cascade=["political_secret_learned"]),
        Outcome(id="hth_misunderstand", label="误会", weight=-5,
                effects={},
                emotion_delta={"valence": -0.1},
                relationship_delta={"trust": -3, "intimacy": -2},
                narrative="{target}似乎误解了{initiator}的意思，气氛变得尴尬",
                cascade=[]),
        Outcome(id="hth_betrayal", label="背叛信任", weight=-15,
                effects={},
                emotion_delta={"valence": -0.5, "arousal": 0.4},
                relationship_delta={"trust": -30, "intimacy": -20},
                narrative="{target}将{initiator}的真心话当成了把柄！",
                cascade=["political_secret_exposed"]),
    ],
    importance=7,
    cooldown_ticks=12,
)
```

**B3. 告密 (informing)**

```python
EventTemplate(
    id="social_informing",
    name="告密",
    category=EventCategory.SOCIAL,
    description="{initiator}向{authority}告发{target}",
    preconditions=[
        {"check": "relationship.trust", "target": "target", "max": -30},
        {"check": "role", "authority": "掌门"},
    ],
    participants={"initiator": "告密者", "target": "被告发者", "authority": "掌门/上级"},
    resolution={"method": "dice", "attribute": "charisma", "penalty": 20},
    outcomes=[
        Outcome(id="inform_believed", label="采信", weight=10,
                effects={},
                emotion_delta={"valence": 0.3},
                relationship_delta={},
                narrative="{authority}听信了{initiator}的话，决定追究{target}",
                cascade=["political_punishment"]),
        Outcome(id="inform_doubted", label="怀疑", weight=-5,
                effects={},
                emotion_delta={"valence": -0.1},
                relationship_delta={"trust": -5},
                narrative="{authority}将信将疑，没有立即表态",
                cascade=[]),
        Outcome(id="inform_rejected", label="驳回", weight=-10,
                effects={},
                emotion_delta={"valence": -0.2, "arousal": 0.2},
                relationship_delta={"trust": -10},
                narrative="{authority}认为{initiator}是在搬弄是非，严厉训斥",
                cascade=[]),
        Outcome(id="inform_counter", label="反咬", weight=-15,
                effects={},
                emotion_delta={"valence": -0.4, "arousal": 0.4},
                relationship_delta={"trust": -20},
                narrative="{target}当场揭穿{initiator}的谎言，反而让{initiator}陷入困境",
                cascade=["political_punishment"]),
    ],
    importance=8,
    cooldown_ticks=24,
)
```

##### C. 修炼事件 (TRAINING)

**C1. 闭关 (seclusion)**

```python
EventTemplate(
    id="training_seclusion",
    name="闭关",
    category=EventCategory.TRAINING,
    description="{initiator}在{location}闭关修炼",
    preconditions=[
        {"check": "location", "in": ["思过崖", "藏经阁"]},
        {"check": "initiator.energy", "min": 50},
        {"check": "initiator.inner_power", "min": 30},
    ],
    participants={"initiator": "修炼者"},
    resolution={"method": "dice", "attribute": "talent", "penalty": 30},
    outcomes=[
        Outcome(id="secl_breakthrough", label="突破", weight=10,
                effects={"inner_power": 5, "sword_skill": 3, "energy": -30},
                emotion_delta={"valence": 0.5, "arousal": 0.3},
                relationship_delta={},
                narrative="{initiator}闭关悟道，武功大进！内力和剑法都有突破",
                cascade=[]),
        Outcome(id="secl_progress", label="精进", weight=5,
                effects={"inner_power": 2, "sword_skill": 1, "energy": -20},
                emotion_delta={"valence": 0.2},
                relationship_delta={},
                narrative="{initiator}闭关有所领悟，修为精进",
                cascade=[]),
        Outcome(id="secl_stagnant", label="停滞", weight=0,
                effects={"energy": -15},
                emotion_delta={"valence": -0.1},
                relationship_delta={},
                narrative="闭关数日，却毫无进展",
                cascade=[]),
        Outcome(id="secl_deviation", label="走火入魔", weight=-15,
                effects={"health": -20, "inner_power": -5, "energy": -40},
                emotion_delta={"valence": -0.5, "arousal": 0.5},
                relationship_delta={},
                narrative="{initiator}修炼出错，走火入魔！经脉受损！",
                cascade=["health_qi_deviation"]),
    ],
    importance=7,
    cooldown_ticks=24,
)
```

**C2. 传功 (teaching)**

```python
EventTemplate(
    id="training_teaching",
    name="传功",
    category=EventCategory.TRAINING,
    description="{master}在{location}向{disciple}传授武艺",
    preconditions=[
        {"check": "same_location"},
        {"check": "relationship.relation_type", "in": ["师徒", "父女"]},
        {"check": "master.role", "in": ["掌门", "掌门夫人", "师娘"]},
    ],
    participants={"master": "师父", "disciple": "弟子"},
    resolution={"method": "dice", "attribute": "wisdom", "penalty": 15},
    outcomes=[
        Outcome(id="teach_master", label="青出于蓝", weight=10,
                effects={"disciple.sword_skill": 5, "disciple.inner_power": 3},
                emotion_delta={"valence": 0.3},
                relationship_delta={"trust": 5, "intimacy": 5},
                narrative="{disciple}天赋异禀，将{master}所授融会贯通",
                cascade=[]),
        Outcome(id="teach_learn", label="学成", weight=5,
                effects={"disciple.sword_skill": 2, "disciple.inner_power": 1},
                emotion_delta={"valence": 0.15},
                relationship_delta={"trust": 3, "intimacy": 3},
                narrative="{disciple}认真听讲，剑法有所提升",
                cascade=[]),
        Outcome(id="teach_fail", label="不成器", weight=-5,
                effects={},
                emotion_delta={"valence": -0.2},
                relationship_delta={"trust": -3, "intimacy": -2},
                narrative="{disciple}心不在焉，{master}大失所望",
                cascade=[]),
        Outcome(id="teach_rebel", label="叛逆", weight=-10,
                effects={},
                emotion_delta={"valence": -0.3, "arousal": 0.3},
                relationship_delta={"trust": -10, "intimacy": -8},
                narrative="{disciple}公然质疑{master}的教法，师徒起了冲突",
                cascade=["social_argument"]),
    ],
    importance=6,
    cooldown_ticks=6,
)
```

**C3. 偷学 (steal_learning)**

```python
EventTemplate(
    id="training_steal",
    name="偷学",
    category=EventCategory.TRAINING,
    description="{initiator}偷窥{target}练功，试图偷学招式",
    preconditions=[
        {"check": "relationship.trust", "max": 40},
        {"check": "initiator.perception", "min": 50},
        {"check": "location", "in": ["练武场", "华山大殿"]},
    ],
    participants={"initiator": "偷学者", "target": "被偷学者"},
    resolution={"method": "dice", "attribute": "perception", "penalty": 25},
    outcomes=[
        Outcome(id="steal_success", label="学会", weight=10,
                effects={"sword_skill": 2},
                emotion_delta={"valence": 0.2},
                relationship_delta={},
                narrative="{initiator}暗中观摩，领悟了几招",
                cascade=[]),
        Outcome(id="steal_partial", label="一知半解", weight=3,
                effects={"sword_skill": 1},
                emotion_delta={},
                relationship_delta={},
                narrative="{initiator}看了个大概，似懂非懂",
                cascade=[]),
        Outcome(id="steal_caught", label="被发现", weight=-10,
                effects={},
                emotion_delta={"valence": -0.3, "arousal": 0.4},
                relationship_delta={"trust": -15, "intimacy": -10},
                narrative="{target}发现{initiator}在偷窥练功，勃然大怒",
                cascade=["social_argument"]),
        Outcome(id="steal_caught_punish", label="被抓惩罚", weight=-15,
                effects={"health": -10},
                emotion_delta={"valence": -0.4, "arousal": 0.4},
                relationship_delta={"trust": -25, "intimacy": -15},
                narrative="{target}当场拿下{initiator}，上报掌门处理",
                cascade=["political_punishment"]),
    ],
    importance=7,
    cooldown_ticks=12,
)
```

##### D. 权谋事件 (POLITICAL)

**D1. 逼宫 (usurpation)**

```python
EventTemplate(
    id="political_usurpation",
    name="逼宫",
    category=EventCategory.POLITICAL,
    description="{initiator}在{location}公然挑战{authority}的权威",
    preconditions=[
        {"check": "initiator.tier", "max": 1},
        {"check": "initiator.sword_skill", "min": 70},
        {"check": "relationship.trust", "target": "authority", "max": -40},
        {"check": "witnesses.count", "min": 3},
    ],
    participants={"initiator": "挑战者", "authority": "当权者", "witnesses": "门人"},
    resolution={"method": "versus", "attribute_a": "charisma", "attribute_b": "charisma"},
    outcomes=[
        Outcome(id="usurp_success", label="逼宫成功", weight=10,
                effects={},
                emotion_delta={"valence": 0.5, "arousal": 0.5},
                relationship_delta={"trust": 20},
                narrative="{initiator}声威大振，{authority}不得不让步",
                cascade=["political_power_shift"]),
        Outcome(id="usurp_fail_exile", label="失败被逐", weight=-15,
                effects={},
                emotion_delta={"valence": -0.6, "arousal": 0.3},
                relationship_delta={"trust": -30, "intimacy": -25},
                narrative="{authority}震怒，将{initiator}逐出师门",
                cascade=["political_exile"]),
        Outcome(id="usurp_fail_imprison", label="失败被囚", weight=-20,
                effects={"health": -10},
                emotion_delta={"valence": -0.7, "arousal": 0.2},
                relationship_delta={"trust": -40, "intimacy": -30},
                narrative="{authority}将{initiator}拿下，关押在思过崖",
                cascade=["health_imprisonment"]),
        Outcome(id="usurp_compromise", label="妥协", weight=3,
                effects={},
                emotion_delta={"valence": 0.1},
                relationship_delta={"trust": 5},
                narrative="双方各退一步，达成暂时妥协",
                cascade=[]),
    ],
    importance=10,
    cooldown_ticks=72,
)
```

**D2. 出走 (departure)**

```python
EventTemplate(
    id="political_departure",
    name="出走",
    category=EventCategory.POLITICAL,
    description="{initiator}决定离开华山派",
    preconditions=[
        {"check": "relationship.trust", "target": "faction_leader", "max": 20},
        {"check": "emotion.valence", "max": -0.3},
    ],
    participants={"initiator": "出走者", "faction_leader": "掌门"},
    resolution={"method": "weighted_random"},
    outcomes=[
        Outcome(id="depart_persuaded", label="被挽留", weight=6,
                effects={},
                emotion_delta={"valence": 0.2},
                relationship_delta={"trust": 5, "intimacy": 5},
                narrative="{faction_leader}出面挽留，{initiator}决定再留下看看",
                cascade=[]),
        Outcome(id="depart_forbidden", label="被禁止", weight=3,
                effects={},
                emotion_delta={"valence": -0.3, "arousal": 0.3},
                relationship_delta={"trust": -10},
                narrative="{faction_leader}严令禁止{initiator}离开",
                cascade=[]),
        Outcome(id="depart_success", label="成功离开", weight=0,
                effects={},
                emotion_delta={"valence": 0.1},
                relationship_delta={"trust": -15, "intimacy": -10},
                narrative="{initiator}收拾行囊，悄然离开华山",
                cascade=["political_exile"]),
        Outcome(id="depart_pursued", label="被追杀", weight=-10,
                effects={"health": -10},
                emotion_delta={"valence": -0.5, "arousal": 0.6},
                relationship_delta={"trust": -30, "intimacy": -20},
                narrative="{initiator}试图下山，却被拦截！双方动起手来",
                cascade=["combat_duel"]),
    ],
    importance=9,
    cooldown_ticks=48,
)
```

**D3. 惩罚 (punishment)**

```python
EventTemplate(
    id="political_punishment",
    name="门规处置",
    category=EventCategory.POLITICAL,
    description="{authority}在{location}对{target}执行门规处置",
    preconditions=[
        {"check": "role", "authority": "掌门"},
    ],
    participants={"authority": "掌门", "target": "受罚者", "witnesses": "门人"},
    resolution={"method": "weighted_random"},
    outcomes=[
        Outcome(id="punish_warning", label="训斥", weight=5,
                effects={},
                emotion_delta={"valence": -0.15},
                relationship_delta={"trust": -5},
                narrative="{authority}当众严厉训斥{target}",
                cascade=[]),
        Outcome(id="punish_demotion", label="降级", weight=0,
                effects={},
                emotion_delta={"valence": -0.3},
                relationship_delta={"trust": -10, "intimacy": -5},
                narrative="{target}被降级处罚",
                cascade=[]),
        Outcome(id="punish_seclusion", label="罚面壁", weight=-5,
                effects={},
                emotion_delta={"valence": -0.4},
                relationship_delta={"trust": -15, "intimacy": -10},
                narrative="{target}被罚往思过崖面壁思过",
                cascade=["training_seclusion"]),
        Outcome(id="punish_expel", label="逐出师门", weight=-15,
                effects={},
                emotion_delta={"valence": -0.6, "arousal": 0.5},
                relationship_delta={"trust": -40, "intimacy": -30},
                narrative="{authority}宣布将{target}逐出华山派！",
                cascade=["political_exile"]),
    ],
    importance=9,
    cooldown_ticks=24,
)
```

**D4. 密谋 (conspiracy)**

```python
EventTemplate(
    id="political_conspiracy",
    name="密谋",
    category=EventCategory.POLITICAL,
    description="{initiator}与{accomplice}在{location}秘密密谋",
    preconditions=[
        {"check": "location.allows", "action": "secret_chat"},
        {"check": "relationship.trust", "target": "accomplice", "min": 30},
    ],
    participants={"initiator": "主谋", "accomplice": "共谋者"},
    resolution={"method": "dice", "attribute": "wisdom", "penalty": 25},
    outcomes=[
        Outcome(id="conspire_success", label="密谋成功", weight=10,
                effects={},
                emotion_delta={"valence": 0.2},
                relationship_delta={"trust": 5, "intimacy": 5},
                narrative="两人达成秘密协议，暗中布局",
                cascade=[]),
        Outcome(id="conspire_refused", label="被拒绝", weight=-5,
                effects={},
                emotion_delta={"valence": -0.2},
                relationship_delta={"trust": -10, "intimacy": -5},
                narrative="{accomplice}不愿参与，令{initiator}十分不满",
                cascade=[]),
        Outcome(id="conspire_exposed", label="暴露", weight=-15,
                effects={},
                emotion_delta={"valence": -0.5, "arousal": 0.5},
                relationship_delta={"trust": -20},
                narrative="密谋被人撞破！消息迅速传开",
                cascade=["social_informing"]),
    ],
    importance=8,
    cooldown_ticks=24,
)
```

##### E. 身体事件 (HEALTH)

**E1. 伤病 (injury)**

```python
EventTemplate(
    id="health_injury",
    name="受伤",
    category=EventCategory.HEALTH,
    description="{initiator}受了伤",
    preconditions=[{"check": "health", "max": 70}],
    participants={"initiator": "伤者"},
    resolution={"method": "weighted_random"},
    outcomes=[
        Outcome(id="injury_recover", label="自行恢复", weight=5,
                effects={"health": 5},
                emotion_delta={"valence": 0.1},
                relationship_delta={},
                narrative="伤势不重，休息几日便好",
                cascade=[]),
        Outcome(id="injury_treat", label="求医治愈", weight=3,
                effects={"health": 15},
                emotion_delta={"valence": 0.15},
                relationship_delta={},
                narrative="{initiator}到药园敷药疗伤，恢复了不少",
                cascade=[]),
        Outcome(id="injury_worsen", label="伤势恶化", weight=-10,
                effects={"health": -15},
                emotion_delta={"valence": -0.3, "arousal": 0.2},
                relationship_delta={},
                narrative="伤势不见好转，反而恶化了",
                cascade=[]),
    ],
    importance=6,
    cooldown_ticks=6,
)

# 重伤版本（由决斗/偷袭连锁触发）
EventTemplate(
    id="health_severe_injury",
    name="重伤",
    category=EventCategory.HEALTH,
    description="{initiator}身受重伤，急需救治！",
    preconditions=[{"check": "health", "max": 40}],
    participants={"initiator": "伤者"},
    resolution={"method": "weighted_random"},
    outcomes=[
        Outcome(id="severe_treated", label="得到救治", weight=5,
                effects={"health": 20},
                emotion_delta={"valence": 0.2},
                relationship_delta={},
                narrative="经药园紧急救治，{initiator}脱离了危险",
                cascade=[]),
        Outcome(id="severe_linger", label="伤势缠绵", weight=-5,
                effects={"health": -5, "energy": -20},
                emotion_delta={"valence": -0.3},
                relationship_delta={},
                narrative="{initiator}伤势反复，卧床不起",
                cascade=[]),
        Outcome(id="severe_death", label="不治身亡", weight=-20,
                effects={"health": -100},
                emotion_delta={},
                relationship_delta={},
                narrative="{initiator}伤重不治，撒手人寰",
                cascade=["political_death_aftermath"]),
    ],
    importance=9,
    cooldown_ticks=12,
)
```

**E2. 走火入魔 (qi_deviation)**

```python
EventTemplate(
    id="health_qi_deviation",
    name="走火入魔",
    category=EventCategory.HEALTH,
    description="{initiator}经脉逆行，走火入魔！",
    preconditions=[],
    participants={"initiator": "患者"},
    resolution={"method": "weighted_random"},
    outcomes=[
        Outcome(id="deviation_recover", label="自行恢复", weight=3,
                effects={"inner_power": -5, "health": -10},
                emotion_delta={"valence": 0.1},
                relationship_delta={},
                narrative="{initiator}凭借深厚内力，硬生生将逆行的真气压了回去",
                cascade=[]),
        Outcome(id="deviation_damage", label="经脉受损", weight=-10,
                effects={"inner_power": -15, "health": -20, "sword_skill": -5},
                emotion_delta={"valence": -0.4},
                relationship_delta={},
                narrative="{initiator}经脉受损，功力大退",
                cascade=[]),
        Outcome(id="deviation_madness", label="神志不清", weight=-15,
                effects={"health": -30, "inner_power": -10},
                emotion_delta={"valence": -0.6, "arousal": 0.8},
                relationship_delta={},
                narrative="{initiator}走火入魔，神志不清，胡乱攻击周围的人！",
                cascade=["combat_ambush"]),
    ],
    importance=10,
    cooldown_ticks=36,
)
```

##### F. 环境事件 (ENVIRONMENT)

**F1. 外敌入侵 (invasion)**

```python
EventTemplate(
    id="env_invasion",
    name="外敌入侵",
    category=EventCategory.ENVIRONMENT,
    description="有外敌闯入{location}！",
    preconditions=[{"check": "scripted_trigger"}],  # 由 YAML 事件流触发
    participants={"enemies": "入侵者", "defenders": "守卫者"},
    resolution={"method": "versus", "attribute_a": "sword_skill", "attribute_b": "sword_skill"},
    outcomes=[
        Outcome(id="invade_repelled", label="击退", weight=5,
                effects={},
                emotion_delta={"valence": 0.3},
                relationship_delta={"trust": 5, "intimacy": 3},
                narrative="华山弟子齐心协力，将来犯之敌击退",
                cascade=[]),
        Outcome(id="invade_stalemate", label="僵持", weight=0,
                effects={},
                emotion_delta={"valence": -0.1, "arousal": 0.2},
                relationship_delta={},
                narrative="双方激战，一时难分胜负",
                cascade=[]),
        Outcome(id="invade_breach", label="失守", weight=-10,
                effects={"health": -10},
                emotion_delta={"valence": -0.4, "arousal": 0.4},
                relationship_delta={"trust": -5},
                narrative="敌势浩大，华山弟子节节败退",
                cascade=["health_severe_injury"]),
    ],
    importance=10,
    cooldown_ticks=0,  # 脚本事件不冷却
)
```

##### G. 连锁终端事件（只由 cascade 触发）

```python
# 政治后果
EventTemplate(id="political_exile", name="流放", ..., outcomes=[
    Outcome(id="exile_wander", ..., cascade=["env_encounter"]),
    Outcome(id="exile_return", ..., cascade=[]),
])
EventTemplate(id="political_death_aftermath", name="死亡善后", ..., outcomes=[
    Outcome(id="death_mourning", ..., cascade=[]),
    Outcome(id="death_revenge_oath", ..., cascade=["political_seeking_revenge"]),
])
EventTemplate(id="political_seeking_revenge", name="誓报仇", ..., outcomes=[
    Outcome(id="revenge_prepare", ..., cascade=[]),
    Outcome(id="revenge_immediate", ..., cascade=["combat_ambush"]),
])
EventTemplate(id="political_secret_learned", name="获知秘密", ..., outcomes=[
    Outcome(id="secret_keep", ..., cascade=[]),
    Outcome(id="secret_use", ..., cascade=["social_informing"]),
])
EventTemplate(id="social_humiliation", name="当众受辱", ..., outcomes=[
    Outcome(id="humiliation_endure", ..., cascade=[]),
    Outcome(id="humiliation_rage", ..., cascade=["combat_duel"]),
    Outcome(id="humiliation_depart", ..., cascade=["political_departure"]),
])
```

#### 3.11.4 事件连锁图谱

```
                        ┌─ spar_injury ──────── health_injury
combat_spar ────────────┤
                        └─ (正常结束)

                        ┌─ duel_win ──────── social_humiliation ──┬─ endure
                        │                                       ├─ rage → combat_duel (循环)
combat_duel ────────────┤                                       └─ depart → political_departure
                        ├─ duel_severe ──── health_severe ──┬─ treated
                        │                                    ├─ linger
                        │                                    └─ death → political_death_aftermath ──┬─ mourning
                        │                                                                             └─ revenge → combat_ambush
                        ├─ duel_death ────── political_death_aftermath
                        └─ duel_flee ─────── social_humiliation + political_seeking_revenge

combat_ambush ──────────┬─ success ─── health_severe + political_seeking_revenge
                        ├─ dodged ──── combat_duel
                        └─ countered ── political_arrest

social_argument ────────┬─ reconcile
                        ├─ cold_war
                        ├─ rift ──────── political_seeking_revenge
                        └─ physical ──── combat_duel

social_heart_to_heart ──┬─ bond
                        ├─ secret ────── political_secret_learned ──┬─ keep
                        │                                              └─ use → social_informing
                        └─ betrayal ─── political_secret_exposed → political_punishment

training_seclusion ─────┬─ breakthrough
                        ├─ progress
                        ├─ stagnant
                        └─ deviation ──── health_qi_deviation ──┬─ recover
                                                                  ├─ damage
                                                                  └─ madness → combat_ambush

political_punishment ───┬─ warning
                        ├─ demotion
                        ├─ seclusion ───── training_seclusion
                        └─ expel ──────── political_exile

political_usurpation ───┬─ success ────── political_power_shift
                        ├─ fail_exile ─── political_exile
                        ├─ fail_imprison ─ health_imprisonment
                        └─ compromise
```

#### 3.11.5 引擎集成

```python
# engine.py 中
class SimulationEngine:
    def __init__(self):
        ...
        self.event_chain = EventChainEngine(EVENT_TEMPLATES)

    def tick(self):
        current_tick = self.time_system.advance()
        # Pass 1: 位置更新
        # Pass 2: Agent 执行 step
        # Pass 3: 行为触发
        # Pass 4: 事件链检查 [新增]
        for agent in self.agents.values():
            self._check_event_chains(agent, current_tick)

    def _check_event_chains(self, agent, tick):
        """检查是否有事件链应该触发"""
        for tmpl in self.event_chain.templates.values():
            if self._should_trigger(tmpl, agent, tick):
                self.event_chain.try_trigger(
                    tmpl.id,
                    self._resolve_participants(tmpl, agent),
                    tick,
                    self.agents,
                )
```

## 验证

### 基础系统
- Agent 在 16×16 地图上从 A 点移动到 B 点，路径合理，速度受地形影响
- Agent 执行"练功"行为，技能经验增加
- 两个 Agent 交互（打招呼），双方记忆和好感变化

### 江湖事件传播
- 骰子大成功事件 → 当事人写入 gossip_worthy 记忆
- 社交互动时 → 八卦从当事人传到第三方 → 第三方获得二手记忆
- 三手之后记忆 importance 降到 1 → 不再传播
- 高克明收到令狐冲的八卦后 → 因 trust 低产生嫉妒情绪

### 世界黑板
- 重要事件自动写入黑板（结构化数据）
- Agent 查询黑板获取世界事件
- 劳德诺（卧底）从黑板获取华山派内部情报
- 一天结束时黑板提供当日大事摘要

### 多人场景对话
- 3 人在食堂触发群聊
- 令狐冲（高外向）先发言，梁发（低外向）简短回应或沉默
- 群聊结果写入所有参与者记忆 + 黑板

### 行为触发
- Agent 连续负面事件 → 情绪跌破阈值 → 触发暴怒/回避
- Agent 体力耗尽 → 自动强制休息
- 劳德诺 trust 跌破 -60 → 触发"举报"事件写入黑板
- 同一触发 12 tick 冷却期内不重复触发

### 事件链完整场景

**场景1: 切磋 → 意外受伤 → 求医**
```
令狐冲 vs 高克明 切磋
→ roll(sword_skill vs sword_skill) → 大失败(高克明)
→ outcome: spar_injury → cascade: health_injury
→ 令狐冲获得: "切磋中失手，高克明受了伤" (health -10, trust -3)
→ 高克明 health=40 → 触发 health_injury
→ outcome: injury_treat → 高克明前往药园治疗
→ 高克明记忆: "令狐冲练剑不分轻重，害我受伤，还好药园有药"
```

**场景2: 密谋 → 暴露 → 告密 → 惩罚 → 出走**
```
劳德诺 + 梁发 在弟子精舍密谋
→ roll(wisdom, 25) → 大失败
→ outcome: conspire_exposed → cascade: social_informing
→ 梁发记忆: "密谋被人撞破！"

→ 梁发向岳不群告密劳德诺
→ roll(charisma, 20) → 成功
→ outcome: inform_believed → cascade: political_punishment
→ 岳不群记忆: "梁发报告劳德诺密谋不轨"

→ 岳不群处置劳德诺
→ outcome: punish_expel → cascade: political_exile
→ 劳德诺被逐出华山派
→ 黑板事件: "劳德诺被逐出华山派，罪名：密谋不轨" (importance=10)
```

**场景3: 闭关 → 走火入魔 → 神志不清 → 偷袭队友**
```
令狐冲在思过崖闭关
→ roll(talent, 30) → 大失败
→ outcome: secl_deviation → cascade: health_qi_deviation
→ 令狐冲 health=-20, inner_power=-5

→ health_qi_deviation 判定
→ outcome: deviation_madness → cascade: combat_ambush
→ 令狐冲神志不清，向最近的 Agent 发动偷袭
→ 假设岳灵珊在附近
→ 偷袭判定 → 令狐冲 perception 低（走火入魔状态）
→ outcome: ambush_dodged → cascade: combat_duel
→ 岳灵珊躲开，令狐冲恢复一丝理智

→ 记忆: 令狐冲 "闭关走火入魔，恍惚间差点伤到小师妹，事后羞愧万分"
→ 关系变化: trust -5, intimacy -3
```

**场景4: 完整决斗链**
```
令狐冲 trust=-50 对高克明 → 触发 combat_duel
→ versus(sword_skill vs sword_skill)
→ 令狐冲 55 vs 高克明 25 → 压倒性胜利
→ outcome: duel_win_decisive → cascade: social_humiliation

→ 高克明当众受辱
→ 高克明 personality.agreeableness=0.3 (记仇)
→ outcome: humiliation_rage → cascade: combat_duel (反向挑战)
→ 但高克明 sword_skill=25 远不如令狐冲 55
→ 冷却 24 tick 后才能再次挑战

→ 高克明反思: "令狐冲仗着武功欺人太甚，我一定要报复！"
→ trust -30 → 总 trust 到 -60
→ 下次自由时间可能触发: social_informing (向师父告状)
```
