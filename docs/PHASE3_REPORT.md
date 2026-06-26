# Relationship Event OS v3 — Phase 3 Release Report

> Everything is Event. Everything else is Projection.

**版本:** v3-rc1
**日期:** 2026-06-26
**作者:** Suncatoo2
**状态:** Release Candidate Approved

---

## 一、本阶段目标

Phase 3 的目标是将 Phase 1（Event Log）和 Phase 2（7 个 Projections）整合成一个**可运行的 MCP Server**，让任何 AI（DeepSeek、Qwen、GPT、Claude）都能通过标准 MCP 协议调用关系管理能力。

核心交付物：
1. Context Composer — 组合所有 Projection 的输出
2. Prompt Builder — 把结构化数据变成 LLM 能理解的文本
3. MCP Server — 7 Write Tools + 5 Read Tools + 2 Resources
4. 验收测试 — 压力测试、真实场景、对抗性测试、边界条件
5. 代码审计 + RC Review

---

## 二、已完成功能

### 2.1 核心架构

| 组件 | 文件 | 说明 |
|------|------|------|
| Event 数据结构 | `src/event_types.py` | Event dataclass + 8 种事件类型 + 枚举值 |
| Event Log | `src/event_log.py` | append-only JSONL + 迭代器 + 搜索 |
| Projection 基类 | `src/projections/base.py` | parse_ts / group_by_person / make_metadata / project_one |
| Provider Interface | `src/provider.py` | CC Switch / OpenAI Compatible / 离线模式 |
| MCP Server | `src/mcp_server.py` | 7 Write + 5 Read + 2 Resources |
| 入口 | `src/main.py` | stdio / HTTP 两种模式 |

### 2.2 7 个 Projections

| Projection | 文件 | 输出 | 核心能力 |
|-----------|------|------|---------|
| Person | `person.py` | PersonProfile | 人物画像、事实记忆、metadata |
| Relationship | `relationship.py` | RelationshipProfile | 关系阶段、好感度衰减、Timeline、ChemistryRecord |
| Time Context | `time_context.py` | TimeContextProfile | 相对时间、密度、沉默检测、时间锚点、扩展接口 |
| Emotion | `emotion.py` | EmotionProfile | 情绪趋势、主导情绪、可配置报警、EmotionTrend 枚举 |
| Growth | `growth.py` | GrowthProfile | 成长时间线、里程碑、Trajectory |
| Reminder | `reminder.py` | ReminderProfile | 多态 Trigger、状态管理、5 种提醒类型 |
| Conversation | `conversation.py` | ConversationProfile | 三层窗口、topic_frequency、密度、confidence |

### 2.3 整合层

| 组件 | 文件 | 说明 |
|------|------|------|
| Context Composer | `context.py` | 组合 7 个 Projection，动态 Budget，ContextSnapshot |
| Prompt Builder | `prompt_builder.py` | Default / GPT / Claude / DeepSeek 四种格式 |

### 2.4 MCP Tools

**Write Tools（写入事件）：**

| Tool | 说明 |
|------|------|
| `add_person` | 添加人物（姓名、生日、标签、备注） |
| `remember` | 记住事实（内容、分类、重要性） |
| `add_chat` | 记录聊天（角色、内容、话题标签） |
| `add_emotion` | 记录情绪（valence、arousal、标签） |
| `update_relation` | 更新关系（阶段、好感度、事件） |
| `add_milestone` | 记录里程碑（类型、描述、重要性） |
| `add_growth` | 记录成长（标题、类型、描述、影响程度） |

**Read Tools（读取视图）：**

| Tool | 说明 |
|------|------|
| `get_context` | 获取完整 AI 上下文（支持 max_tokens + prompt_style） |
| `get_person` | 获取人物画像 |
| `get_events` | 获取原始事件流（支持 person/days/type 过滤） |
| `get_reminders` | 获取所有提醒 |
| `search` | 搜索所有事件 |

**Resources：**

| URI | 说明 |
|-----|------|
| `relationship://people` | 所有人物列表 |
| `relationship://stats` | 系统统计摘要 |

---

## 三、项目架构说明

### 3.1 整体架构

```
Event Log（唯一数据源）
    │
    ▼
Projection Layer（7 个 Projection）
    │
    ▼
Context Composer（组合 + 预算控制）
    │
    ▼
ContextSnapshot（结构化数据）
    │
    ▼
Prompt Builder（LLM 适配层）
    │
    ▼
Prompt（最终输出给 AI）
```

### 3.2 核心设计原则

1. **Everything is Event** — Event Log 是唯一的 Source of Truth
2. **Everything else is Projection** — 所有视图从 Event Log replay 生成
3. **Event 不可修改** — 只 append，不 update/delete
4. **Projection 不互相依赖** — 每个 Projection 只读 Event Log
5. **Context Composer 只读 Profile** — 不读 Event Log
6. **Projection 不做推断** — 情绪识别、话题提取是调用方 AI 的工作
7. **统一 metadata** — 所有 Profile 包含 generated_at、source_event_count、version

### 3.3 Analyzer vs Reasoning

```
Analyzer Projection（分析器）:
  Person / Relationship / Time / Emotion / Growth / Conversation
  → 只从 Event Log 读取数据，输出结构化分析

Reasoning Projection（推理器）:
  Reminder / Context / Insight
  → 融合多个 Analyzer 的结果，生成判断和建议
```

### 3.4 Projection 之间的关系

```
Event Log
    │
    ├─ person/fact ──→ Person Projection ──→ PersonProfile
    │
    ├─ relation/chat/milestone/person ──→ Relationship Projection ──→ RelationshipProfile
    │
    ├─ chat/person/milestone ──→ Time Context Projection ──→ TimeContextProfile
    │
    ├─ emotion ──→ Emotion Projection ──→ EmotionProfile
    │
    ├─ growth ──→ Growth Projection ──→ GrowthProfile
    │
    ├─ chat ──→ Conversation Projection ──→ ConversationProfile
    │
    └─ mixed ──→ Reminder Projection ──→ ReminderProfile
                        │
                        ▼
                Context Composer（只读 Profile，不读 Event Log）
                        │
                        ▼
                ContextSnapshot → Prompt Builder → Prompt
```

---

## 四、测试统计

### 4.1 单元测试

| 测试文件 | 测试数 | 状态 |
|---------|--------|------|
| test_event_types.py | 18 | ✅ |
| test_event_log.py | 29 | ✅ |
| test_projection_base.py | 29 | ✅ |
| test_person_projection.py | 19 | ✅ |
| test_relationship_projection.py | 21 | ✅ |
| test_time_context_projection.py | 28 | ✅ |
| test_emotion_projection.py | 22 | ✅ |
| test_growth_projection.py | 18 | ✅ |
| test_reminder_projection.py | 15 | ✅ |
| test_conversation_projection.py | 21 | ✅ |
| test_context_composer.py | 16 | ✅ |
| test_prompt_builder.py | 13 | ✅ |
| **总计** | **249** | **全部通过** |

### 4.2 验收测试

| 测试类别 | 测试数 | 状态 |
|---------|--------|------|
| 压力测试（50万事件） | 8 | ✅ |
| 真实场景模拟 | 8 | ✅ |
| 对抗性测试（故意找 Bug） | 10 | ✅ |
| 边界条件 | 4 | ✅ |
| API 一致性检查 | 17 | ✅ |
| **总计** | **47** | **47/47 passed** |

### 4.3 压力测试结果

| 测试项 | 数据量 | 耗时 | 状态 |
|--------|--------|------|------|
| 事件写入 | 500,000 | 46.0s | ✅ |
| 事件读取 | 500,000 | 1.7s | ✅ |
| Person Projection | 500,000 | 0.5s | ✅ |
| Relationship Projection | 500,000 | 0.3s | ✅ |
| TimeContext Projection | 500,000 | 0.7s | ✅ |
| Emotion Projection | 500,000 | 0.2s | ✅ |
| Growth Projection | 500,000 | 0.1s | ✅ |
| Conversation Projection | 500,000 | 0.6s | ✅ |
| Context Composer | 500,000 | 3.0s | ✅ |
| topic_frequency（10000条同 topic） | 10,000 | 0.013s | ✅ O(n) |

---

## 五、已知限制（Known Limitations）

| 编号 | 限制 | 严重程度 | 说明 |
|------|------|---------|------|
| 1 | `_search_dict` 不递归嵌套 dict | MEDIUM | 当前 event schema 不受影响 |
| 2 | ReminderProfile 返回类型不一致 | LOW | 设计决策，不是 Bug |
| 3 | Provider 代码重复 | LOW | 两个 Provider 的 chat 方法几乎相同 |
| 4 | 2月29日闰年里程碑可能崩溃 | LOW | 极端场景，需要关系恰好从2月29日开始 |
| 5 | conversation._is_within_days 重复 parse_ts | LOW | 可用 base.parse_ts 替代 |
| 6 | project_one 每次 replay 全部事件 | LOW | 50万事件下仍 < 1s，暂不影响 |
| 7 | Event.data 无 schema 验证 | LOW | 调用方 AI 负责写入正确格式 |
| 8 | 无用户认证 | N/A | 单用户工具，不需要 |

---

## 六、为什么采用 Event Log + Projection 设计

### 传统模块化的问题

```
传统设计：
  Memory 模块存 {name: "小雨", facts: [...]}
  Relationship 模块存 {stage: "暧昧", chemistry: 80}
  Time 模块存 {last_contact: "2026-06-23"}
  Emotion 模块存 {current: "焦虑"}

问题：
  1. 三份独立数据，可能不一致
  2. 想加情绪？再加一个模块
  3. 想加成长？再加一个模块
  4. 每个模块有自己的存储逻辑
```

### Event-first 的优势

```
Event-first 设计：
  events.jsonl 里只有事件：
    {type: "fact", person: "小雨", data: {content: "喜欢奶茶"}}
    {type: "relation", person: "小雨", data: {stage: "暧昧", delta: 30}}
    {type: "emotion", person: "小雨", data: {valence: -0.3, label: "焦虑"}}

优势：
  1. 一份数据，所有 Projection 从同一份数据计算，天然一致
  2. 想加新功能？加一个事件类型 + 一个 Projection，核心架构不变
  3. Event 不可修改，天然可追溯
  4. 升级 Projection 算法？重新 replay，不用迁移数据
  5. 50万事件下 Context Composer < 3s，性能完全够用
```

---

## 七、后续 Roadmap（Phase 4）

Phase 4 的方向不是"还能写什么代码"，而是"AI 怎样真正变得更懂人"。

### 可能的方向

| 方向 | 说明 |
|------|------|
| Insight Projection | 从所有 Projection 生成结构化洞察，而不只是数据聚合 |
| Story Projection | 自动生成"你和 TA 的故事"叙述 |
| Social Graph | 人与人之间的关系网络 |
| Identity / Role | 同一个人的多重身份（同学/室友/暧昧对象） |
| Temporal Perception | 心理时间（同样1天沉默，感受完全不同） |
| Relationship Seasons | 关系季节（初识/热恋/稳定/冷淡/恢复） |
| Emotional Momentum | 情绪惯性（检测趋势，不只是平均值） |
| Opportunity Reminder | 基于话题频率的聊天机会提醒 |
| Relationship Flow | 关系流向（warming/cooling/stable + velocity） |
| Confidence 自动计算 | 基于数据完整度的置信度 |
| Reason Trace | 来源追溯（derived_from event_id 列表） |
| Stress Test 增强 | 100万人、1000万事件的极端测试 |

---

## 八、给未来开发者的说明（Architecture Notes）

### 8.1 添加新的 Projection

```python
# 1. 创建 src/projections/my_projection.py
from .base import Projection

class MyProjection(Projection):
    def project(self, events) -> dict[str, MyProfile]:
        ...

# 2. 在 src/projections/context.py 中注册
from .my_projection import MyProjection

# 3. 添加到 PRIORITY_MAP
PRIORITY_MAP["my_projection"] = ProfilePriority.MEDIUM

# 4. 在 ContextComposer.__init__ 中实例化
self.my_proj = MyProjection()

# 5. 在 compose() 中调用
my_profile = self.my_proj.project_one(event_list, person_name)
```

### 8.2 添加新的 Prompt Builder

```python
# 1. 创建 src/projections/prompt_builder.py 中的新类
class MyLLMBuilder(DefaultBuilder):
    def _format_person(self, p) -> str:
        # 你的 LLM 偏好的格式
        ...

# 2. 注册到 BUILDERS 字典
BUILDERS["my_llm"] = MyLLMBuilder
```

### 8.3 添加新的事件类型

```python
# 1. 在 src/event_types.py 的 EventType 枚举中添加
class EventType(str, Enum):
    ...
    MY_TYPE = "my_type"

# 2. 在相关 Projection 中处理
# 3. 在 MCP Server 中添加 Write Tool
```

### 8.4 关键文件索引

| 文件 | 职责 |
|------|------|
| `event_types.py` | 所有数据结构和枚举的定义 |
| `event_log.py` | 唯一的数据存储层 |
| `projections/base.py` | 所有 Projection 的共享工具 |
| `projections/context.py` | Context Composer（组合器） |
| `projections/prompt_builder.py` | LLM 格式适配 |
| `mcp_server.py` | 对外 MCP 接口 |
| `docs/ARCHITECTURE.md` | 完整架构设计文档 |
| `tests/acceptance_test.py` | 验收测试脚本 |

---

## 九、标签历史

| Tag | 说明 |
|-----|------|
| v3-phase1 | Event Types + Event Log + Projection Base |
| v3-phase2 | 7 Projections 完成 |
| v3-phase3 | Context Composer + Prompt Builder + MCP Server |
| v3-rc1 | Release Candidate（验收测试通过 + RC Review Approved） |

---

*本文档由 Relationship Event OS 开发团队生成*
*最后更新：2026-06-26*
