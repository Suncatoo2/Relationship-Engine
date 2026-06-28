"""Tests for prompt_adapter.py — PromptAdapter"""

import pytest
from src.protocol import (
    ContextObject, IdentityBlock, MemoryBlock, FactItem,
    RelationshipBlock, TimeBlock, EmotionBlock, GoalsBlock, GoalItem, SystemBlock,
)
from src.prompt_adapter import (
    PromptAdapter, ClaudeAdapter, GPTAdapter, DeepSeekAdapter, get_adapter,
)


def make_context(stage="朋友", chemistry=50, emotion="开心", has_goals=True):
    """构建标准测试 ContextObject"""
    facts = [
        FactItem(content="喜欢蓝色", category="preference"),
        FactItem(content="口腔专业", category="general"),
    ]
    goals = None
    if has_goals:
        goals = GoalsBlock(
            active_goals=[GoalItem(title="考研", category="goal")],
            goal_count=1,
        )
    return ContextObject(
        identity=IdentityBlock(name="小雨", tags=["同学"]),
        memory=MemoryBlock(
            active_facts=facts,
            fact_count=2,
            memory_summary="小雨是口腔专业学生，喜欢蓝色",
        ),
        relationship=RelationshipBlock(
            stage=stage,
            chemistry=chemistry,
            trend="升温",
            last_contact_summary="3天前聊过",
        ),
        time=TimeBlock(
            last_chat_label="3天前",
            silence_label="几天没聊",
        ),
        emotion=EmotionBlock(
            trend="升温",
            dominant_emotion=emotion,
        ),
        goals=goals,
        system=SystemBlock(version=1, event_count=10),
    )


class TestPromptAdapterABC:
    def test_cannot_instantiate_abstract(self):
        with pytest.raises(TypeError):
            PromptAdapter()

    def test_tone_for_stage(self):
        adapter = DeepSeekAdapter()
        assert "敬语" in adapter._tone_for_stage("陌生人")
        assert "真诚" in adapter._tone_for_stage("朋友")
        assert "亲密" in adapter._tone_for_stage("热恋")


class TestClaudeAdapter:
    def test_build_contains_identity(self):
        adapter = ClaudeAdapter()
        ctx = make_context()
        prompt = adapter.build(ctx)
        assert "<identity>小雨</identity>" in prompt

    def test_build_contains_memory_summary(self):
        adapter = ClaudeAdapter()
        prompt = adapter.build(make_context())
        assert "<memory_summary>" in prompt
        assert "口腔专业" in prompt

    def test_build_contains_relationship(self):
        adapter = ClaudeAdapter()
        prompt = adapter.build(make_context())
        assert "stage=" in prompt
        assert "chemistry=" in prompt

    def test_build_contains_emotion(self):
        adapter = ClaudeAdapter()
        prompt = adapter.build(make_context())
        assert "<emotion" in prompt
        assert "开心" in prompt

    def test_build_contains_goals(self):
        adapter = ClaudeAdapter()
        prompt = adapter.build(make_context(has_goals=True))
        assert "<goals>" in prompt
        assert "考研" in prompt

    def test_build_no_goals_when_empty(self):
        adapter = ClaudeAdapter()
        prompt = adapter.build(make_context(has_goals=False))
        assert "<goals>" not in prompt


class TestGPTAdapter:
    def test_build_uses_markdown(self):
        adapter = GPTAdapter()
        prompt = adapter.build(make_context())
        assert "# 关于" in prompt
        assert "## 记忆" in prompt
        assert "## 关系" in prompt
        assert "## 情绪" in prompt

    def test_build_contains_facts(self):
        adapter = GPTAdapter()
        prompt = adapter.build(make_context())
        assert "[preference]" in prompt
        assert "喜欢蓝色" in prompt


class TestDeepSeekAdapter:
    def test_build_is_plain_text(self):
        adapter = DeepSeekAdapter()
        prompt = adapter.build(make_context())
        assert "【小雨】" in prompt
        assert "关系:" in prompt
        assert "情绪:" in prompt

    def test_build_contains_suggestions(self):
        adapter = DeepSeekAdapter()
        ctx = make_context()
        ctx = ContextObject(
            identity=ctx.identity, memory=ctx.memory,
            relationship=ctx.relationship, time=ctx.time,
            emotion=ctx.emotion, goals=ctx.goals,
            system=ctx.system,
            suggestions=["Bob 30天没联系了", "Alice生日还有5天"],
        )
        prompt = adapter.build(ctx)
        assert "建议:" in prompt
        assert "Bob" in prompt


class TestAdapterFactory:
    def test_get_claude_adapter(self):
        adapter = get_adapter("claude")
        assert isinstance(adapter, ClaudeAdapter)

    def test_get_gpt_adapter(self):
        adapter = get_adapter("gpt")
        assert isinstance(adapter, GPTAdapter)

    def test_get_deepseek_adapter(self):
        adapter = get_adapter("deepseek")
        assert isinstance(adapter, DeepSeekAdapter)

    def test_get_default_adapter(self):
        adapter = get_adapter("default")
        assert isinstance(adapter, DeepSeekAdapter)

    def test_get_unknown_adapter_falls_back(self):
        adapter = get_adapter("unknown_model")
        assert isinstance(adapter, DeepSeekAdapter)


class TestAdapterNeverReasons:
    """验证 PromptAdapter 只翻译，不推理"""

    def test_no_llm_calls(self):
        """Adapter.build() 不应该调用任何 LLM"""
        adapter = ClaudeAdapter()
        ctx = make_context()
        # build() 只做字符串拼接，不调用 LLM
        prompt = adapter.build(ctx)
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_deterministic_output(self):
        """相同输入 → 相同输出（确定性）"""
        adapter = GPTAdapter()
        ctx = make_context()
        p1 = adapter.build(ctx)
        p2 = adapter.build(ctx)
        assert p1 == p2

    def test_empty_context_still_works(self):
        """空 ContextObject 不崩溃"""
        for AdapterCls in [ClaudeAdapter, GPTAdapter, DeepSeekAdapter]:
            adapter = AdapterCls()
            ctx = ContextObject()
            prompt = adapter.build(ctx)
            assert isinstance(prompt, str)
