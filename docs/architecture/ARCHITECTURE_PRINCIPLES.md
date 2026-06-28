# Architecture Principles — 架构原则

> 控制在一页纸。以后每一个 PR 都拿这七条检查。
> 项目做一年都不会跑偏。

---

## 1. Engine 永远不思考

Engine 是确定性管道。它不做推理、不猜情绪、不判断重要性。所有这些都交给 LLM。

## 2. LLM 永远负责推理

LLM 负责所有"需要理解"的工作：判断情绪、提取事实、评估重要性、决定回复内容。Engine 不代劳。

## 3. Projection 必须纯函数

`project(events) → Profile (frozen dataclass)`。无成员变量，无内部状态，无可变性。输入决定输出，100% 可重现。

## 4. Storage 可以替换

业务逻辑永远不直接读写文件。只通过 Storage 接口。今天是 JSONL，明天可以是 SQLite、Redis、图数据库。

## 5. Context Object 是唯一输出

Memory Engine 输出结构化的 Context Object，不是文本 Prompt。Prompt 是下游 Adapter 的事。加新模型 = 加新 Adapter，不改 Memory。

## 6. Snapshot 只是缓存

Snapshot 是 Projection 结果的持久化副本，目的是加速。不是新的数据源，不替代 Event Log。Event Log 挂了，Snapshot 可以从 Event Log 重建。

## 7. Event 永远不可修改

Event Log 只追加不修改。Projection 算错了就重新 replay，不要改原始事件。这和 Git 的原理一样。

---

*最后一个 commit 写完了吗？拿出来，拿这七条一条一条对。*