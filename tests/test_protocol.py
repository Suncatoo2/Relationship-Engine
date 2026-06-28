"""Tests for protocol.py — Context Object v1"""

import pytest
import json
from src.protocol import (
    ContextObject, IdentityBlock, MemoryBlock, RelationshipBlock,
    TimeBlock, EmotionBlock, SystemBlock, FactItem,
)


class TestContextObject:

    def test_create_minimal(self):
        """最简创建 — 所有 must blocks 有默认值"""
        ctx = ContextObject()
        assert ctx.identity is not None
        assert ctx.memory is not None
        assert ctx.relationship is not None
        assert ctx.time is not None
        assert ctx.system is not None
        assert ctx.emotion is None                  # optional
        assert ctx.growth is None                   # optional

    def test_create_with_data(self):
        """完整数据创建"""
        ctx = ContextObject(
            identity=IdentityBlock(name="小雨", tags=["同学"], birthday="1999-03-15"),
            memory=MemoryBlock(
                active_facts=[
                    FactItem(content="喜欢蓝色", category="preference", confidence=0.95),
                    FactItem(content="口腔专业", category="general"),
                ],
                fact_count=2,
                memory_summary="小雨是口腔专业学生，喜欢蓝色",
            ),
            relationship=RelationshipBlock(stage="暧昧", chemistry=85, last_contact_summary="3天前聊过"),
            time=TimeBlock(last_chat_label="3天前", silence_label="几天没聊"),
            system=SystemBlock(generated_at="2026-06-27T00:00:00Z", event_count=42),
        )
        assert ctx.identity.name == "小雨"
        assert ctx.memory.fact_count == 2
        assert ctx.relationship.stage == "暧昧"

    def test_to_dict(self):
        """序列化"""
        ctx = ContextObject(
            identity=IdentityBlock(name="小雨"),
            system=SystemBlock(version=1),
        )
        d = ctx.to_dict()
        assert isinstance(d, dict)
        assert d["identity"]["name"] == "小雨"
        assert d["system"]["version"] == 1
        assert "emotion" not in d                    # optional None 不输出
        assert "growth" not in d

    def test_to_dict_with_emotion(self):
        """含 optional block 的序列化"""
        ctx = ContextObject(
            emotion=EmotionBlock(trend="稳定", dominant_emotion="开心"),
        )
        d = ctx.to_dict()
        assert d["emotion"]["trend"] == "稳定"

    def test_to_json(self):
        """JSON 序列化"""
        ctx = ContextObject(identity=IdentityBlock(name="小雨"))
        j = ctx.to_json()
        assert isinstance(j, str)
        data = json.loads(j)
        assert data["identity"]["name"] == "小雨"

    def test_immutable_identity(self):
        """frozen dataclass — 不可修改"""
        identity = IdentityBlock(name="小雨")
        with pytest.raises(Exception):
            identity.name = "老王"  # type: ignore

    def test_immutable_context(self):
        """frozen dataclass — 不可修改"""
        ctx = ContextObject()
        with pytest.raises(Exception):
            ctx.identity = None  # type: ignore

    def test_type_hints(self):
        """type hints 验证 — 确保字段类型正确"""
        ctx = ContextObject(
            identity=IdentityBlock(name="小雨"),
            memory=MemoryBlock(active_facts=[FactItem(content="test")]),
            relationship=RelationshipBlock(stage="朋友"),
            time=TimeBlock(),
            system=SystemBlock(),
        )
        assert isinstance(ctx.identity.name, str)
        assert isinstance(ctx.memory.active_facts, list)
        assert isinstance(ctx.memory.active_facts[0], FactItem)
        assert isinstance(ctx.relationship.stage, str)
        assert isinstance(ctx.system.version, int)

    def test_field_defaults(self):
        """字段有合理的默认值"""
        identity = IdentityBlock()
        assert identity.name == ""
        assert identity.tags == []

        fact = FactItem()
        assert fact.content == ""
        assert fact.confidence == 0.9
        assert fact.source == "user_direct"
        assert fact.status == "active"

    def test_roundtrip(self):
        """完整 roundtrip: create → to_dict → from dict → verify"""
        ctx = ContextObject(
            identity=IdentityBlock(name="小雨", birthday="1999-03-15"),
            memory=MemoryBlock(
                active_facts=[FactItem(content="喜欢蓝色", category="preference")],
                fact_count=1,
            ),
            relationship=RelationshipBlock(stage="暧昧", chemistry=85),
            time=TimeBlock(last_chat_label="今天"),
            system=SystemBlock(version=1, generated_at="now", event_count=10),
        )
        d = ctx.to_dict()
        j = ctx.to_json()
        data = json.loads(j)
        assert data["identity"]["name"] == "小雨"
        assert data["memory"]["fact_count"] == 1
        assert data["relationship"]["stage"] == "暧昧"
