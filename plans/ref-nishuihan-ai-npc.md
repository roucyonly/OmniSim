# 逆水寒 AI NPC 技术方案参考 & OmniSim 落地设计

> 本文档分析网易《逆水寒》手游的 AI NPC 技术实践，提炼可借鉴的设计思路，映射到 OmniSim 的架构改进中。

---

## 一、逆水寒 AI NPC 技术概览

### 1.1 系统规模

- 游戏 400+ NPC 加载了智能引擎
- 玩家自创"江湖友人"突破 500 万
- 依托阿里云大模型 + 分布式算力，支撑千万级用户交互

### 1.2 四层技术架构

```
┌───────────────────────────────────────────────┐
│              多模态交互层                        │
│  实时语音 / 文本对话 / 情绪感知 / AI动画生成       │
├───────────────────────────────────────────────┤
│              记忆与认知层                        │
│  短期对话记忆 / 长期RAG记忆 / 性格记忆 / 情感记忆  │
├───────────────────────────────────────────────┤
│              大模型推理层                        │
│  武侠专用GPT / 后训练定制 / 多模型竞技(5大模型)    │
├───────────────────────────────────────────────┤
│              平台与工具链层                      │
│  网易有灵AOP平台 / "易生诸相"多模态AI              │
└───────────────────────────────────────────────┘
```

### 1.3 核心能力拆解

| 能力 | 逆水寒实现 | 关键技术 |
|------|-----------|---------|
| **个性化** | 每个 NPC 有独特性格、喜好、目的、背景故事 | 角色卡 + 性格向量 |
| **记忆** | 记住对话内容、穿着、去过的地方、做过的事 | 高性能专用数据库 + RAG |
| **关系** | 性格、关系类型、对玩家印象、好感度 | 关系矩阵 + 好感度数值 |
| **情感** | NPC 能感知玩家情绪并做出回应 | 情绪识别 + 情感反馈系统 |
| **主动行为** | NPC 主动发起对话、触发支线 | 事件驱动 + 意图生成 |
| **陪伴** | 陪玩、打本、闲逛、发"朋友圈" | AI companion 范式 |
| **UGC创作** | 玩家输入文字生成角色+动画+短视频 | "剧组模式" 一句话创作 |
| **数字分身** | 好友不在线时可与其 AI 分身互动 | 行为克隆 + 性格建模 |

---

## 二、关键设计提炼 → OmniSim 借鉴点

### 2.1 分层记忆系统（高优先级）

**逆水寒做法**：记忆分层存储——短期（对话上下文）、长期（RAG + 向量库）、性格记忆、情感记忆。所有记忆存入专用高性能数据库。

**OmniSim 现状**：MemoryStream 是平铺结构，只有 `description + importance + tick`，查询靠关键词匹配。

**改进方案**：

```
MemoryStream
├── 工作记忆 (Working Memory)     ← 当前 tick 的感知缓冲区
│   └── 最近 3-5 tick 的原始感知，未加工
│
├── 短期记忆 (Short-term Memory)  ← 当前对话/交互上下文
│   └── 当前交互的对话历史、场景描述
│
├── 长期记忆 (Long-term Memory)   ← 核心记忆流（已有）
│   ├── 每条记忆增加：emotion_tag (情绪标签)
│   ├── 每条记忆增加：involved_agents (涉及的其他角色)
│   └── 每条记忆增加：location (发生地点)
│
└── 压缩记忆 (Compressed Memory)  ← 反思产物的摘要
    └── 每 6 tick 反思生成的高层认知
```

**具体改动**：
- `MemoryEntry` 增加 `emotion: str`、`involved_agents: list[str]`、`location: str` 字段
- `query()` 方法增加按 `involved_agents` 过滤（查"和令狐冲相关的记忆"）
- 新增 `query_by_emotion(emotion)` 方法（查"我最近开心的事"）
- 反思产物存入压缩记忆，与原始记忆分开索引

### 2.2 情感系统（高优先级）

**逆水寒做法**：NPC 有情绪状态，能感知玩家情绪并做出情感反馈。情绪影响 NPC 对话语气和行为选择。

**OmniSim 现状**：没有显式的情感模型。性格是一段文字描述，不影响数值行为。

**改进方案**：

```python
@dataclass
class EmotionalState:
    """情感状态 - 每个 Agent 维护"""
    valence: float       # 效价 [-1, 1]：负面(-1) → 正面(1)
    arousal: float       # 唤醒度 [0, 1]：平静(0) → 激动(1)
    dominant_emotion: str  # 当前主导情绪：开心/愤怒/悲伤/恐惧/惊讶/厌恶/信任

    # 情感偏移来源（用于反思）
    emotion_log: list[tuple[int, str, float]]  # (tick, 触发事件, valence变化)
```

**情感影响链**：
```
事件发生 → emotion_shift() 更新情感状态
         → 影响骰子判定（心情好 → 社交加成，心情差 → 社交惩罚）
         → 影响对话风格（LLM prompt 注入当前情绪）
         → 影响计划偏好（悲伤时更倾向独处）
         → 每 tick 自然衰减（回归中性状态）
```

**与骰子系统联动**：
- 正面情绪 → `bonus += arousal * 5`（兴奋时发挥更好）
- 负面情绪 → `penalty += abs(valence) * 3`（沮丧时容易失误）
- 大成功/大失败本身也触发情绪变化

### 2.3 关系图谱（高优先级）

**逆水寒做法**：NPC 面板显示 性格、关系类型、对玩家印象、好感度。

**OmniSim 现状**：没有关系系统。Agent 之间通过 `nearby` 列表感知彼此，但不记录历史关系。

**改进方案**：

```python
@dataclass
class Relationship:
    """两个 Agent 之间的关系"""
    target_id: str
    relation_type: str     # 师徒/同门/恋人/敌对/陌生人
    trust: float           # 信任度 [-100, 100]
    intimacy: float        # 亲密值 [0, 100]
    impression: str        # 一句话印象（由反思生成）
    last_interaction_tick: int
    interaction_count: int
```

**关系变化规则**：
- 同一地点社交 → intimacy += 2
- 骰子大成功互动 → trust += 5, intimacy += 5
- 骰子大失败互动 → trust -= 5
- 超过 12 tick 无互动 → intimacy 自然衰减 -1
- 信任度影响：对话内容（LLM prompt 中注入关系状态）、协作意愿（骰子 bonus/penalty）

### 2.4 性格结构化（中优先级）

**逆水寒做法**：NPC 有"独特性格"，后训练定制化。

**OmniSim 现状**：性格是一段自由文本 `"洒脱不羁，豪爽义气，嗜酒如命"`，仅用于 LLM prompt。

**改进方案**：增加性格维度向量，与自由文本并存：

```python
@dataclass
class PersonalityVector:
    """性格维度 - 影响行为偏好和骰子判定"""
    extraversion: float     # 外向性 [0, 1]：影响社交主动性
    agreeableness: float    # 宜人性 [0, 1]：影响合作/冲突倾向
    conscientious: float    # 尽责性 [0, 1]：影响计划执行稳定性
    openness: float         # 开放性 [0, 1]：影响冒险/创新行为
    stability: float        # 情绪稳定性 [0, 1]：影响情感波动幅度
```

**用途**：
- 高外向性 → 更可能在计划中选择社交行为
- 低宜人性 → 更容易产生冲突
- 低尽责性 → 偶尔偏离计划（重规划概率更高）
- 高开放性 → 遇到新事物时探索概率更高
- 低稳定性 → 情感波动更大（arousal 衰减更慢）

**MVP 阶段**：从 huashan-mvp.yaml 的 `personality` 文本 + `core_motivation` 推导出默认值，手工校准关键角色。

### 2.5 主动行为系统（中优先级）

**逆水寒做法**：NPC 主动发起对话、触发支线任务。

**OmniSim 现状**：Agent 严格按计划执行，没有主动发起交互的机制。

**改进方案**：

在 `step()` 中增加 **主动意图判定**：

```python
def _check_proactive_intent(self, nearby_agents):
    """检查是否主动发起交互"""
    for agent in nearby_agents:
        rel = self.relationships.get(agent.id)
        if not rel:
            # 陌生人：外向性高 → 可能打招呼
            if self.personality.extraversion > 0.7:
                return ("greet", agent)
            continue

        # 熟人：根据关系和情绪决定
        if rel.intimacy > 60 and self.emotion.valence > 0.3:
            return ("chat", agent)  # 心情好 + 关系好 → 主动聊天
        if rel.trust < -30:
            return ("confront", agent)  # 敌对关系 → 可能挑衅
    return None
```

**与计划系统的关系**：
- 如果当前计划是"自由活动"（tick 6, 9），允许主动行为覆盖计划
- 如果当前计划是具体任务（练功、吃饭），只在到达后执行主动行为
- 主动行为触发后写入记忆，可能引发对方的计划修订

### 2.6 对话上下文构建（低优先级，Plan 6 增强）

**逆水寒做法**：NPC 对话时带入完整记忆、性格、关系、情绪上下文。

**OmniSim 现状**：Plan 6 的对话 prompt 有基本结构，但缺少情感和关系上下文。

**改进方案**（为 Plan 6 预留）：

```
对话 Prompt 结构：
├── 角色身份：name, role, personality_text, personality_vector
├── 当前状态：location, status, emotional_state
├── 关系上下文：与对方的 relationship（trust, intimacy, impression）
├── 记忆上下文：query(involved_agents=[对方id]) 的 top 5 记忆
├── 近期反思：最近一条与对方相关的反思
└── 对话历史：当前交互的 short-term memory
```

---

## 三、OmniSim 改动优先级

| 优先级 | 改动 | 影响范围 | 预计工作量 |
|--------|------|---------|-----------|
| P0 | 记忆增强（emotion_tag, involved_agents） | agents/memory.py, agents/base.py | 小 |
| P0 | 情感系统 EmotionalState | 新增 agents/emotion.py, 改 agents/base.py | 中 |
| P0 | 关系图谱 Relationship | 新增 agents/relationship.py, 改 agents/base.py, engine.py | 中 |
| P1 | 性格结构化 PersonalityVector | 改 agents/base.py (AgentState) | 小 |
| P1 | 主动行为判定 | 改 agents/base.py (step方法) | 小 |
| P2 | 对话上下文增强 | Plan 6 (llm/prompts/) | 中 |
| P2 | 多模态交互 | 前端 + 后端，远期目标 | 大 |

---

## 四、逆水寒给我们的启示

### 4.1 核心教训

1. **记忆是灵魂**：玩家最强烈的体验来自 NPC "记得我"。OmniSim 的记忆流是核心资产，值得持续投入。

2. **情感 = 沉浸感**：单纯的对话 AI 不够，NPC 需要有情绪反应才能让玩家"感到真实"。骰子系统 + 情感系统 是 OmniSim 的差异化优势。

3. **关系是粘性**：NPC 之间的关系网络让世界"活"起来。华山派师徒、师兄妹的关系变化是涌现叙事的核心素材。

4. **主动性 = 惊喜**：NPC 主动发起交互是"涌现"的关键触发器。逆水寒的 NPC 会主动找你聊天，OmniSim 也应让令狐冲主动找小师妹切磋。

5. **分层控制成本**：逆水寒用后训练 + 多模型竞速控制成本。OmniSim 的 T1/T2/T3 分层 + 骰子系统已经是很好的成本控制策略，情感和关系系统主要是规则引擎驱动，LLM 成本增加有限。

### 4.2 OmniSim 的差异化

逆水寒是商业 MMO，NPC 服务于玩家体验。OmniSim 是沙盒模拟器，NPC 之间**自主交互产生涌现叙事**。这决定了：

- 我们更重视 **NPC-to-NPC 关系**（不只是 NPC-to-Player）
- 骰子系统带来的**不确定性叙事**是独有特色
- 反思系统驱动的**认知演化**（"我开始怀疑师父了"）是核心看点
- 造物主通过天道之子的**间接影响**是独特玩法

---

## 五、参考资料

- [《逆水寒》手游AI负责人刘畅 2025云栖大会分享](https://fuxi.163.com/database/2750)
- [逆水寒引入了 AI 系统之后发生了什么 - 知乎](https://zhuanlan.zhihu.com/p/716332083)
- [网易伏羲揭秘AI Agent驱动游戏玩法革新](https://lingdong.fuxi.163.com/database/2403)
- [全球最大AI竞技场 — 五大国产模型化身武侠少女](https://hub.baai.ac.cn/view/42740)
- [AI重塑游戏：供给革新与需求跃迁（PDF报告）](https://pdf.dfcfw.com/pdf/H3_AP202603251820744415_1.pdf)
- [自捏江湖友人玩法介绍](https://bbs.4399.cn/thread-view-tid-46145777)
- [网易《逆水寒》手游玩家自创智能NPC数量突破500万](https://www.donews.com/news/detail/4/4514036.html)
