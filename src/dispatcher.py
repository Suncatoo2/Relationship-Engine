"""Projection Dispatcher — 插件化分发（registry 模式）

ADR-006: 只有 Pipeline 可以访问 Event Store。
Projection 只消费 Event，不主动读取。

registry = {
    "fact":      [FactProjection(), ...],
    "emotion":   [EmotionProjection(), ...],
    "relation":  [RelationshipProjection(), ...],
    ...
}

新增 Projection = 一行注册，不改 Dispatcher。
Pipeline 不知道 Dispatcher 里有几个 Projection。
"""

from collections import defaultdict
from src.projections.base import Projection
from src.event_types import Event


class ProjectionDispatcher:
    """投影分发器 — 按 event_type 注册路由

    Pipeline 只调用 dispatcher.dispatch(event)。
    Dispatcher 用 registry 决定路由到哪些 Projection。
    Pipeline 不知道里面有几个 Projection。
    """

    def __init__(self, projections: list[Projection] | None = None):
        self._registry: dict[str, list[Projection]] = defaultdict(list)
        self._all_projections: list[Projection] = list(projections) if projections else []
        self._dead_letter: list[dict] = []  # 死信记录：单个 Projection 失败的审计日志

    def register(self, projection: Projection, event_types: list[str]):
        """注册一个 Projection 监听指定 event_type

        Args:
            projection: Projection 实例
            event_types: 监听的事件类型列表，如 ["fact", "person"]
        """
        for t in event_types:
            self._registry[t].append(projection)
        if projection not in self._all_projections:
            self._all_projections.append(projection)

    def dispatch(self, event: Event):
        """按 event.type 从 registry 路由到对应的 Projection

        某个 Projection 的 apply() 失败不影响其他 Projection。
        失败记录写入死信队列（_dead_letter），严禁雪崩。

        Args:
            event: 由 Pipeline 传入的单个 Event
        """
        for proj in self._registry.get(event.type, []):
            try:
                proj.apply(event)
            except Exception as e:
                self._dead_letter.append({
                    "event_type": event.type if isinstance(event.type, str) else event.type.value,
                    "event_id": event.event_id,
                    "projection": proj.__class__.__name__,
                    "error": str(e),
                })

    def snapshot_all(self) -> dict[str, dict]:
        """获取所有 Projection 的当前快照"""
        snapshots: dict[str, dict] = {}
        for proj in self._all_projections:
            try:
                snapshots[proj.__class__.__name__] = proj.snapshot()
            except NotImplementedError:
                pass
        return snapshots

    def project_all(self, events: list[Event], person: str = "") -> dict[str, dict]:
        """对所有 Projection 执行批量计算（recall 时使用）

        Args:
            events: Event 列表
            person: 按人物过滤（传递给支持 person 参数的 Projection）

        Returns:
            {projection_name: profile_dict}
        """
        results: dict[str, dict] = {}
        for proj in self._all_projections:
            try:
                results[proj.__class__.__name__] = proj.project(events, person=person)
            except TypeError:
                # 不支持 person 参数的 Projection，用默认调用
                results[proj.__class__.__name__] = proj.project(events)
            except Exception:
                pass
        return results

    def count(self) -> int:
        return len(self._all_projections)

    def list_names(self) -> list[str]:
        return [p.__class__.__name__ for p in self._all_projections]

    def registered_types(self) -> list[str]:
        return list(self._registry.keys())

    @property
    def dead_letters(self) -> list[dict]:
        """死信队列：apply() 失败的记录"""
        return self._dead_letter

    def info(self) -> list[dict]:
        """返回所有已注册 Projection 的元信息"""
        return [p.info() for p in self._all_projections]
