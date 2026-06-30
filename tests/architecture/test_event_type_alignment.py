"""EventType Alignment Check — 确保 EventType / Input DTO / decompose 三者对齐

检查内容：
1. 每个 EventType 是否有对应的 decompose 路径（或明确的"不用产生"决策）
2. 每个 Input DTO 是否有对应的 make_*_event 函数
3. Dispatcher registry 是否覆盖所有会被产生的 EventType
"""

from src.event_types import EventType
from src.interaction_pipeline import (
    decompose, Interaction,
    FactInput, EmotionInput, RelationInput,
    MilestoneInput, GrowthInput,
)


class TestEventTypeAlignment:
    """EventType enum ↔ decompose() ↔ Input DTO 对齐"""

    def test_event_types_with_decompose_path(self):
        """检查每个 EventType 的 decompose 覆盖情况"""
        # 构造一个包含所有 Input 的 Interaction
        interaction = Interaction(
            message="综合测试",
            person="Alice",
            facts=[FactInput(content="喜欢蓝色", category="preference")],
            emotion=EmotionInput(valence=0.7, label="开心"),
            relation_change=RelationInput(stage="朋友", delta=5, event="测试"),
            milestone=MilestoneInput(
                milestone_type="first_meet",
                description="初次见面",
                significance=10,
            ),
            growth=GrowthInput(
                title="学会Python",
                category="skill",
                description="3个月学会",
                impact_level=7,
                date="2026-06-15",
            ),
        )

        events = decompose(interaction)
        types_produced = set(e.type for e in events)

        # 7 个 EventType 中，REMINDER 和 PERSON 不由 decompose 产生是正确的：
        #   - REMINDER: 由 ReminderProjection 内部产生（Engine detects）
        #   - PERSON:  由 add_person Tool 通过 TYPE="person" 的 Interaction 产生
        expected_produced = {"chat", "fact", "emotion", "relation", "milestone", "growth"}
        missing = expected_produced - types_produced

        assert missing == set(), (
            f"decompose() 未产生以下预期类型: {missing}"
        )

    def test_input_dto_to_event_mapping(self):
        """每个 Input DTO 都有对应的 make_*_event 函数"""
        from src.interaction_pipeline import (
            make_chat_event, make_fact_event, make_emotion_event,
            make_relation_event, make_milestone_event, make_growth_event,
        )
        # 所有 Event 构造函数都存在
        # 验证每个函数会被正确参数调用
        interaction = Interaction(
            message="test",
            person="Alice",
            facts=[FactInput(content="test", category="general")],
            emotion=EmotionInput(valence=0.5, label="平静"),
            relation_change=RelationInput(stage="朋友", delta=5),
            milestone=MilestoneInput(milestone_type="first_meet", description="test"),
            growth=GrowthInput(title="test", category="skill"),
        )

        # 验证每个 make 函数正常返回
        chat_event = make_chat_event(interaction)
        assert chat_event.type == "chat"

        fact_event = make_fact_event(interaction, interaction.facts[0])
        assert fact_event.type == "fact"

        emotion_event = make_emotion_event(interaction)
        assert emotion_event.type == "emotion"

        relation_event = make_relation_event(interaction)
        assert relation_event.type == "relation"

        milestone_event = make_milestone_event(interaction)
        assert milestone_event.type == "milestone"

        growth_event = make_growth_event(interaction)
        assert growth_event.type == "growth"

    def test_event_types_with_no_input_dto_are_intentional(self):
        """EventType 中没有 Input DTO 的类型必须有明确设计意图"""
        # PERSON: 通过 Interaction.type="person" 触发，不需要专门的 PersonInput
        #         因为 decompose 始终生成 chat event，person data 在 Interaction 的顶层字段
        # CHAT:   始终生成，message 字段就是 chat data
        # REMINDER: ReminderProjection 内部产生，不由外部 Input

        # 有 Input DTO 的类型
        dto_covered = {"fact", "emotion", "relation", "milestone", "growth", "chat", "profile"}
        # chat 由 message 字段覆盖，不需要专门的 ChatInput

        all_types = set(t.value for t in EventType)
        intentional_no_dto = {"person", "reminder"}

        # 验证 EventType 分类完整性
        accounted = dto_covered | intentional_no_dto
        unaccounted = all_types - accounted

        assert unaccounted == set(), (
            f"EventType 中有未归类的类型: {unaccounted}\n"
            f"每个 EventType 要么有 Input DTO，要么在设计文档中说明原因。"
        )

    def test_dispatcher_registry_covers_all_produced_types(self):
        """Dispatcher 的 registry 必须覆盖 decompose 产生的所有事件类型"""
        from src.interaction_pipeline import create_pipeline
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            pipeline = create_pipeline(data_dir=tmpdir, user_id="test")

            # decompose 产生的所有类型
            interaction = Interaction(
                message="test",
                person="Alice",
                facts=[FactInput(content="test", category="general")],
                emotion=EmotionInput(valence=0.5, label="平静"),
                relation_change=RelationInput(stage="朋友", delta=5),
                milestone=MilestoneInput(milestone_type="first_meet", description="test"),
                growth=GrowthInput(title="test", category="skill"),
            )
            events = decompose(interaction)
            produced_types = set(e.type for e in events)

            registered_types = set(pipeline.dispatcher.registered_types())

            missing_in_dispatcher = produced_types - registered_types
            assert missing_in_dispatcher == set(), (
                f"decompose 产生的类型 {missing_in_dispatcher} 没有对应的 Dispatcher 路由\n"
                f"这意味着对应类型的 Event dispatch 时会被静默丢弃。"
            )
