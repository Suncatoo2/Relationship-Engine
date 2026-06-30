"""ADR Compliance Tests — 运行时架构合规验证

ADR-005: 高层只有一个入口 — publish_interaction()
ADR-006: 只有 Pipeline 可以访问 Event Store
ADR-010: Pipeline.recall() 返回 PipelineResponse

这些测试验证架构铁律在运行时成立，不只是 AST 扫描层面。
"""

import tempfile
import os

from src.storage import JSONLStorage
from src.dispatcher import ProjectionDispatcher
from src.interaction_pipeline import (
    InteractionPipeline, Interaction,
    FactInput, EmotionInput, RelationInput,
    MilestoneInput, GrowthInput,
    create_pipeline,
)
from src.projections.fact_state import FactProjection
from src.projections.person import PersonProjection
from src.projections.relationship import RelationshipProjection
from src.projections.time_context import TimeContextProjection
from src.projections.emotion import EmotionProjection
from src.projections.growth import GrowthProjection
from src.projections.conversation import ConversationProjection
from src.projections.reminder import ReminderProjection


class TestADR005SingleEntryPointRuntime:
    """ADR-005 运行时验证：publish_interaction() 是唯一写入口"""

    def test_all_event_types_flow_through_publish(self):
        """验证全部 7 种事件类型都能通过 publish() 写入"""
        with tempfile.TemporaryDirectory() as tmpdir:
            pipeline = create_pipeline(data_dir=tmpdir, user_id="test")

            # chat + fact + emotion + relation_change
            result = pipeline.publish(Interaction(
                message="你好",
                person="Alice",
                facts=[FactInput(content="喜欢蓝色", category="preference")],
                emotion=EmotionInput(valence=0.7, label="开心"),
                relation_change=RelationInput(stage="朋友", delta=10, event="初次聊天"),
            ))
            assert result.event_id, "chat event 未生成"

            # milestone
            result2 = pipeline.publish(Interaction(
                message="[里程碑] 第一次吵架",
                person="Alice",
                milestone=MilestoneInput(
                    milestone_type="first_fight",
                    description="第一次吵架",
                    significance=8,
                ),
            ))
            assert result2.event_id, "milestone event 未生成"

            # growth
            result3 = pipeline.publish(Interaction(
                message="[成长] 学会Python",
                person="我自己",
                growth=GrowthInput(
                    title="从0到1学会Python",
                    category="skill",
                    description="用了3个月",
                    impact_level=8,
                    date="2026-06-15",
                ),
            ))
            assert result3.event_id, "growth event 未生成"

            # 验证所有 events 都在 storage 中
            all_events = list(pipeline.storage.read_all())
            types_found = set(e.type for e in all_events)
            # chat 必定存在（每个 Interaction 都产生一个）
            assert "chat" in types_found
            assert "fact" in types_found
            assert "emotion" in types_found
            assert "relation" in types_found
            assert "milestone" in types_found
            assert "growth" in types_found

    def test_publish_returns_publish_result(self):
        """publish() 返回 PublishResult，不是裸 event_id"""
        with tempfile.TemporaryDirectory() as tmpdir:
            pipeline = create_pipeline(data_dir=tmpdir, user_id="test")
            result = pipeline.publish(Interaction(
                message="测试",
                person="Bob",
            ))
            assert hasattr(result, "event_id")
            assert hasattr(result, "derived_event_ids")
            assert isinstance(result.derived_event_ids, list)

    def test_decompose_creates_milestone_event(self):
        """验证 decompose 对 milestone 的处理"""
        from src.interaction_pipeline import decompose, make_milestone_event
        interaction = Interaction(
            message="[里程碑] 测试",
            person="Alice",
            milestone=MilestoneInput(
                milestone_type="first_meet",
                description="初次见面",
                significance=10,
            ),
        )
        events = decompose(interaction)
        # chat + milestone = 2 events
        assert len(events) >= 2
        milestone_events = [e for e in events if e.type == "milestone"]
        assert len(milestone_events) == 1
        assert milestone_events[0].data["milestone_type"] == "first_meet"
        assert milestone_events[0].data["description"] == "初次见面"

    def test_decompose_creates_growth_event(self):
        """验证 decompose 对 growth 的处理"""
        from src.interaction_pipeline import decompose, make_growth_event
        interaction = Interaction(
            message="[成长] 测试",
            person="我自己",
            growth=GrowthInput(
                title="学会写测试",
                category="skill",
                description="学会了 pytest",
                impact_level=7,
                date="2026-06-30",
            ),
        )
        events = decompose(interaction)
        growth_events = [e for e in events if e.type == "growth"]
        assert len(growth_events) == 1
        assert growth_events[0].data["title"] == "学会写测试"


class TestADR006PipelineOnlyRuntime:
    """ADR-006: Pipeline 是 Event Store 的唯一访问者（运行时验证）"""

    def test_storage_is_accessed_through_pipeline(self):
        """验证 data 路径和文件确实通过 Pipeline 创建"""
        with tempfile.TemporaryDirectory() as tmpdir:
            pipeline = create_pipeline(data_dir=tmpdir, user_id="alice_user")
            pipeline.publish(Interaction(
                message="第一条消息",
                person="Alice",
            ))
            # 检查 JSONL 确实被写入
            jsonl_path = os.path.join(tmpdir, "alice_user", "events.jsonl")
            assert os.path.exists(jsonl_path), (
                "Storage events.jsonl 应由 Pipeline 通过 Storage 接口写入"
            )
            # 验证 recall 也通过 Pipeline
            response = pipeline.recall("Alice")
            assert response.context is not None
            assert response.metadata is not None
            assert response.metadata.event_count >= 1

    def test_full_event_roundtrip(self):
        """完整的写入→分发→召回 链路"""
        with tempfile.TemporaryDirectory() as tmpdir:
            pipeline = create_pipeline(data_dir=tmpdir, user_id="test_user")

            # 写入
            pipeline.publish(Interaction(
                message="今天心情不错",
                person="Charlie",
                emotion=EmotionInput(valence=0.9, label="开心"),
                facts=[FactInput(content="喜欢咖啡", category="preference", importance=6)],
            ))

            # 分发已在 publish 内完成（Storage.append → Dispatcher.dispatch）

            # 召回
            response = pipeline.recall("Charlie")
            ctx = response.context
            d = ctx.to_dict()

            assert d["identity"]["name"] == "Charlie"
            assert d["memory"]["fact_count"] >= 1
            assert d.get("emotion") is not None


class TestADR010PipelineResponseRuntime:
    """ADR-010: Pipeline.recall() 返回 PipelineResponse，不是裸 ContextObject"""

    def test_recall_returns_pipeline_response(self):
        """recall() 返回值是 PipelineResponse 实例"""
        with tempfile.TemporaryDirectory() as tmpdir:
            pipeline = create_pipeline(data_dir=tmpdir, user_id="test")
            pipeline.publish(Interaction(message="hello", person="Dave"))

            response = pipeline.recall("Dave")
            from src.pipeline_response import PipelineResponse
            assert isinstance(response, PipelineResponse), (
                "recall() 必须返回 PipelineResponse，不是裸 ContextObject"
            )

    def test_pipeline_response_context_is_context_object(self):
        """PipelineResponse.context 是 ContextObject 实例"""
        with tempfile.TemporaryDirectory() as tmpdir:
            pipeline = create_pipeline(data_dir=tmpdir, user_id="test")
            pipeline.publish(Interaction(message="hello", person="Eve"))

            response = pipeline.recall("Eve")
            from src.protocol import ContextObject
            assert isinstance(response.context, ContextObject), (
                "PipelineResponse.context 必须是 ContextObject 实例"
            )

    def test_pipeline_response_metadata_has_event_count(self):
        """PipelineResponse.metadata 包含 event_count"""
        with tempfile.TemporaryDirectory() as tmpdir:
            pipeline = create_pipeline(data_dir=tmpdir, user_id="test")
            pipeline.publish(Interaction(message="msg1", person="Frank"))
            pipeline.publish(Interaction(message="msg2", person="Frank"))

            response = pipeline.recall("Frank")
            assert response.metadata.event_count == 2

    def test_pipeline_response_diagnostics_not_none(self):
        """PipelineResponse.diagnostics 必须填充（v0.7 起非空）"""
        with tempfile.TemporaryDirectory() as tmpdir:
            pipeline = create_pipeline(data_dir=tmpdir, user_id="test")
            pipeline.publish(Interaction(message="hello", person="Grace"))

            response = pipeline.recall("Grace")
            assert response.diagnostics is not None, (
                "PipelineResponse.diagnostics 不得为 None（v0.7 起完整填充）"
            )
        assert response.diagnostics.storage in ("healthy", "warning", "degraded")
        assert response.diagnostics.dispatcher == "healthy"
        assert response.diagnostics.projection_count >= 9

    def test_pipeline_response_metadata_has_timing(self):
        """PipelineResponse.metadata 包含 timing_ms, trace_id, request_id"""
        with tempfile.TemporaryDirectory() as tmpdir:
            pipeline = create_pipeline(data_dir=tmpdir, user_id="test")
            pipeline.publish(Interaction(message="hello", person="Grace"))

            response = pipeline.recall("Grace")
            assert response.metadata.timing_ms > 0
            assert response.metadata.trace_id != ""
            assert response.metadata.request_id != ""
            assert response.metadata.engine_version == "v1.0"

    def test_pipeline_response_to_dict(self):
        """PipelineResponse.to_dict() 包含 context + metadata + diagnostics"""
        with tempfile.TemporaryDirectory() as tmpdir:
            pipeline = create_pipeline(data_dir=tmpdir, user_id="test")
            pipeline.publish(Interaction(message="hello", person="Hank"))

            d = pipeline.recall("Hank").to_dict()
            # Contract: 3 top-level keys
            assert "context" in d
            assert "metadata" in d
            assert "diagnostics" in d
            # Metadata contract
            assert d["metadata"]["trace_id"] != ""
            assert d["metadata"]["request_id"] != ""
            assert d["metadata"]["timing_ms"] > 0
            assert "event_count" in d["metadata"]
            assert "total_events" in d["metadata"]
            assert "recall_strategy" in d["metadata"]
            # Diagnostics contract
            assert d["diagnostics"]["health"]["storage"] in ("healthy", "warning", "degraded", "corrupted", "unavailable")
            assert d["diagnostics"]["health"]["projection_count"] >= 9
            assert isinstance(d["diagnostics"]["projection_timing"], dict)
            assert isinstance(d["diagnostics"]["warnings"], list)
            assert "dead_letter_count" in d["diagnostics"]
            assert "engine_version" in d["diagnostics"]
            assert "engine_time" in d["diagnostics"]


class TestPipelineContract:
    """Engine 1.0 Pipeline Contract Tests — PipelineResponse 字段永不缺失

    这些测试保证:
      Interaction → Pipeline.publish() → Pipeline.recall() → PipelineResponse
    的返回结构是稳定的、可预期的、完整的。
    """

    def test_contract_metadata_fields_present(self):
        """PipelineResponse.metadata 必须包含全部 Engine 1.0 字段"""
        with tempfile.TemporaryDirectory() as tmpdir:
            pipeline = create_pipeline(data_dir=tmpdir, user_id="test")
            pipeline.publish(Interaction(message="contract test", person="CT"))

            m = pipeline.recall("CT").metadata
            required = {
                "version", "engine_version",
                "timing_ms", "started_at",
                "request_id", "trace_id",
                "recall_strategy", "scoring_method",
                "cache_hit", "snapshot_used",
                "event_count", "total_events", "person_count",
            }
            missing = required - set(m.to_dict().keys())
            assert missing == set(), f"Metadata 缺少字段: {missing}"

    def test_contract_diagnostics_fields_present(self):
        """PipelineResponse.diagnostics 必须包含全部 Engine 1.0 字段"""
        with tempfile.TemporaryDirectory() as tmpdir:
            pipeline = create_pipeline(data_dir=tmpdir, user_id="test")
            pipeline.publish(Interaction(message="contract test", person="DT"))

            d = pipeline.recall("DT").diagnostics
            assert d is not None, "diagnostics 不得为 None"
            dd = d.to_dict()

            required = {
                "health", "storage_health", "projection_timing",
                "warnings", "dead_letter_count",
                "engine_version", "engine_time",
            }
            missing = required - set(dd.keys())
            assert missing == set(), f"Diagnostics 缺少字段: {missing}"

    def test_contract_health_fields_present(self):
        """PipelineResponse.diagnostics.health 必须包含 storage + dispatcher 状态"""
        with tempfile.TemporaryDirectory() as tmpdir:
            pipeline = create_pipeline(data_dir=tmpdir, user_id="test")
            pipeline.publish(Interaction(message="contract test", person="ET"))

            h = pipeline.recall("ET").diagnostics.to_dict()["health"]
            assert "storage" in h
            assert "dispatcher" in h
            assert "projection_count" in h
            assert "registered_event_types" in h
            assert h["storage"] in ("healthy", "warning", "degraded", "corrupted", "unavailable")

    def test_contract_storage_health_present(self):
        """PipelineResponse.diagnostics.storage_health 包含 size / corrupted / wal"""
        with tempfile.TemporaryDirectory() as tmpdir:
            pipeline = create_pipeline(data_dir=tmpdir, user_id="test")
            pipeline.publish(Interaction(message="contract test", person="FT"))

            sh = pipeline.recall("FT").diagnostics.to_dict().get("storage_health", {})
            assert "status" in sh
            assert "current_size_bytes" in sh
            assert "event_count" in sh
            assert "corrupted_records" in sh
            assert "wal_dirty" in sh

    def test_contract_full_pipeline_roundtrip(self):
        """完整的 Interaction → Pipeline → PipelineResponse 链路"""
        with tempfile.TemporaryDirectory() as tmpdir:
            pipeline = create_pipeline(data_dir=tmpdir, user_id="test")

            # 写入：多种事件类型
            pipeline.publish(Interaction(
                message="hello",
                person="Alice",
                facts=[FactInput(content="likes blue", category="preference")],
                emotion=EmotionInput(valence=0.8, label="happy"),
                relation_change=RelationInput(stage="朋友", delta=10),
            ))

            # 读取
            response = pipeline.recall("Alice")

            # Context 合约（goals 是 optional block，有 goal 数据时才出现）
            d = response.context.to_dict()
            assert d["identity"]["name"] == "Alice"
            assert "memory" in d
            assert "relationship" in d
            assert "time" in d
            assert "emotion" in d
            assert "system" in d

            # Metadata 合约
            assert response.metadata.event_count >= 1
            assert response.metadata.total_events >= 1
            assert response.metadata.timing_ms > 0

            # Diagnostics 合约
            assert response.diagnostics is not None
            assert response.diagnostics.storage in ("healthy", "warning", "degraded", "corrupted", "unavailable")
            assert response.diagnostics.projection_count >= 9
            assert response.diagnostics.warnings is not None

    def test_contract_warning_no_events_for_unknown_person(self):
        """recall 未知 person 时产生 warning，不 crash"""
        with tempfile.TemporaryDirectory() as tmpdir:
            pipeline = create_pipeline(data_dir=tmpdir, user_id="test")
            response = pipeline.recall("NoSuchPerson")

            assert response.context is not None  # 仍返回空 Context
            assert response.diagnostics is not None
            assert any("no_events_for_person" in w for w in response.diagnostics.warnings), \
                "recall 未知 person 应产生 no_events_for_person warning"

    def test_contract_empty_store_recall(self):
        """空 Storage 时 recall 返回合法 PipelineResponse，不 crash"""
        with tempfile.TemporaryDirectory() as tmpdir:
            pipeline = create_pipeline(data_dir=tmpdir, user_id="test")
            response = pipeline.recall("Anyone")

            assert response.context is not None
            assert response.metadata.event_count == 0
            assert response.metadata.total_events == 0
            assert response.diagnostics.storage in ("healthy", "warning", "degraded", "corrupted")
            assert "empty_event_log" in response.diagnostics.warnings
