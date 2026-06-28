# Refactor Roadmap — 技术债与架构演进路线

> 不是"以后可能要改"，而是明确：什么必须修、什么可以搁置、什么时候做。

---

## v0.4 必须完成（Interaction Pipeline）

| # | 任务 | 文件 | 说明 |
|---|------|------|------|
| 1 | InteractionPipeline | `src/interaction_pipeline.py` | 统一入口 + pub/sub |
| 2 | ProjectionDispatcher | `src/projection_dispatcher.py` | 插件化分发 |
| 3 | web_server 改为调用 pipeline.publish() | `src/web_server.py` | 替换手动写 Event |
| 4 | Memory Engine 改为调用 pipeline.snapshot() | `src/memory_engine.py` | 替换手动 replay |

## v0.4.5 必须完成（Snapshot + 增量）

| # | 任务 |
|---|------|
| 1 | Projection.apply() 实时更新 |
| 2 | Projection.snapshot() 序列化 |
| 3 | from_snapshot() 恢复 |
| 4 | Incremental Projection（只 replay 新事件） |

## v0.5 扩展引擎

| # | 问题 | 位置 | 影响范围 | 修复方案 |
|---|------|------|---------|---------|
| 1 | EventLog 直接读写文件，无 Storage 接口 | `src/event_log.py` | 未来换数据库要大改 | 改为调用 Storage 抽象接口 |
| 2 | `_auto_extract_facts` 直接遍历所有 events | `src/web_server.py:320-325` | 每次写 fact 都扫描全量 events | 改为调用 FactProjection |
| 3 | `web_server.py` 职责过多（提取+保存+回复+日志） | `src/web_server.py` | 难以测试，难以扩展 | 拆成 WebServer + FactExtractor + ChatHandler |

---

## v0.4 ~ v0.5 可以搁置的

| # | 问题 | 暂缓理由 | 建议触发条件 |
|---|------|---------|------------|
| 1 | memory_engine.py 无 Storage 抽象 | JSONL 目前完全够用 | 改为调用 `_event_log` 的 Storage 接口（改一行 import）|
| 2 | 全量 replay 每次 scan 几千条 event | 全量 < 100ms | 事件量超过 10 万时改 Incremental |
| 3 | MCP Server 还在用老接口（事件遍历） | MCP 不是主开发路径 | v0.6 重写 |
| 4 | `type` 参数名遮盖 Python 内建 | 不影响运行 | v0.5 Code Cleanup 统一修 |

---

## v1.0 前必须完成的

| # | 问题 | 说明 |
|---|------|------|
| 1 | Storage 抽象层 | 必须至少有 JSONL + SQLite 两种实现 |
| 2 | Incremental Projection | 百万级事件时的性能保障 |
| 3 | MCP Server 重构 | 7 Write + 5 Read 接口太重，合并为高层语义接口 |
| 4 | Provider 接口标准化 | Stream/Non-stream 统一返回类型 |

---

## 架构原则（不容妥协）

1. **Projection 不互相调用** — 任何 Projection 只能读 Event Log
2. **Projection 是纯函数** — Stateless + Immutable 输出
3. **业务逻辑不直接读文件** — 只能通过 Storage 接口
4. **Write Time 保证一致性** — 不为 Read Time 补救留坑
5. **新功能 = 新 Event Type + 新 Projection** — 不改核心架构

---

## 当前状态速查

```
版本:    v0.3.95
测试:    32/32 Memory Test Suite passed
数据量:  < 10000 条 event
存储:    JSONL (文件直写)
Projection: 8 个 (Stateless + Immutable)
下一步:  Step 4 — Memory 分层
```
