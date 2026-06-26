# Relationship Event OS — Architecture Document v3.0

> Everything is Event. Everything else is Projection.
> The Event Log is the only Source of Truth.

---

## 第一章：核心哲学

### 1.1 为什么不是 Memory Engine？

Memory 是**单向的**——AI 记住你的信息，像一个笔记本。

Relationship 是**双向的、动态的、有温度的**。

| | Memory Engine | Relationship OS |
|---|---|---|
| 本质 | 数据库 | 关系操作系统 |
| 问法 | "小雨喜欢什么？" | "我现在应该怎么和小雨说话？" |
| 时间 | 不感知时间 | 深度感知时间流逝 |
| 变化 | 信息不变就一直存着 | 关系每天都在变化 |
| 输出 | 事实 | **上下文 + 感知 + 趋势** |

Memory 回答的是"我知道什么"。
Relationship OS 回答的是"我应该理解什么"。

### 1.2 AI 为什么应该拥有"人与人关系模型"？

因为**人类不是靠信息活着的，是靠关系活着的。**

一个 AI 记住了"小雨喜欢奶茶"——这是信息。
一个 AI 知道"你和小雨三天没说话了，她最近考试压力大，今天应该主动问一下"——这是关系。

人与人之间的关系不是一张表，是一条**河流**——它流动、变化、有涨有落。

AI 如果只做 Memory，它是一个**档案管理员**。
AI 如果做 Relationship OS，它是一个**懂人心的参谋**。

### 1.3 Everything is Event, Everything else is Projection

这是整个系统的架构基石。

- **Event Log** 是唯一的 Source of Truth
- **Memory、Relationship、Time、Emotion、Growth、Reminder** 全是 Projection
- **Entity Snapshot** 也是 Projection，不是架构中的特殊层
- **Context Builder** 也是一个 Projection，不是特殊模块
- 新增功能 = 新增事件类型 + 新增 Projection，不改核心架构

```
传统模块化思维：
  Memory 是一个模块，Relationship 是一个模块，Time 是一个模块...
  每个模块有自己的存储、自己的逻辑

事件驱动思维：
  Event Log 是唯一的存储
  Memory、Relationship、Time、Emotion、Reminder 全是 Projection
  没有模块，只有"事件类型"和"投影逻辑"
```

### 1.4 Relationship OS 的定位

**Relationship OS 是一个服务，不是一个人。**

它被任何 AI 调用（DeepSeek、GPT、Claude、Qwen）。它不替 AI 做决策，它输出的是**对关系的理解和整理**（Relationship Intelligence），最终决策由调用方 AI 完成。

类比：
- Relationship OS = 军事情报系统（分析、整理、建议）
- 调用方 AI = 将军（结合全局信息做最终决策）

---

## 第二章：系统架构

### 2.1 架构全景

```
┌─────────────────────────────────────────────────────┐
│              Relationship Event OS                    │
│        Everything is Event,                          │
│        Everything else is Projection                 │
├─────────────────────────────────────────────────────┤
│                                                      │
│  Layer 1: Event Log（事件日志）                       │
│  ┌──────────────────────────────────────────────┐   │
│  │ append-only, immutable, JSONL                │   │
│  │                                              │   │
│  │ events.jsonl — 唯一的数据文件                 │   │
│  │                                              │   │
│  │ Event Types:                                 │   │
│  │   person      人物事件                        │   │
│  │   chat        聊天事件                        │   │
│  │   fact        事实/记忆事件                    │   │
│  │   emotion     情绪事件                        │   │
│  │   relation    关系变化事件                     │   │
│  │   milestone   里程碑事件                      │   │
│  │   growth      成长事件                        │   │
│  │   reminder    提醒事件                        │   │
│  │   social      社交关系事件（v3+）              │   │
│  │   ...         未来新增 = 新事件类型            │   │
│  └──────────────────────┬───────────────────────┘   │
│                         │                            │
│                   replay + compute                    │
│                         │                            │
│  Layer 2: Projection Engine（投影引擎）               │
│  ┌──────────────────────▼───────────────────────┐   │
│  │ Projection = f(events) → view                │   │
│  │                                              │   │
│  │ Built-in Projections:                        │   │
│  │   person_profile    人物画像                  │   │
│  │   relationship      关系状态                  │   │
│  │   time_context      时间上下文                │   │
│  │   emotion_summary   情绪摘要                  │   │
│  │   growth_timeline   成长时间线                │   │
│  │   reminders         提醒列表                  │   │
│  │   conversation      对话历史                  │   │
│  │   context           AI 上下文（最核心）        │   │
│  │   ...               未来新增 = 新 Projection  │   │
│  └──────────────────────┬───────────────────────┘   │
│                         │                            │
│                   query + format                     │
│                         │                            │
│  Layer 3: MCP Layer（接口层）                         │
│  ┌──────────────────────▼───────────────────────┐   │
│  │                                              │   │
│  │  Write Tools（写入事件）:                      │   │
│  │    add_person / remember / add_chat /        │   │
│  │    add_emotion / update_relation /           │   │
│  │    add_milestone / add_growth                │   │
│  │                                              │   │
│  │  Read Tools（查询投影）:                       │   │
│  │    get_context / get_person / get_events /   │   │
│  │    get_reminders / search                    │   │
│  │                                              │   │
│  │  Resources:                                  │   │
│  │    relationship://people                     │   │
│  │    relationship://stats                      │   │
│  └──────────────────────────────────────────────┘   │
│                                                      │
│  Layer 4: Provider Interface                         │
│  ┌──────────────────────────────────────────────┐   │
│  │ CC Switch / OpenAI Compatible / Offline       │   │
│  └──────────────────────────────────────────────┘   │
│                                                      │
└─────────────────────────────────────────────────────┘
```

### 2.2 和之前设计的对比

| 设计 | 模块数 | 数据文件 | 扩展方式 | 一致性 |
|------|--------|---------|---------|--------|
| v1 模块化 | 8 模块 | 4 个 JSON | 加模块 | 可能不一致 |
| v2 Event+Entity+Context | 3 层 | 1 JSONL + 1 JSON | 加事件+投影 | 一致 |
| **v3 Event-first** | **0 模块** | **1 个 JSONL** | **加事件类型+投影** | **天然一致** |

---

## 第三章：Event 模型

### 3.1 Event 数据结构

**只有一种数据结构：Event。所有数据都以 Event 形式存储。**

```python
class Event:
    id: str                    # UUID，全局唯一
    timestamp: datetime        # 事件发生时间
    type: str                  # 事件类型
    person: str                # 关联的人物（可选，部分事件不关联人物）
    data: dict                 # 事件数据（类型不同，结构不同）
    source: str                # 来源：user_input / ai_detected / system
```

### 3.2 事件类型设计

#### person — 人物事件

```json
{
    "type": "person",
    "person": "小雨",
    "data": {
        "action": "create",
        "birthday": "1998-06-15",
        "nickname": "小鱼儿",
        "tags": ["口腔同学", "室友"],
        "notes": "喜欢画画，温柔"
    }
}
```

用于：创建人物、更新人物信息。每个 `person` 事件是对人物属性的增量更新。

#### chat — 聊天事件

```json
{
    "type": "chat",
    "person": "小雨",
    "data": {
        "role": "user",
        "content": "今天一起吃饭吧"
    }
}
```

用于：记录每一次对话消息。`role` 可以是 `user`（用户说的）或 `assistant`（AI 回复的）。

#### fact — 事实/记忆事件

```json
{
    "type": "fact",
    "person": "小雨",
    "data": {
        "content": "喜欢喝抹茶拿铁",
        "category": "preference",
        "importance": 8
    }
}
```

category 枚举值：
- `general` — 通用信息
- `preference` — 喜好
- `birthday` — 生日相关
- `hobby` — 爱好
- `story` — 故事/经历
- `important` — 重要信息
- `secret` — 秘密

importance: 1-10，越高越重要。

#### emotion — 情绪事件

```json
{
    "type": "emotion",
    "person": "小雨",
    "data": {
        "valence": 0.8,
        "arousal": 0.6,
        "label": "开心",
        "context": "情人节收到礼物"
    }
}
```

- `valence`: -1.0 到 +1.0（负面到正面）
- `arousal`: 0 到 1（平静到激动）
- `label`: 人类可读的情绪标签（开心/难过/焦虑/平静/兴奋/愤怒/压力）
- `context`: 触发这个情绪的场景

情绪数据的来源：
- 用户主动告知（"我今天心情不好"）
- AI 从聊天内容推断（调用方 AI 判断后调用 `add_emotion` 存入）
- 事件推断（考试 → 可能压力大）

#### relation — 关系变化事件

```json
{
    "type": "relation",
    "person": "小雨",
    "data": {
        "stage": "暧昧",
        "delta": 15,
        "event": "第一次约会"
    }
}
```

- `stage`: 新的关系阶段（可选，如果未变化则不填）
- `delta`: 好感度变化（正数升温，负数降温）
- `event`: 触发这个变化的事件描述

阶段枚举值：`陌生人` / `认识` / `聊天` / `熟悉` / `朋友` / `重要的人` / `长期陪伴` / `暧昧` / `热恋` / `稳定` / `冷淡` / `分手`

#### milestone — 关系里程碑事件

```json
{
    "type": "milestone",
    "person": "小雨",
    "data": {
        "milestone_type": "first_date",
        "description": "第一次一起看电影",
        "significance": 9
    }
}
```

milestone_type 枚举值：
- `first_meet` — 第一次见面
- `first_chat` — 第一次聊天
- `first_deep_talk` — 第一次深聊
- `first_secret` — 第一次分享秘密
- `first_fight` — 第一次吵架
- `first_reconciliation` — 第一次和好
- `first_date` — 第一次约会
- `first_trip` — 第一次一起旅行
- `first_collaboration` — 第一次合作
- `custom` — 自定义里程碑

significance: 1-10，对关系的影响程度。

**Milestone 和 Event 的区别：**

| | 普通事件（relation event） | Milestone |
|---|---|---|
| 性质 | 日常 | 永久标记 |
| 数量 | 很多 | 很少 |
| 影响 | 暂时改变好感度 | 永久改变关系本质 |
| 能否回退 | 能（吵架可以和好） | 不能（分享过的秘密收不回来） |

#### growth — 成长事件

```json
{
    "type": "growth",
    "person": "我自己",
    "data": {
        "title": "学会 Python",
        "category": "skill",
        "description": "从零开始学编程",
        "impact_level": 7,
        "date": "2025-12"
    }
}
```

category 枚举值：
- `skill` — 学会了什么
- `experience` — 经历了什么
- `milestone` — 人生节点
- `achievement` — 完成了什么
- `realization` — 想通了什么

impact_level: 1-10，对这个人的人生影响。

#### reminder — 提醒事件

```json
{
    "type": "reminder",
    "person": "小雨",
    "data": {
        "reminder_type": "birthday",
        "trigger_date": "2025-06-15",
        "message": "小雨生日",
        "recurring": true,
        "acknowledged": false
    }
}
```

用于：创建提醒、记录提醒确认。

### 3.3 存储格式：JSONL

所有事件存储在一个文件 `data/events.jsonl` 中，每行一个 JSON 对象：

```jsonl
{"id":"a1","timestamp":"2025-01-15T10:00:00","type":"person","person":"小雨","data":{"action":"create","birthday":"1998-06-15","tags":["口腔同学","室友"]},"source":"user_input"}
{"id":"a2","timestamp":"2025-01-15T14:30:00","type":"chat","person":"小雨","data":{"role":"user","content":"今天一起吃饭吧"},"source":"user_input"}
{"id":"a3","timestamp":"2025-01-15T14:31:00","type":"chat","person":"小雨","data":{"role":"assistant","content":"好呀，吃什么？"},"source":"ai_detected"}
{"id":"a4","timestamp":"2025-01-20T09:00:00","type":"fact","person":"小雨","data":{"content":"喜欢喝抹茶拿铁","category":"preference","importance":8},"source":"user_input"}
{"id":"a5","timestamp":"2025-02-14T20:00:00","type":"emotion","person":"小雨","data":{"valence":0.8,"label":"开心","context":"情人节收到礼物"},"source":"user_input"}
{"id":"a6","timestamp":"2025-03-01T10:00:00","type":"relation","person":"小雨","data":{"stage":"暧昧","delta":20,"event":"第一次约会"},"source":"user_input"}
{"id":"a7","timestamp":"2025-03-01T10:00:00","type":"milestone","person":"小雨","data":{"milestone_type":"first_date","description":"第一次一起看电影","significance":9},"source":"user_input"}
```

**为什么是 JSONL 而不是数据库？**

- append-only，永远只追加，不会修改
- 人类可读，可以直接打开查看
- 可以 git 追踪
- 不需要额外依赖（SQLite / PostgreSQL）
- 单用户系统，数据量在几千到几万行，完全够用

---

## 第四章：Projection 系统

### 4.1 什么是 Projection？

**Projection = 一个函数，输入事件流，输出一个视图。**

```python
class Projection:
    """所有 Projection 的基类"""
    def project(self, events: list[Event]) -> dict:
        """输入事件流，输出视图"""
        ...
```

Projection 不存储任何数据。每次被调用时，从 Event Log 重新计算。
Event Log 变了，Projection 的输出自然变。

### 4.1.1 Projection 独立性原则

**Projection 之间不要互相依赖。**

```
正确：所有 Projection 都只读 Event Log
  Event Log
      │
  ┌───┼───┬───┬───┐
  ▼   ▼   ▼   ▼   ▼
 Person Relationship Time Emotion Growth
  │     │      │     │      │
  ▼     ▼      ▼     ▼      ▼
 ...   ...   ...   ...   ...

错误：Projection 之间互相调用
  Emotion Projection → 调用 → Relationship Projection ❌
```

好处：
- 删掉一个 Projection，其他全部还能运行
- 每个 Projection 可以独立测试
- 未来可以并行计算多个 Projection

### 4.1.2 扩展接口原则

Projection 的 dataclass 应该预留扩展字段（默认 None），而不是以后加字段导致 API 变化。

```python
class TimeContextProfile:
    # 当前实现
    silence: SilenceInfo | None = None
    density_7d: DensityInfo | None = None

    # v2.5 扩展接口（当前 None，未来填充）
    rhythm: dict | None = None          # 节奏模式
    flow: dict | None = None            # 关系流向
    density_detail: dict | None = None  # 密度增强
```

API 一旦稳定，以后升级成本很低——None 变成具体值，外部调用者无需改代码。

### 4.2 内置 Projections

#### person_profile — 人物画像投影

输入：所有 `person` + `fact` 事件
输出：

```python
{
    "小雨": {
        "name": "小雨",
        "nickname": "小鱼儿",
        "birthday": "1998-06-15",
        "tags": ["口腔同学", "室友"],
        "notes": "喜欢画画，温柔",
        "first_met": "2025-01-15",
        "facts": [
            {"content": "喜欢喝抹茶拿铁", "category": "preference", "importance": 8},
            {"content": "生日是6月15日", "category": "birthday", "importance": 9}
        ],
        "total_interactions": 47
    }
}
```

#### relationship — 关系状态投影

输入：所有 `relation` + `chat` + `milestone` 事件
输出：

```python
{
    "小雨": {
        "stage": "暧昧",
        "base_chemistry": 85,
        "decay_chemistry": 72,
        "decay_rate": 0.02,
        "floor": 20,
        "last_contact": "2025-06-20",
        "trend": "升温中",
        "milestones": [
            {"type": "first_date", "description": "第一次一起看电影", "date": "2025-03-01"},
            {"type": "first_secret", "description": "分享了家庭故事", "date": "2025-04-15"}
        ],
        "recent_events": [
            {"content": "一起吃了火锅", "date": "2025-06-20"},
            {"content": "送了生日礼物", "date": "2025-06-15"}
        ]
    }
}
```

**关系衰减模型：**

```
effective_chemistry = base_chemistry × decay_factor + floor

decay_factor = 1 / (1 + λ × days_since_last_contact)
```

不同关系类型的衰减参数：

| 关系类型 | λ（衰减速率） | floor（最低值） |
|---------|-------------|--------------|
| 家人 | 0.001 | 60 |
| 挚友 | 0.005 | 30 |
| 普通朋友 | 0.02 | 10 |
| 暧昧 | 0.05 | 5 |
| 同事 | 0.03 | 5 |

**关键设计：`base_chemistry` 是事件推导出的值，`decay_chemistry` 是运行时计算的值。** 每次有新事件（聊天、约会、吵架），`base_chemistry` 更新，`last_contact` 重置，衰减归零。

**关系生命周期（状态图，不是线性）：**

```
陌生人 → 认识 → 聊天 → 熟悉 → 朋友 → 重要的人 → 长期陪伴
                          ↓
                      暧昧 → 热恋 → 稳定
                          ↓
                      吵架 → 冷淡 → 分手
```

关系升级触发条件：

| 升级 | 触发条件 |
|------|---------|
| 陌生人 → 认识 | 记录第一次见面 |
| 认识 → 聊天 | 第一次主动发起对话 |
| 聊天 → 熟悉 | 累计聊天超过一定量 / 分享过私人信息 |
| 熟悉 → 朋友 | 共同经历（一起做某事 / 互相帮助） |
| 朋友 → 重要的人 | 分享过秘密 / 在困难时互相支持 |
| 重要的人 → 长期陪伴 | 持续互动超过一定时间 + 共同成长 |

#### time_context — 时间上下文投影

输入：所有 `chat` + `person` + `milestone` + `reminder` 事件
输出：

```python
{
    "小雨": {
        "last_contact_days": 5,
        "last_contact_label": "有一阵子没联系了",
        "frequency_trend": "最近两周频率下降40%",
        "rhythm": {
            "normal_interval": 2,
            "current_interval": 5,
            "alert": true,
            "message": "偏离正常聊天节奏"
        },
        "upcoming": [
            {"type": "birthday", "date": "2025-06-20", "days_until": 5, "label": "生日还有5天"},
            {"type": "anniversary", "date": "2025-07-15", "days_until": 40, "label": "认识纪念日还有40天"}
        ],
        "relationship_age": 187,
        "interaction_count": 47,
        "avg_weekly_frequency": 3.2
    }
}
```

**Time Engine 的五个维度：**

1. **间隔感知（Interval）**
   - 0-1小时: "刚聊完"
   - 1-6小时: "今天聊过"
   - 6-24小时: "今天还没聊"
   - 1-3天: "最近几天没聊"
   - 3-7天: "有一阵子了"
   - 7-30天: "好久没联系了"
   - 30+天: "很久很久了"

2. **频率趋势（Frequency Trend）**
   - 最近一周: 7次 → 前一周: 5次 → 趋势: ↑ 升温中
   - 最近一周: 2次 → 前一周: 5次 → 趋势: ↓ 降温中

3. **节奏感知（Rhythm）**
   - 每段关系有自己的"正常节奏"
   - 和小雨: 通常每天聊 → 3天没聊 = 异常
   - 和老王: 通常每周聊一次 → 一周没聊 = 正常

4. **关键时刻（Key Moments）**
   - 生日、纪念日、节日
   - 考试结束、入职、搬家等里程碑

5. **时间语义（Time Semantics）**
   - 为 AI 生成可直接使用的语境描述

#### emotion_summary — 情绪摘要投影

输入：所有 `emotion` 事件
输出：

```python
{
    "小雨": {
        "current": {"valence": -0.3, "arousal": 0.7, "label": "焦虑"},
        "trend": "最近一周持续下降",
        "pattern": "每月月初情绪偏低",
        "alert": "连续5天情绪偏负面",
        "suggestion": "最近适合陪伴，不适合提要求",
        "history": [
            {"date": "2025-06-15", "valence": 0.2, "label": "平静"},
            {"date": "2025-06-18", "valence": -0.1, "label": "略焦虑"},
            {"date": "2025-06-20", "valence": -0.5, "label": "焦虑"}
        ]
    }
}
```

**情绪模型：**

- `valence`: -1.0 到 +1.0（负面到正面）
- `arousal`: 0 到 1（平静到激动）
- "兴奋"和"焦虑"都是高 arousal，但 valence 不同
- "平静"和"麻木"都是低 arousal，但 valence 不同

**Emotion Engine 的职责：**
1. 存储情绪记录（由调用方 AI 写入）
2. 分析情绪趋势（Projection 计算）
3. 预警情绪异常（Projection 检测）

**Emotion Engine 不做情绪识别。** 情绪识别是调用方 AI 的工作。调用方 AI 判断后调用 `add_emotion` 存入 Event Log。

#### growth_timeline — 成长时间线投影

输入：所有 `growth` 事件
输出：

```python
{
    "我自己": {
        "timeline": [
            {"date": "2025-09", "title": "学习口腔医学", "category": "milestone", "impact": 6},
            {"date": "2025-12", "title": "学会 Python", "category": "skill", "impact": 7},
            {"date": "2026-03", "title": "开发 Relationship Engine", "category": "achievement", "impact": 9},
            {"date": "2026-06", "title": "发布 MCP Server", "category": "milestone", "impact": 10}
        ],
        "trajectory": "从医学转向AI，发展速度加快",
        "recent_focus": "AI 开发",
        "growth_rate": "加速中"
    }
}
```

**Growth 的价值：** 让 AI 理解变化，而不只是状态。

Memory 记住的是"小雨喜欢画画"。
Growth 记住的是"小雨从一个不会画画的人，变成了一个画家"。

#### reminders — 提醒投影

输入：所有 `person` + `reminder` + `chat` + `emotion` + `relation` 事件
输出：

```python
[
    {
        "person": "小雨",
        "type": "birthday",
        "message": "小雨生日还有5天",
        "urgency": "high",
        "trigger_date": "2025-06-20",
        "suggested_action": "准备一份礼物或祝福"
    },
    {
        "person": "小雨",
        "type": "lost_contact",
        "message": "和小雨偏离正常节奏（通常每天聊，已5天没聊）",
        "urgency": "high",
        "suggested_action": "主动打个招呼"
    },
    {
        "person": "小雨",
        "type": "emotion_alert",
        "message": "连续5天情绪偏负面",
        "urgency": "high",
        "suggested_action": "关心一下最近的状态"
    }
]
```

**提醒类型：**

| 类型 | 触发条件 | 紧急度 |
|------|---------|--------|
| birthday | 生日前 7 天 / 3 天 / 当天 | 高 |
| lost_contact | 偏离正常聊天节奏 | 中-高 |
| emotion_alert | 连续情绪低落 | 高 |
| anniversary | 认识纪念日、第一次约会等 | 中 |
| milestone_event | 对方的考试、面试等重要日子 | 中 |
| relationship_upgrade | 满足升级条件 | 低 |
| festival | 根据关系类型选择相关节日 | 低-中 |

#### conversation — 对话历史投影

输入：所有 `chat` 事件
输出：

```python
{
    "小雨": {
        "recent_messages": [
            {"role": "user", "content": "考完了吗？", "timestamp": "2025-06-20T10:00:00"},
            {"role": "assistant", "content": "还没，明天最后一门", "timestamp": "2025-06-20T10:01:00"}
        ],
        "total_messages": 342,
        "avg_messages_per_day": 4.2,
        "common_topics": ["考试", "吃饭", "电影", "画画"]
    }
}
```

### 4.3 性能优化

Projection 每次从 Event Log 重新计算。在事件量级为几千到几万时，replay 成本可忽略。

如果未来需要优化：
- **Projection 缓存**：缓存 Projection 的结果，只在 Event Log 变化时重新计算
- **增量 Projection**：不 replay 全部事件，只处理新增事件
- **快照**：定期保存 Projection 的完整状态，避免每次都从头计算

这些都是实现细节，不影响架构设计。

---

## 第五章：Context Builder — 最核心的 Projection

### 5.1 设计目标

当 AI 要和某个人相关的话题互动时，调用一次 `get_context(person)`，就能获得**在这一刻，关于这个人，AI 最应该知道的一切**。

Context Builder 不是一个特殊模块，它就是一个 Projection。
它做的事情：读取所有事件，调用其他 Projection 获取各维度数据，组合成一个结构化的上下文对象。

### 5.2 输出结构

```python
{
    "identity": {
        "name": "小雨",
        "nickname": "小鱼儿",
        "tags": ["口腔同学", "室友"],
        "birthday": "1998-06-15",
        "first_met": "2025-01-15",
        "days_known": 187
    },

    "relationship": {
        "stage": "暧昧",
        "chemistry": 85,
        "decay_chemistry": 72,
        "trend": "升温中",
        "milestones": [
            "2025-03-01: 第一次一起看电影",
            "2025-04-15: 分享了家庭故事"
        ]
    },

    "time": {
        "last_contact": "5天前",
        "last_contact_label": "有一阵子没联系了",
        "frequency_trend": "最近两周频率下降",
        "rhythm_alert": true,
        "upcoming": ["生日还有5天"],
        "relationship_age": "认识187天"
    },

    "emotion": {
        "current": "焦虑",
        "trend": "最近一周持续下降",
        "alert": "连续5天情绪偏负面",
        "approach": "最近适合陪伴，不适合提要求"
    },

    "growth": {
        "recent": "最近开始学摄影",
        "trajectory": "从AI转向创意方向"
    },

    "recent_events": [
        {"type": "chat", "content": "聊了考试的事", "date": "2025-06-20"},
        {"type": "fact", "content": "喜欢抹茶拿铁", "date": "2025-01-20"},
        {"type": "emotion", "content": "焦虑（考试压力）", "date": "2025-06-20"}
    ],

    "active_reminders": [
        "生日还有5天",
        "5天没联系了"
    ],

    "summary": "小雨，暧昧阶段，好感度85。已经5天没联系了。最近情绪焦虑，考试压力大。生日还有5天。"
}
```

### 5.3 summary 生成逻辑

summary 是模板化文本，不需要 LLM，使用确定性规则生成：

```python
def generate_summary(person, relationship, time, emotion, reminders):
    parts = []

    # 基本信息
    parts.append(f"{person.name}，{relationship.stage}阶段，好感度{relationship.chemistry}。")

    # 时间感知
    if time.last_contact_days > 3:
        parts.append(f"已经{time.last_contact_days}天没联系了。")

    # 情绪状态
    if emotion.alert:
        parts.append(f"注意：{emotion.alert}。")

    # 即将到来
    if time.upcoming:
        parts.append(f"即将到来：{'、'.join(time.upcoming)}。")

    # 节奏异常
    if time.rhythm_alert:
        parts.append(f"偏离了正常聊天节奏。")

    return " ".join(parts)
```

### 5.4 为什么 Context Builder 不做推理？

**Relationship OS 的定位是情报系统，不是决策系统。**

```
Context Builder 输出：
  事实 + 趋势 + 模式 + 异常

调用方 AI 做：
  推理 + 判断 + 决策

"她5天没联系了，最近3次聊天情绪得分下降" → 事实 + 趋势（Context Builder）
"她可能是压力大，你应该关心一下" → 推理 + 建议（调用方 AI）
```

Context Builder 的输出足够丰富、结构化、有组织，让调用方 AI 可以高效地理解和使用，但不替它做推理。

---

## 第六章：MCP Tools 设计

### 6.1 设计原则

- 只有两类：**写事件，读投影**
- Write Tools 写入 Event Log
- Read Tools 查询 Projection
- 所有数据操作最终都是 Event 操作

### 6.2 Write Tools（写入事件）

#### add_person

```
添加一个新人物到系统。

参数：
  name: str              # 姓名（必填）
  birthday: str = ""     # 生日（YYYY-MM-DD）
  nickname: str = ""     # 昵称
  tags: list[str] = []   # 标签（口腔同学、室友等）
  notes: str = ""        # 备注

写入事件：person {action: "create", ...}
```

#### remember

```
记住关于某人的一条信息/事实。

参数：
  person_name: str                # 人名（必填）
  content: str                    # 要记住的内容（必填）
  category: str = "general"       # 分类
  importance: int = 5             # 重要性 1-10

写入事件：fact {content, category, importance}
```

#### add_chat

```
记录一条聊天消息。

参数：
  person_name: str     # 人名（必填）
  role: str            # user 或 assistant（必填）
  content: str         # 消息内容（必填）

写入事件：chat {role, content}
同时自动更新：time_context.last_contact
```

#### add_emotion

```
记录一条情绪数据。

参数：
  person_name: str     # 人名（必填）
  valence: float       # -1.0 到 +1.0（必填）
  label: str           # 情绪标签（必填）
  arousal: float = 0.5 # 0 到 1
  context: str = ""    # 触发场景

写入事件：emotion {valence, arousal, label, context}
```

#### update_relation

```
更新与某人的关系状态。

参数：
  person_name: str       # 人名（必填）
  stage: str = ""        # 新关系阶段（可选）
  chemistry_delta: int = 0  # 好感度变化（可选）
  event: str = ""        # 触发事件描述（可选）

写入事件：relation {stage, delta, event}
```

#### add_milestone

```
记录一个关系里程碑。

参数：
  person_name: str          # 人名（必填）
  milestone_type: str       # 里程碑类型（必填）
  description: str          # 描述（必填）
  significance: int = 8     # 重要性 1-10

写入事件：milestone {milestone_type, description, significance}
```

#### add_growth

```
记录一个成长节点。

参数：
  person_name: str       # 人名（必填，通常是"我自己"）
  title: str             # 标题（必填）
  category: str          # skill/experience/milestone/achievement/realization
  description: str = ""  # 描述
  impact_level: int = 5  # 影响程度 1-10
  date: str = ""         # 日期（默认今天）

写入事件：growth {title, category, description, impact_level, date}
```

### 6.3 Read Tools（查询投影）

#### get_context

```
获取某人的完整 AI 上下文（最核心的读取接口）。

参数：
  person_name: str     # 人名（必填）

返回：完整上下文对象（见第五章）
包含：identity + relationship + time + emotion + growth + recent_events + reminders + summary
```

#### get_person

```
获取某人的人物画像。

参数：
  name: str     # 人名（必填）

返回：person_profile 投影
```

#### get_events

```
获取原始事件流。

参数：
  person_name: str = ""    # 人名（可选，为空则返回所有）
  days: int = 30           # 最近多少天
  event_type: str = ""     # 事件类型过滤（可选）

返回：事件列表
```

#### get_reminders

```
获取所有提醒。

参数：无

返回：reminders 投影
```

#### search

```
在所有事件中搜索关键词。

参数：
  keyword: str     # 搜索关键词（必填）

返回：匹配的事件列表
```

### 6.4 Resources

#### relationship://people

获取所有人物列表。

#### relationship://stats

获取系统统计摘要（总人数、总事件数、各类型事件数量等）。

---

## 第七章：Provider Interface

### 7.1 设计原则

Relationship OS 不绑定任何 LLM。通过 Provider Interface 调用，默认接入 CC Switch。

Relationship OS 只负责 Memory、Relationship、Conversation 和 Tools，不负责模型本身。

### 7.2 Provider 接口

```python
class LLMProvider(ABC):
    @abstractmethod
    def chat(self, system_prompt: str, messages: list[dict],
             temperature: float = 0.7, max_tokens: int = 1000) -> str:
        ...

    @abstractmethod
    def name(self) -> str:
        ...
```

### 7.3 内置 Providers

| Provider | 说明 |
|----------|------|
| CCSwitchProvider | 默认，通过 CC Switch 网关调用任何 LLM |
| OpenAICompatibleProvider | 通用 OpenAI 兼容接口（DeepSeek、Qwen、GPT 等） |
| None（离线模式） | 不调用 LLM，只提供 Tools |

### 7.4 配置

```
# CC Switch（推荐）
CC_SWITCH_BASE_URL=https://your-ccswitch/v1
CC_SWITCH_API_KEY=your-key
CC_SWITCH_MODEL=deepseek-chat

# 或直接用任何 OpenAI 兼容 LLM
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_API_KEY=your-key
LLM_MODEL=deepseek-chat
```

---

## 第八章：目录结构

```
Relationship-Engine/
├── src/
│   ├── event_log.py           # 事件日志（append + read + replay）
│   ├── event_types.py         # 事件类型定义（Event dataclass + 枚举值）
│   │
│   ├── projections/
│   │   ├── base.py            # Projection 基类
│   │   ├── person.py          # 人物画像投影
│   │   ├── relationship.py    # 关系状态投影（含衰减模型）
│   │   ├── time_context.py    # 时间上下文投影
│   │   ├── emotion.py         # 情绪摘要投影
│   │   ├── growth.py          # 成长时间线投影
│   │   ├── reminder.py        # 提醒投影
│   │   ├── conversation.py    # 对话历史投影
│   │   └── context.py         # AI 上下文投影（最核心）
│   │
│   ├── provider.py            # LLM Provider Interface
│   ├── mcp_server.py          # MCP Server（7 Write + 5 Read Tools）
│   └── main.py                # 入口（stdio / HTTP）
│
├── data/
│   └── events.jsonl           # 唯一的数据文件
│
├── tests/
│   ├── test_event_log.py
│   ├── test_projections.py
│   └── test_mcp_tools.py
│
├── pyproject.toml
├── .env.example
├── .gitignore
└── README.md
```

**关键观察：`src/` 只有 4 个核心文件 + 1 个 `projections/` 目录。** 没有 memory/、relationship/、conversation/ 模块目录，因为它们不是独立模块，它们只是 Projection。

---

## 第九章：运行模式

### 9.1 stdio 模式（本地）

配合 Claude Desktop 等本地 AI 客户端。

```bash
python -m src.main
```

Claude Desktop 配置：
```json
{
    "mcpServers": {
        "relationship-engine": {
            "command": "python",
            "args": ["-m", "src.main"],
            "cwd": "/path/to/Relationship-Engine"
        }
    }
}
```

### 9.2 HTTP 模式（远程）

部署到阿里云等服务器，任何支持 MCP 的 AI 客户端可连接。

```bash
python -m src.main --http
```

连接地址：`http://your-server:8080/mcp`

---

## 第十章：未来扩展规划

### 10.1 扩展原则

**新增功能 = 新增事件类型 + 新增 Projection。核心架构永远不变。**

### 10.2 Social Graph（v3+）

```
新增事件类型：social_link
{
    "type": "social_link",
    "person": "小雨",
    "data": {
        "target": "小明",
        "relationship": "恋爱",
        "strength": 9
    }
}

新增投影：social_graph.py
  → 输出：关系网络图
  → "小雨和小明是情侣"
  → "老王和你是室友"
  → "你们有3个共同朋友"
```

### 10.3 Group Management（v3+）

```
新增事件类型：group
{
    "type": "group",
    "data": {
        "group_name": "AI实验室",
        "action": "add_member",
        "member": "小雨"
    }
}

新增投影：group.py
  → 输出：群体归属、群体动态
  → "你和小雨同在AI实验室"
  → "今天是组会日，她可能比较忙"
```

### 10.4 Identity / Role（v3+）

```
新增事件类型：role
{
    "type": "role",
    "person": "小雨",
    "data": {
        "role": "暧昧对象",
        "context": "关系在发展中",
        "tone": "关心、温暖",
        "topics": ["心情", "生活", "未来"],
        "active": true
    }
}

新增投影：identity.py
  → 输出：多角色感知
  → "小雨同时是你的口腔同学、室友、游戏搭子、暧昧对象"
  → "当前主要角色：暧昧对象"
  → "提到课程时切同学模式"
```

### 10.5 AI Memory（v3+）

```
不需要新事件类型，复用 fact 事件。

新增投影：ai_memory.py
  → 从 fact 事件中提取 AI 专属记忆
  → "用户不喜欢被催促"
  → "用户习惯晚上聊天"
  → "用户提到过想学摄影"
```

### 10.6 Relationship Intelligence（v3+）

```
在 Context Builder 基础上，增加推理层。

新增：intelligence.py（Projection 的高级版本）
  → 输入：Context Builder 的输出
  → 输出：Observation + Risk + Possible Intent + Suggestions
  
  这是 v3 的功能，需要更多数据积累后才有意义。
```

### 10.7 扩展路线图

```
v2.0（当前）
  Event Log + 8 Projections + 12 MCP Tools + Context Builder
  核心能力：记忆、关系追踪、时间感知、情绪存储、提醒

v2.5
  + Group（群体归属）— 低成本高收益
  + 基础的 Social Link

v3.0
  + Social Graph Engine（关系网络）
  + Identity Engine（多角色）
  + Relationship Intelligence（推理层）
  + AI Memory（AI 专属记忆）
```

---

## 第十一章：数据流总览

### 11.1 写入数据流

```
调用方 AI（DeepSeek/GPT/Claude/Qwen）
    │
    │  调用 MCP Write Tool
    │
    ▼
MCP Layer
    │
    │  验证参数，构建 Event
    │
    ▼
Event Log（events.jsonl）
    │
    │  append event
    │
    ▼
Projections 自动更新（下次查询时重新计算）
```

### 11.2 读取数据流

```
调用方 AI
    │
    │  调用 MCP Read Tool（如 get_context）
    │
    ▼
MCP Layer
    │
    │  调用对应的 Projection
    │
    ▼
Projection Engine
    │
    │  replay Event Log，计算视图
    │
    ▼
返回结构化数据给调用方 AI
```

### 11.3 完整交互示例

```
用户对 GPT 说："我刚和小雨聊完天，她最近考试压力很大，心情不好"

GPT（调用方 AI）处理：
  1. 调用 add_chat("小雨", "user", "她最近考试压力很大，心情不好")
  2. 调用 add_emotion("小雨", valence=-0.4, label="焦虑", context="考试压力")
  3. 调用 get_context("小雨") 获取完整上下文
  4. GPT 根据上下文，结合自己的判断，给出回复
  
  GPT 的回复（由 GPT 自己决定，不是 Relationship OS 决定）：
  "小雨最近考试压力大，已经5天没好好聊了。
   她生日还有3天，你可以提前准备一下。
   建议今晚主动问一下她考得怎么样，但不要聊太深入。"
```

---

## 附录 A：事件类型完整枚举

| type | 说明 | person 字段 | data 字段 |
|------|------|------------|----------|
| person | 人物事件 | 必填 | action, birthday, nickname, tags, notes |
| chat | 聊天事件 | 必填 | role, content |
| fact | 事实/记忆 | 必填 | content, category, importance |
| emotion | 情绪事件 | 必填 | valence, arousal, label, context |
| relation | 关系变化 | 必填 | stage, delta, event |
| milestone | 里程碑 | 必填 | milestone_type, description, significance |
| growth | 成长事件 | 必填 | title, category, description, impact_level, date |
| reminder | 提醒事件 | 可选 | reminder_type, trigger_date, message, recurring, acknowledged |
| social_link | 社交关系（v3+） | 必填 | target, relationship, strength |
| group | 群组事件（v3+） | 可选 | group_name, action, member |
| role | 角色事件（v3+） | 必填 | role, context, tone, topics, active |

## 附录 B：关系阶段枚举

```
陌生人 → 认识 → 聊天 → 熟悉 → 朋友 → 重要的人 → 长期陪伴
                          ↘ 暧昧 → 热恋 → 稳定
                          ↘ 吵架 → 冷淡 → 分手
```

## 附录 C：里程碑类型枚举

| milestone_type | 说明 | significance 范围 |
|---------------|------|-----------------|
| first_meet | 第一次见面 | 5-7 |
| first_chat | 第一次聊天 | 4-6 |
| first_deep_talk | 第一次深聊 | 6-8 |
| first_secret | 第一次分享秘密 | 8-10 |
| first_fight | 第一次吵架 | 6-8 |
| first_reconciliation | 第一次和好 | 7-9 |
| first_date | 第一次约会 | 8-10 |
| first_trip | 第一次一起旅行 | 8-10 |
| first_collaboration | 第一次合作 | 6-8 |
| custom | 自定义 | 1-10 |

## 附录 D：情绪标签建议

| valence 范围 | arousal 范围 | 建议标签 |
|-------------|-------------|---------|
| +0.5 ~ +1.0 | 0.5 ~ 1.0 | 兴奋、开心、激动 |
| +0.5 ~ +1.0 | 0.0 ~ 0.5 | 满足、平静、幸福 |
| -0.5 ~ +0.5 | 0.0 ~ 0.3 | 平静、无聊、淡然 |
| -0.5 ~ +0.5 | 0.3 ~ 0.7 | 紧张、期待、纠结 |
| -1.0 ~ -0.5 | 0.5 ~ 1.0 | 焦虑、愤怒、压力 |
| -1.0 ~ -0.5 | 0.0 ~ 0.5 | 难过、沮丧、疲惫 |

## 附录 E：衰减参数表

| 关系类型 | λ（衰减速率） | floor（最低值） | 半衰期（天） |
|---------|-------------|--------------|------------|
| 家人 | 0.001 | 60 | 693 |
| 挚友 | 0.005 | 30 | 139 |
| 普通朋友 | 0.02 | 10 | 35 |
| 暧昧 | 0.05 | 5 | 14 |
| 同事 | 0.03 | 5 | 23 |

半衰期 = ln(2) / λ，即好感度衰减到一半所需的天数。

---

*文档版本：v3.0*
*最后更新：2026-06-25*
*作者：Suncatoo2*
*架构：Everything is Event, Everything else is Projection*
