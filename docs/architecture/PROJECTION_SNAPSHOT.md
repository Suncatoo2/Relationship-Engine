# Projection Snapshot + Incremental Projection 设计

> 现在设计接口，v0.6 实现。当下的全量 Replay 对几千条事件完全够用。

---

## 核心思想

Projection 是纯函数：`project(events) → Profile`。

当 Event Log 超过 10 万条时，每次全量 replay 不再可行。
但 Projection 的接口不应该改变——只是内部实现从全量变为增量。

---

## Snapshot 设计

### 什么是 Snapshot？

```
全量 Replay（现在）:
  从 event #0 开始，逐条处理到 event #100000

Snapshot + Incremental（未来）:
  读取 snapshot (event #0 ~ #99000 的聚合结果)
    + replay 最后 1000 条事件 (event #99001 ~ #100000)
  = 当前结果
```

### 接口

```python
class Projection(ABC):
    @abstractmethod
    def project(self, events, since: str = None) -> Profile:
        """输入事件流，输出 Profile

        Args:
            events: 事件列表（全量或增量）
            since: snapshot 之后的第一条 event_id（None = 全量）

        Returns:
            Profile (dataclass)
        """
        ...

    def snapshot(self) -> dict:
        """返回当前状态的序列化快照

        Returns:
            可 JSON 序列化的 dict，用于持久化存储
        """
        ...

    @classmethod
    def from_snapshot(cls, data: dict) -> "Projection":
        """从快照恢复 Projection 实例

        用于：读取磁盘上的 snapshot 文件，重建 Projection，
              然后只 replay 新事件。
        """
        ...
```

### 快照存储格式

```json
{
  "projection_type": "FactProjection",
  "version": 1,
  "snapshot_at": "2026-08-01T00:00:00Z",
  "last_event_id": "a1b2c3d4-...",
  "state": {
    "active": {"preference": {...}, "general": {...}},
    "deprecated": [...],
    "total": 50000
  }
}
```

---

## Incremental Projection 接口（v0.6 实现）

```python
class FactProjection(Projection):
    def project(self, events, since: str = None) -> FactState:
        if since is None:
            return self._full_replay(events)
        else:
            return self._incremental(events, since)

    def _full_replay(self, events) -> FactState:
        """当前实现：全量 replay"""
        ...

    def _incremental(self, events, since: str) -> FactState:
        """v0.6 实现：从 snapshot + since 之后的事件增量计算"""
        snapshot = self._load_snapshot()
        new_events = [e for e in events if e.id > since]
        return self._merge(snapshot, new_events)
```

### 调用方不需要改

```python
# 当前（全量）：
state = FactProjection().project(events)

# 未来（增量）：
state = FactProjection().project(events, since="event_#99000")

# Memory Engine 一行不改
```

---

## Snapshot 写入策略

```
每 N 条新事件 (N = 10000)，自动写一次 snapshot。
或者：每次 shutdown 时写。
或者：每次 Projection 计算时间超过阈值 (100ms) 时写。
```

### 存储位置

```
data/
├── events.jsonl              # Event Log（唯一数据源）
├── prompts.jsonl             # Prompt Log
└── snapshots/
    ├── fact_state.json       # FactProjection snapshot
    ├── person_state.json     # PersonProjection snapshot
    ├── relationship_state.json
    └── ...
```

---

## 暂缓实现的原因

```
当前数据量: < 10000 条事件
全量 replay 耗时: < 100ms

实现 Snapshot 的代价:
  - 增加 8 个 snapshot 文件管理
  - 增加 snapshot 失效检测逻辑
  - 增加序列化/反序列化代码
  - 增加测试矩阵

收益: 几乎为零（当前数据量下无感知）

实现时机: 全量 replay 耗时 > 500ms 时
预估时间: v0.6 (事件量达到 10 万级别)
```

---

## 设计验证

当 v0.6 实现 Incremental Projection 时：
- Memory Engine 的 `recall()` 方法**不改一行**
- Projection 的接口 `project(events, since=None)` **不加新参数**
- 只有 `FactProjection._incremental()` 内部实现改变
- 32 个 Memory Tests 应该全部照旧通过
