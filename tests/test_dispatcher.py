"""Tests for dispatcher.py — ProjectionDispatcher (registry 模式)"""

import pytest
from src.event_types import Event, EventType, create_event
from src.dispatcher import ProjectionDispatcher
from src.projections.base import Projection


class CountingProjection(Projection):
    """测试用 Projection：记录 apply 调用次数"""

    def __init__(self):
        self.apply_count = 0
        self.last_event = None

    def project(self, events):
        return {"count": len(events)}

    def apply(self, event):
        self.apply_count += 1
        self.last_event = event


class SnapshotProjection(Projection):
    """测试用 Projection：支持 snapshot"""

    def __init__(self):
        self._state = {"version": 1}

    def project(self, events):
        return {"state": self._state}

    def snapshot(self):
        return dict(self._state)


class NoSnapshotProjection(Projection):
    """测试用 Projection：不支持 snapshot（默认行为）"""

    def project(self, events):
        return {}


class TestDispatcher:
    @pytest.fixture
    def dispatcher(self):
        return ProjectionDispatcher()

    def test_init_empty(self, dispatcher):
        assert dispatcher.count() == 0
        assert dispatcher.list_names() == []
        assert dispatcher.registered_types() == []

    def test_init_with_projections(self):
        p1 = CountingProjection()
        p2 = SnapshotProjection()
        d = ProjectionDispatcher([p1, p2])
        assert d.count() == 2

    def test_register(self, dispatcher):
        p = CountingProjection()
        dispatcher.register(p, event_types=["chat", "fact"])
        assert dispatcher.count() == 1
        assert "CountingProjection" in dispatcher.list_names()
        assert "chat" in dispatcher.registered_types()
        assert "fact" in dispatcher.registered_types()

    def test_dispatch_routes_by_event_type(self, dispatcher):
        """只路由到注册了该 event_type 的 Projection"""
        fact_proj = CountingProjection()
        chat_proj = CountingProjection()
        dispatcher.register(fact_proj, event_types=["fact"])
        dispatcher.register(chat_proj, event_types=["chat"])

        fact_event = create_event(type=EventType.FACT, data={}, person="小雨")
        dispatcher.dispatch(fact_event)
        assert fact_proj.apply_count == 1
        assert chat_proj.apply_count == 0  # 未注册 fact，不路由

    def test_dispatch_multiple_projections_same_type(self, dispatcher):
        """多个 Projection 注册同一 event_type"""
        p1 = CountingProjection()
        p2 = CountingProjection()
        dispatcher.register(p1, event_types=["fact"])
        dispatcher.register(p2, event_types=["fact"])
        dispatcher.dispatch(create_event(type=EventType.FACT, data={}))
        assert p1.apply_count == 1
        assert p2.apply_count == 1

    def test_dispatch_unregistered_type(self, dispatcher):
        """未注册的 event_type 不路由任何 Projection"""
        p = CountingProjection()
        dispatcher.register(p, event_types=["fact"])
        dispatcher.dispatch(create_event(type=EventType.EMOTION, data={}))
        assert p.apply_count == 0

    def test_snapshot_all(self, dispatcher):
        s = SnapshotProjection()
        dispatcher.register(s, event_types=["fact"])
        snapshots = dispatcher.snapshot_all()
        assert "SnapshotProjection" in snapshots
        assert snapshots["SnapshotProjection"]["version"] == 1

    def test_snapshot_skips_not_implemented(self, dispatcher):
        n = NoSnapshotProjection()
        dispatcher.register(n, event_types=["fact"])
        snapshots = dispatcher.snapshot_all()
        assert "NoSnapshotProjection" not in snapshots

    def test_project_all(self, dispatcher):
        c = CountingProjection()
        dispatcher.register(c, event_types=["chat"])
        events = [
            create_event(type=EventType.CHAT, data={}, person="x"),
            create_event(type=EventType.CHAT, data={}, person="x"),
        ]
        results = dispatcher.project_all(events)
        assert "CountingProjection" in results
        assert results["CountingProjection"]["count"] == 2

    def test_registered_types(self, dispatcher):
        p1 = CountingProjection()
        p2 = SnapshotProjection()
        dispatcher.register(p1, event_types=["fact", "person"])
        dispatcher.register(p2, event_types=["emotion"])
        types = dispatcher.registered_types()
        assert set(types) == {"fact", "person", "emotion"}
