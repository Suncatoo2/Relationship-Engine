"""Golden ContextObject — 标准输出回归测试

Golden ContextObject 是 ContextObject.to_dict() 的固定 JSON 快照。
任何修改如果改变了 Golden 输出，测试会立即失败。

用途：
  - 保证 ContextObject JSON 结构稳定
  - 保证 Projection 输出正确填入对应 Block
  - 保证 future 修改不会意外破坏输出格式

更新 Golden：
  当且仅当 ContextObject 结构发生有意变更时，
  运行 generate_golden() 重新生成 golden_context.json。
"""

import json
import os
import pytest
from src.storage import JSONLStorage
from src.dispatcher import ProjectionDispatcher
from src.interaction_pipeline import InteractionPipeline, Interaction, FactInput, EmotionInput, RelationInput
from src.projections.fact_state import FactProjection
from src.projections.person import PersonProjection
from src.projections.relationship import RelationshipProjection
from src.projections.time_context import TimeContextProjection
from src.projections.emotion import EmotionProjection
from src.projections.growth import GrowthProjection
from src.protocol import ContextObject

GOLDEN_DIR = os.path.join(os.path.dirname(__file__), "golden")
GOLDEN_FILE = os.path.join(GOLDEN_DIR, "context_object.json")


def _build_pipeline(tmp_path) -> InteractionPipeline:
    """构建含所有 Projection 的 Pipeline"""
    store = JSONLStorage(str(tmp_path))
    disp = ProjectionDispatcher()
    for p, types in [
        (FactProjection(),          ["fact"]),
        (PersonProjection(),        ["person", "fact"]),
        (RelationshipProjection(),  ["relation", "chat", "milestone", "person"]),
        (TimeContextProjection(),   ["chat", "person", "milestone"]),
        (EmotionProjection(),       ["emotion"]),
        (GrowthProjection(),        ["growth"]),
    ]:
        disp.register(p, event_types=types)
    return InteractionPipeline(storage=store, dispatcher=disp)


def _seed_data(pipeline: InteractionPipeline):
    """写入标准化测试数据"""
    pipeline.publish(Interaction(
        message="hi", person="小雨",
        facts=[
            FactInput(content="喜欢蓝色", category="preference", importance=8),
            FactInput(content="口腔专业", category="general", importance=6),
        ],
        emotion=EmotionInput(valence=0.8, label="开心"),
        relation_change=RelationInput(stage="朋友", delta=20, event="初次见面"),
    ))
    pipeline.publish(Interaction(
        message="今天天气不错", person="小雨",
        emotion=EmotionInput(valence=0.6, label="平静"),
    ))


def _generate_context_dict(tmp_path) -> dict:
    """生成 ContextObject 并返回 to_dict()"""
    pipeline = _build_pipeline(tmp_path)
    _seed_data(pipeline)
    ctx = pipeline.recall("小雨")
    return ctx.to_dict()


# ============================================================
#  Golden 生成（手动运行，不在 CI 中执行）
# ============================================================

def generate_golden():
    """生成 golden_context.json（仅在有意变更结构时调用）"""
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        d = _generate_context_dict(tmp)
        os.makedirs(GOLDEN_DIR, exist_ok=True)
        with open(GOLDEN_FILE, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=2)
        print(f"Golden written to {GOLDEN_FILE}")


# ============================================================
#  Golden 回归测试
# ============================================================

class TestGoldenContextObject:
    """验证 ContextObject 输出与 Golden 快照一致"""

    def test_golden_file_exists(self):
        """Golden 文件必须存在"""
        assert os.path.exists(GOLDEN_FILE), (
            f"Golden file missing: {GOLDEN_FILE}\n"
            f"Run: python -c 'from tests.test_golden_context import generate_golden; generate_golden()'"
        )

    def test_structure_matches_golden(self, tmp_path):
        """ContextObject 结构必须与 Golden 一致"""
        actual = _generate_context_dict(tmp_path)
        with open(GOLDEN_FILE, "r", encoding="utf-8") as f:
            golden = json.load(f)

        # 比较 key 结构（不比较具体值，因为时间戳每次不同）
        assert set(actual.keys()) == set(golden.keys()), (
            f"Top-level keys changed.\n"
            f"  Golden: {sorted(golden.keys())}\n"
            f"  Actual: {sorted(actual.keys())}"
        )

        # 每个 block 的 key 结构一致
        for block_name in golden:
            if isinstance(golden[block_name], dict) and isinstance(actual.get(block_name), dict):
                assert set(actual[block_name].keys()) == set(golden[block_name].keys()), (
                    f"Block '{block_name}' keys changed.\n"
                    f"  Golden: {sorted(golden[block_name].keys())}\n"
                    f"  Actual: {sorted(actual[block_name].keys())}"
                )

    def test_memory_block_has_summary(self, tmp_path):
        """memory_summary 必须非空"""
        actual = _generate_context_dict(tmp_path)
        assert actual["memory"]["memory_summary"], "memory_summary should not be empty"

    def test_relationship_block_filled(self, tmp_path):
        """RelationshipBlock 必须被填充"""
        actual = _generate_context_dict(tmp_path)
        assert actual["relationship"]["stage"] != "陌生人"
        assert actual["relationship"]["chemistry"] > 0

    def test_emotion_block_filled(self, tmp_path):
        """EmotionBlock 必须被填充"""
        actual = _generate_context_dict(tmp_path)
        assert "emotion" in actual
        assert actual["emotion"]["dominant_emotion"]

    def test_last_consumed_event_id(self, tmp_path):
        """last_consumed_event_id 必须非空"""
        actual = _generate_context_dict(tmp_path)
        assert actual["last_consumed_event_id"]

    def test_golden_json_serializable(self, tmp_path):
        """ContextObject 必须可序列化为 JSON"""
        actual = _generate_context_dict(tmp_path)
        j = json.dumps(actual, ensure_ascii=False)
        assert len(j) > 100  # 不是空 JSON


# ============================================================
#  边界情况回归测试
# ============================================================

class TestContextEdgeCases:
    """保证边界情况下 ContextObject 不崩溃"""

    def test_empty_pipeline_recall(self, tmp_path):
        """空 Pipeline 的 recall 不应崩溃"""
        store = JSONLStorage(str(tmp_path))
        disp = ProjectionDispatcher()
        pipeline = InteractionPipeline(storage=store, dispatcher=disp)
        ctx = pipeline.recall("不存在的人")
        assert ctx.identity.name == "不存在的人"
        assert ctx.memory.fact_count == 0
        assert ctx.system.event_count == 0
        assert ctx.last_consumed_event_id == ""

    def test_multiple_persons_isolation(self, tmp_path):
        """不同人物的数据应隔离"""
        store = JSONLStorage(str(tmp_path))
        disp = ProjectionDispatcher()
        disp.register(FactProjection(), event_types=["fact"])
        pipeline = InteractionPipeline(storage=store, dispatcher=disp)

        pipeline.publish(Interaction(message="a", person="Alice",
                                     facts=[FactInput(content="likes red", category="preference")]))
        pipeline.publish(Interaction(message="b", person="Bob",
                                     facts=[FactInput(content="likes green", category="preference")]))

        ctx_alice = pipeline.recall("Alice")
        ctx_bob = pipeline.recall("Bob")

        # Alice 的 facts 应该只有 "likes red"
        assert any(f.content == "likes red" for f in ctx_alice.memory.active_facts)
        assert not any(f.content == "likes green" for f in ctx_alice.memory.active_facts)

        # Bob 的 facts 应该只有 "likes green"
        assert any(f.content == "likes green" for f in ctx_bob.memory.active_facts)
        assert not any(f.content == "likes red" for f in ctx_bob.memory.active_facts)

    def test_recall_idempotent(self, tmp_path):
        """多次 recall 应返回相同结果（幂等，忽略时间戳）"""
        pipeline = _build_pipeline(tmp_path)
        _seed_data(pipeline)

        ctx1 = pipeline.recall("小雨")
        ctx2 = pipeline.recall("小雨")

        d1 = ctx1.to_dict()
        d2 = ctx2.to_dict()

        # 忽略 generated_at 时间戳差异
        d1["system"]["generated_at"] = ""
        d2["system"]["generated_at"] = ""
        assert d1 == d2

    def test_goals_with_no_goal_facts(self, tmp_path):
        """没有 goal fact 时 goals 应为 None"""
        store = JSONLStorage(str(tmp_path))
        disp = ProjectionDispatcher()
        disp.register(FactProjection(), event_types=["fact"])
        pipeline = InteractionPipeline(storage=store, dispatcher=disp)

        pipeline.publish(Interaction(message="hi", person="x",
                                     facts=[FactInput(content="likes blue", category="preference")]))

        ctx = pipeline.recall("x")
        assert ctx.goals is None

    def test_context_version_frozen(self, tmp_path):
        """ContextObject version 应始终为 1（直到有意升级）"""
        actual = _generate_context_dict(tmp_path)
        assert actual["system"]["version"] == 1


if __name__ == "__main__":
    generate_golden()
