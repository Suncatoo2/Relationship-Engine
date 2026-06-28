# Project Handoff — Relationship Event OS

> **给下一位 Claude（以及未来的自己）**
> 读完这份文档，你应该能完全理解项目现状并直接开始开发。不需要重新讨论架构。

---

## 1. 项目身份

- **产品名**: Relationship OS
- **仓库**: https://github.com/Suncatoo2/Relationship-Engine
- **核心理念**: 创造一个能够和人一起经历时间的 AI
- **核心架构**: Everything is Event, Everything else is Projection
- **当前版本**: v0.3.99 (Architecture Review 完成, Phase 1 Protocol 刚起步)

---

## 2. 已完成工作

### 2.1 架构设计（10 份文档）

| 文档 | 位置 |
|------|------|
| 项目基调 (Pipeline Architecture) | `docs/architecture/01_pipeline_architecture.md` |
| Step 4 设计 (Context Contract + Pipeline) | `docs/architecture/STEP4_DESIGN.md` |
| 架构原则 (7 Principles) | `docs/architecture/ARCHITECTURE_PRINCIPLES.md` |
| 架构决策记录 (5 ADR) | `docs/architecture/ARCHITECTURE_DECISIONS.md` |
| Memory 生命周期 | `docs/architecture/MEMORY_LIFECYCLE.md` |
| Interaction Pipeline 设计 | `docs/architecture/INTERACTION_PIPELINE.md` |
| Projection Snapshot 设计 | `docs/architecture/PROJECTION_SNAPSHOT.md` |
| Storage 抽象层设计 | `docs/architecture/STORAGE_ABSTRACTION.md` |
| 重构路线图 (Refactor Roadmap) | `docs/architecture/REFACTOR_ROADMAP.md` |
| 发布报告 (Phase 3) | `docs/PHASE3_REPORT.md` |
| 项目 Vision | `docs/VISION.md` |
| 项目 Roadmap | `docs/ROADMAP.md` |
| 检查点 | `docs/CHECKPOINT.md` |
| 开发存档 | `docs/SESSION.md` |

### 2.2 已完成代码

| 功能 | 位置 |
|------|------|
| Event 数据结构 + 枚举 | `src/event_types.py` |
| Event Log (append-only JSONL) | `src/event_log.py` |
| Provider Layer (DeepSeek, model-agnostic) | `src/provider.py` |
| Web Server (SSE streaming) | `src/web_server.py` |
| Chat UI (ChatGPT-style) | `src/web/chat.html` |
| Memory Engine (编排层) | `src/memory_engine.py` |
| Memory Selector (关键词匹配) | `src/memory_selector.py` |
| Memory Reasoner (接口预留) | `src/memory_reasoner.py` |
| Protocol Layer (ContextObject v1) | `src/protocol.py` ← 最新 |
| **8 个 Projection** | `src/projections/` |
| └ FactProjection (Stateless + Immutable) | `src/projections/fact_state.py` ← 最新 |
| MCP Server | `src/mcp_server.py` |
| 入口 | `src/main.py` |

### 2.3 测试

| 类型 | 数量 | 状态 |
|------|------|------|
| 单元测试 | 249 → 259 (含 protocol) | ✅ |
| Memory Test Suite | 32 | ✅ |
| 验收测试 | 47 | ✅ |
| Protocol 测试 | 10 | ✅ |

### 2.4 Git 状态

```
Tags: v0.3-stable, v0.3-memory-foundation, v3-phase1→v3-phase3
分支: main
待推送: 网络恢复后 push origin main --tags
```

---

## 3. 7 条架构原则（不可违反）

1. **Engine 永远不思考** — Engine 是确定性管道，不做推理/猜情绪
2. **LLM 永远负责推理** — 理解/判断/提取事实全部是 LLM 的事
3. **Projection 必须纯函数** — `project(events) → Profile (frozen)`, 无状态
4. **Storage 可以替换** — 业务代码不直接读写文件，走 Storage 接口
5. **Context Object 是唯一输出** — Memory Engine 输出结构化 Object，非文本
6. **Snapshot 只是缓存** — 不替 Event Log，可从 Event Log 重建
7. **Event 永远不可修改** — append-only, 算错了就重新 replay

---

## 4. 5 条 ADR（已经决定，不要重新讨论）

1. **ADR-001**: Everything is Event — 所有输入都是 append-only Event
2. **ADR-002**: Projection 必须 Stateless + Immutable
3. **ADR-003**: Engine never competes with LLM for thinking
4. **ADR-004**: Storage 必须抽象 — 今天是 JSONL, 明天可以是 SQLite
5. **ADR-005**: 高层只有一个入口 — `publish_interaction()`

---

## 5. 三句设计总结

> **Memory 保存历史 → Projection 计算状态 → Context 服务推理**

---

## 6. 当前项目目录结构

```
src/
├── event_types.py           # Event 数据结构 + 枚举
├── event_log.py             # append-only JSONL
├── provider.py              # LLM Provider Interface
├── web_server.py            # Web Server (SSE)
├── web/chat.html            # ChatGPT 风格 UI
├── memory_engine.py         # 记忆引擎 (编排层)
├── memory_selector.py       # 记忆选择器 (关键词)
├── memory_reasoner.py       # 推理器 (接口预留)
├── protocol.py              # ← Phase 1: ContextObject v1
├── mcp_server.py            # MCP Server
├── main.py                  # 入口
└── projections/             # 8 个 Projection
    ├── base.py              # Projection 基类
    ├── fact_state.py        # FactProjection (纯函数)
    ├── person.py            # 人物画像
    ├── relationship.py      # 关系 + 衰减
    ├── time_context.py      # 时间感知
    ├── emotion.py           # 情绪摘要
    ├── growth.py            # 成长时间线
    ├── reminder.py          # 智能提醒
    ├── conversation.py      # 对话分析
    ├── context.py           # Context Composer
    └── prompt_builder.py    # Prompt Builder
tests/
├── test_memory_suite.py     # 32 个自动化测试
├── test_protocol.py         # 10 个 Protocol 测试
└── test_*.py                # 249+ 单元测试
docs/
├── architecture/            # 10 份架构文档
├── VISION.md                # North Star
├── ROADMAP.md               # Phase 路线图
├── ARCHITECTURE.md          # 旧架构文档
├── CHECKPOINT.md            # 检查点
├── MILESTONE.md             # 里程碑
├── CHANGELOG.md             # 版本日志
└── SESSION.md               # 开发存档
```

---

## 7. 尚未完成

### Phase 1 Protocol（进行中）

- [ ] `ContextObject` dataclass ← **已完成** (src/protocol.py)
- [ ] `Event` schema 固化
- [ ] `Projection` interface 统一 (apply / update / output)
- [ ] `Storage` interface 统一 (append / read_since / snapshot / restore)

### Phase 2 Pipeline

- [ ] `InteractionPipeline` (publish / recall / snapshot / rebuild)
- [ ] `ProjectionDispatcher` (register / dispatch / snapshot_all)
- [ ] `ContextComposer` 增强 (筛选→排序→摘要→压缩)
- [ ] 端到端验证: 一句话跑通全链路

### Phase 3-4

- [ ] Projection 扩展 (Timeline / Goal 等新建)
- [ ] Storage 切换 (JSONL → SQLite, 不改业务代码)
- [ ] Incremental Projection (百万级事件)
- [ ] Prompt Adapter (Claude / GPT / Gemini / DeepSeek)

---

## 8. 下一步开发（按优先级）

### P0: 固化当前状态

```bash
git push origin main --tags
git tag v0.3.99-architecture-review
```

### P1: Phase 1 — Event Schema 固化

在 `event_types.py` 中确保 Event 结构稳定：`id / timestamp / type / person / data / source`

### P2: Phase 1 — Projection 接口统一

在 `projections/base.py` 中添加 `apply()` / `snapshot()` 方法。

### P3: Phase 1 — Storage 接口

创建 `src/storage.py`，定义 `Storage` 抽象基类，`JSONLStorage` 作为当前实现。

### P4: Phase 2 — InteractionPipeline

创建 `src/interaction_pipeline.py` 和 `src/projection_dispatcher.py`。

### 开发原则

1. **Always Runnable**: 每天结束前代码必须能跑
2. **先测试绿灯**: 改任何代码前确保 32 个测试通过
3. **先定义 Done**: 开始前写清楚完成标准
4. **极简实现**: Phase 1 不要加未来才需要的字段

---

## 9. 最大技术风险

1. **Context Composer 模糊地带**: 当前输出混用字符串 (prompt_text) 和对象 (context_snapshot)。需要明确 Memory Engine 只输出结构化对象
2. **全量 Replay**: 当前每次 replay 全部 Event Log。数据量 > 10 万时性能下降。Snapshot 方案已设计 (v0.6 实现)
3. **deprecation 机制不持久**: Event Log 是 append-only，废弃事件写入新行但未验证读取时正确解析

---

## 10. 接手后第一件事

```bash
# 1. 读架构文件
cat docs/architecture/ARCHITECTURE_PRINCIPLES.md
cat docs/architecture/ARCHITECTURE_DECISIONS.md
cat docs/CHECKPOINT.md

# 2. 跑测试
python -m pytest tests/ --ignore=tests/acceptance_test.py --ignore=tests/test_memory_suite.py -q

# 3. 验证最新代码能运行
python -c "from src.protocol import ContextObject; print('OK')"

# 4. 继续 Phase 1
#   下一步: src/protocol.py 已完成 → 接下来固化 Event Schema 或 Projection Interface
```

---

*Handoff 生成时间: 2026-06-27*
*最后 commit: d624ad7 (ContextObject v1)*
