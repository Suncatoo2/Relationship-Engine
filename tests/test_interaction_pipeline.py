"""Tests for interaction_pipeline.py — InteractionPipeline"""

import pytest
from src.event_types import EventType
from src.storage import JSONLStorage
from src.dispatcher import ProjectionDispatcher
from src.interaction_pipeline import (
    InteractionPipeline, Interaction, FactInput,
    EmotionInput, RelationInput, PublishResult,
)
from src.projections.base import Projection
from src.projections.fact_state import FactProjection


class SpyingProjection(Projection):
    """测试用 Projection：记录 apply 收到的所有事件"""

    def __init__(self):
        self.applied_events = []

    def project(self, events):
        return {"applied_count": len(self.applied_events)}

    def apply(self, event):
        self.applied_events.append(event)


def make_pipeline(tmp_path, projections: list[Projection] | None = None) -> InteractionPipeline:
    """测试辅助：创建 pipeline，projections 自动注册到 dispatcher"""
    store = JSONLStorage(str(tmp_path))
    dispatcher = ProjectionDispatcher()

    for proj in (projections or []):
        # 自动注册所有 8 种事件类型
        dispatcher.register(proj, event_types=[
            "chat", "fact", "emotion", "relation",
            "person", "milestone", "growth", "reminder",
        ])

    return InteractionPipeline(storage=store, dispatcher=dispatcher)


class TestPipeline:
    # ---- publish ----

    def test_publish_creates_chat_event(self, tmp_path):
        pipeline = make_pipeline(tmp_path)
        result = pipeline.publish(Interaction(
            message="我喜欢蓝色", person="小旭", type="statement",
        ))
        assert result.event_id != ""
        assert len(result.derived_event_ids) >= 1
        events = list(pipeline.storage.read_all())
        assert len(events) >= 1
        assert events[0].type == "chat"
        assert events[0].person == "小旭"

    def test_publish_creates_fact_events(self, tmp_path):
        pipeline = make_pipeline(tmp_path)
        pipeline.publish(Interaction(
            message="小雨喜欢奶茶", person="小雨",
            facts=[
                FactInput(content="喜欢奶茶", category="preference", importance=7),
                FactInput(content="喜欢抹茶", category="preference", confidence=0.8),
            ],
        ))
        events = list(pipeline.storage.read_all())
        fact_events = [e for e in events if e.type == "fact"]
        assert len(fact_events) == 2
        assert fact_events[0].data["content"] == "喜欢奶茶"

    def test_publish_creates_emotion_event(self, tmp_path):
        pipeline = make_pipeline(tmp_path)
        pipeline.publish(Interaction(
            message="今天很开心", person="小旭",
            emotion=EmotionInput(valence=0.9, label="开心", context="聊天"),
        ))
        events = list(pipeline.storage.read_all())
        emotion_events = [e for e in events if e.type == "emotion"]
        assert len(emotion_events) == 1
        assert emotion_events[0].data["valence"] == 0.9

    def test_publish_creates_relation_event(self, tmp_path):
        pipeline = make_pipeline(tmp_path)
        pipeline.publish(Interaction(
            message="第一次约会", person="小雨",
            relation_change=RelationInput(stage="暧昧", delta=30, event="第一次约会"),
        ))
        events = list(pipeline.storage.read_all())
        relation_events = [e for e in events if e.type == "relation"]
        assert len(relation_events) == 1
        assert relation_events[0].data["delta"] == 30

    def test_publish_no_emotion_when_none(self, tmp_path):
        pipeline = make_pipeline(tmp_path)
        pipeline.publish(Interaction(message="hello", person="x"))
        events = list(pipeline.storage.read_all())
        assert not any(e.type == "emotion" for e in events)

    def test_publish_no_relation_when_zero_delta(self, tmp_path):
        pipeline = make_pipeline(tmp_path)
        pipeline.publish(Interaction(
            message="hello",
            relation_change=RelationInput(stage="", delta=0),
        ))
        events = list(pipeline.storage.read_all())
        assert not any(e.type == "relation" for e in events)

    # ---- event_id / recorded_at ----

    def test_storage_generates_event_id(self, tmp_path):
        pipeline = make_pipeline(tmp_path)
        result = pipeline.publish(Interaction(message="hello", person="x"))
        assert result.event_id != ""

    def test_storage_generates_recorded_at(self, tmp_path):
        pipeline = make_pipeline(tmp_path)
        result = pipeline.publish(Interaction(message="hello", person="x"))
        events = list(pipeline.storage.read_all())
        for e in events:
            assert e.recorded_at != ""

    # ---- Dispatcher 不暴露 Projection 数量 ----

    def test_pipeline_does_not_know_projection_count(self, tmp_path):
        """Pipeline 只知道 dispatcher，不知道里面有几个 Projection"""
        spy = SpyingProjection()
        pipeline = make_pipeline(tmp_path, projections=[spy])
        assert not hasattr(pipeline, '_projections')
        assert not hasattr(pipeline, 'projections')
        # Pipeline 只通过 dispatcher 交互
        pipeline.publish(Interaction(message="hi", person="x"))
        assert len(spy.applied_events) >= 1  # spy 收到了事件

    # ---- recall ----

    def test_recall_minimal(self, tmp_path):
        pipeline = make_pipeline(tmp_path)
        pipeline.publish(Interaction(message="hello", person="小旭"))
        ctx = pipeline.recall("小旭")
        assert ctx.identity.name == "小旭"

    def test_recall_with_facts(self, tmp_path):
        pipeline = make_pipeline(tmp_path, projections=[FactProjection()])
        pipeline.publish(Interaction(
            message="小雨喜欢蓝色", person="小雨",
            facts=[FactInput(content="喜欢蓝色", category="preference")],
        ))
        ctx = pipeline.recall("小雨")
        assert ctx.memory is not None
        assert ctx.system is not None
        assert ctx.memory.fact_count >= 1

    # ---- snapshot / rebuild ----

    def test_snapshot(self, tmp_path):
        pipeline = make_pipeline(tmp_path)
        pipeline.publish(Interaction(message="hello", person="x"))
        snapshots = pipeline.snapshot()
        assert isinstance(snapshots, dict)

    def test_rebuild(self, tmp_path):
        pipeline = make_pipeline(tmp_path, projections=[SpyingProjection()])
        pipeline.publish(Interaction(message="hello", person="x"))
        pipeline.publish(Interaction(message="world", person="x"))
        results = pipeline.rebuild()
        assert isinstance(results, dict)

    # ---- 端到端验证（6 检查点）----

    def test_end_to_end_one_message(self, tmp_path):
        """一条消息走完完整链路，验证每一步输出

        检查点 1: Event 写入 Storage
        检查点 2: Event 顺序正确（recorded_at 升序）
        检查点 3: Fact Event 完整性
        检查点 4: Projection 更新（FactProjection.apply 收到事件）
        检查点 5: ContextObject 可序列化且包含新增内容
        检查点 6: 重复 recall 幂等
        """
        import json

        fact_proj = FactProjection()
        store = JSONLStorage(str(tmp_path))
        dispatcher = ProjectionDispatcher()
        dispatcher.register(fact_proj, event_types=["fact", "person"])
        pipeline = InteractionPipeline(storage=store, dispatcher=dispatcher)

        result = pipeline.publish(Interaction(
            message="我喜欢蓝色", person="小旭",
            facts=[FactInput(content="喜欢蓝色", category="preference", importance=8)],
        ))

        # 检查点 1: Event 写入成功
        assert result.event_id is not None
        assert len(result.derived_event_ids) >= 2
        all_events = list(store.read_all())
        assert len(all_events) >= 2

        # 检查点 2: Event 顺序正确
        for i in range(len(all_events) - 1):
            assert all_events[i].recorded_at <= all_events[i + 1].recorded_at

        # 检查点 3: Fact Event 完整性
        fact_events = [e for e in all_events if e.type == "fact"]
        assert len(fact_events) == 1
        assert fact_events[0].data["content"] == "喜欢蓝色"
        assert fact_events[0].data["importance"] == 8

        # 检查点 4: Projection 收到了事件（apply 被调用）
        assert len(fact_proj._cache) >= 1

        # 检查点 5: ContextObject 可序列化且包含新增内容
        ctx = pipeline.recall("小旭")
        assert ctx.identity.name == "小旭"
        assert ctx.memory.fact_count >= 1
        d = ctx.to_dict()
        j = json.dumps(d, ensure_ascii=False)
        assert "喜欢蓝色" in j
        assert "小旭" in j

        # 检查点 6: 重复 recall 幂等
        ctx2 = pipeline.recall("小旭")
        assert ctx2.memory.fact_count >= 1
        assert ctx2.identity is not None
        assert ctx2.system is not None
