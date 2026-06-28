# Interaction Pipeline — 统一事件总线设计

> Step 4: 建立统一的事件入口和 Projection 分发机制。
> 新增 Projection = 注册一个处理器，不改 Engine。

---

## 目标

```
当前:  web_server → _auto_extract_facts → Event Log → Memory Engine.recall()
        每个模块自己读 Event，自己做 Projection

目标:  publish_interaction() → Event Log → Projection Dispatcher → 所有 Projection
        统一入口，统一分发，插件化
```

## 核心接口

### Interaction Pipeline

```python
class InteractionPipeline:
    """统一事件总线 — 所有交互的唯一入口"""

    def __init__(self, storage: Storage, projections: list[Projection]):
        self.storage = storage                # Storage 接口（JSONL/SQLite）
        self.dispatcher = ProjectionDispatcher(projections)

    def publish(self, event: Event) -> str:
        """发布一个事件
        1. 写入 Event Log
        2. 分发到所有 Projection
        3. 返回 event_id
        """
        self.storage.append(event.to_dict())
        self.dispatcher.dispatch(event)
        return event.id

    def snapshot(self) -> dict:
        """生成所有 Projection 的当前快照"""
        return self.dispatcher.snapshot_all()
```

### Projection Dispatcher

```python
class ProjectionDispatcher:
    """投影分发器 — 插件化设计

    每个 Projection 独立处理事件，互不依赖。
    新增 Projection 只需注册，不改 Dispatcher。
    """

    def __init__(self, projections: list[Projection]):
        self._projections = projections

    def register(self, projection: Projection):
        """注册一个新的 Projection（插件化）"""
        self._projections.append(projection)

    def dispatch(self, event: Event):
        """分发事件到所有 Projection"""
        for proj in self._projections:
            proj.apply(event)

    def snapshot_all(self) -> dict[str, dict]:
        """获取所有 Projection 的当前快照"""
        return {str(i): p.snapshot() for i, p in enumerate(self._projections)}
```

### Projection 接口（扩展）

```python
class Projection(ABC):
    """Projection 基类 — 支持事件驱动 + 批量计算"""

    @abstractmethod
    def project(self, events, since=None) -> Profile:
        """批量计算（全量或增量）"""
        ...

    def apply(self, event: Event):
        """处理单个事件（实时更新内部状态）

        默认不实现。需要实时更新的 Projection 覆盖此方法。
        """
        pass

    def snapshot(self) -> dict:
        """返回当前状态的序列化快照"""
        raise NotImplementedError
```

---

## 与现有代码的集成路径

```
Step 4.1: 创建 InteractionPipeline + ProjectionDispatcher
          （不影响现有代码，并行运行）

Step 4.2: web_server 改为调用 pipeline.publish()
          替代原来的 _auto_extract_facts + 手动 append

Step 4.3: Memory Engine 改为调用 pipeline.snapshot()
          替代原来的 list(iter_events()) + project(events)

Step 4.4: 验证 32/32 测试全部通过
```

## 现有 Projection 的 apply() 处理规则

| Projection | 处理的事件类型 | apply() 做什么 |
|-----------|-------------|---------------|
| FactProjection | fact | 更新 active_by_cat |
| PersonProjection | person | 更新人物画像 |
| RelationshipProjection | relation, chat | 更新关系状态 |
| TimeContextProjection | chat | 更新 last_contact |
| EmotionProjection | emotion | 添加情绪记录 |
| GrowthProjection | growth | 添加成长节点 |
| ConversationProjection | chat | 更新消息统计 |
| ReminderProjection | person, reminder | 更新提醒列表 |

---

## 插件化注册

```python
# 初始化
pipeline = InteractionPipeline(
    storage=JSONLStorage("data"),
    projections=[
        FactProjection(),
        PersonProjection(),
        RelationshipProjection(),
        TimeContextProjection(),
        EmotionProjection(),
        GrowthProjection(),
        ConversationProjection(),
    ],
)

# 以后加新 Projection，一行注册：
pipeline.dispatcher.register(TimelineProjection())
# 不需要改任何其他代码
```
