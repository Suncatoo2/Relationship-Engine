"""Tests for projections/prompt_builder.py"""

import pytest
from src.projections.prompt_builder import (
    BasePromptBuilder, DefaultBuilder, GPTBuilder, ClaudeBuilder, DeepSeekBuilder,
    get_builder, BUILDERS,
)
from src.projections.context import ContextSnapshot
from src.projections.person import PersonProfile, FactRecord
from src.projections.relationship import RelationshipProfile
from src.projections.emotion import EmotionProfile, EmotionTrend


def make_snapshot():
    return ContextSnapshot(
        version=1,
        person=PersonProfile(
            name="小雨", nickname="小鱼儿", birthday="1998-06-15",
            tags=["口腔同学", "室友"],
            facts=[FactRecord(content="喜欢奶茶", category="preference", importance=8, timestamp="2025-01-01")],
        ),
        relationship=RelationshipProfile(
            person_name="小雨", stage="暧昧", base_chemistry=85,
            decay_chemistry=80, trend="升温",
        ),
        emotion=EmotionProfile(
            person_name="小雨", trend=EmotionTrend.STABLE, dominant_emotion="开心",
        ),
    )


class TestDefaultBuilder:
    def test_build_returns_string(self):
        builder = DefaultBuilder()
        snapshot = make_snapshot()
        result = builder.build(snapshot)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_contains_person_info(self):
        builder = DefaultBuilder()
        snapshot = make_snapshot()
        result = builder.build(snapshot)
        assert "小雨" in result

    def test_contains_relationship_info(self):
        builder = DefaultBuilder()
        snapshot = make_snapshot()
        result = builder.build(snapshot)
        assert "暧昧" in result


class TestGPTBuilder:
    def test_uses_markdown(self):
        builder = GPTBuilder()
        snapshot = make_snapshot()
        result = builder.build(snapshot)
        assert "##" in result or "---" in result


class TestClaudeBuilder:
    def test_uses_xml(self):
        builder = ClaudeBuilder()
        snapshot = make_snapshot()
        result = builder.build(snapshot)
        assert "<" in result and ">" in result


class TestDeepSeekBuilder:
    def test_is_concise(self):
        builder = DeepSeekBuilder()
        snapshot = make_snapshot()
        result = builder.build(snapshot)
        # DeepSeek 格式应该比默认格式短
        default = DefaultBuilder().build(snapshot)
        assert len(result) <= len(default)


class TestGetBuilder:
    def test_get_default(self):
        builder = get_builder("default")
        assert isinstance(builder, DefaultBuilder)

    def test_get_gpt(self):
        builder = get_builder("gpt")
        assert isinstance(builder, GPTBuilder)

    def test_get_claude(self):
        builder = get_builder("claude")
        assert isinstance(builder, ClaudeBuilder)

    def test_get_deepseek(self):
        builder = get_builder("deepseek")
        assert isinstance(builder, DeepSeekBuilder)

    def test_get_unknown_returns_default(self):
        builder = get_builder("unknown")
        assert isinstance(builder, DefaultBuilder)


class TestExcluded:
    def test_excluded_section(self):
        builder = DefaultBuilder()
        snapshot = make_snapshot()
        snapshot.excluded = ["growth", "time"]
        result = builder.build(snapshot)
        assert "growth" in result or "time" in result


class TestEmptySnapshot:
    def test_empty_snapshot(self):
        builder = DefaultBuilder()
        snapshot = ContextSnapshot()
        result = builder.build(snapshot)
        assert isinstance(result, str)
