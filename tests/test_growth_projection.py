"""Tests for projections/growth.py"""

import pytest
from src.event_types import EventType, create_event
from src.projections.growth import (
    GrowthProjection, GrowthProfile, GrowthNode,
    GrowthMilestone, GrowthTrajectory,
)


@pytest.fixture
def proj():
    return GrowthProjection()


def make_growth_events():
    return [
        create_event(type=EventType.GROWTH, data={
            "title": "学习口腔医学", "category": "milestone",
            "description": "进入大学，开始学习口腔", "impact_level": 7, "date": "2024-09"
        }, person="我自己", timestamp="2024-09-01T00:00:00+00:00"),
        create_event(type=EventType.GROWTH, data={
            "title": "学会 Python", "category": "skill",
            "description": "从零开始学编程", "impact_level": 6, "date": "2025-06"
        }, person="我自己", timestamp="2025-06-01T00:00:00+00:00"),
        create_event(type=EventType.GROWTH, data={
            "title": "第一次完成自动化项目", "category": "achievement",
            "description": "用 Python 自动处理实验数据", "impact_level": 8, "date": "2025-09"
        }, person="我自己", timestamp="2025-09-01T00:00:00+00:00"),
        create_event(type=EventType.GROWTH, data={
            "title": "从遇到Bug就放弃到主动查文档", "category": "realization",
            "description": "开始理解调试是学习的一部分", "impact_level": 9, "date": "2025-12"
        }, person="我自己", timestamp="2025-12-01T00:00:00+00:00"),
        create_event(type=EventType.GROWTH, data={
            "title": "开发 Relationship Engine", "category": "achievement",
            "description": "从零开始设计架构", "impact_level": 10, "date": "2026-03"
        }, person="我自己", timestamp="2026-03-01T00:00:00+00:00"),
    ]


class TestEmpty:
    def test_empty(self, proj):
        assert proj.project([]) == {}

    def test_no_growth_events(self, proj):
        events = [create_event(type=EventType.CHAT, data={}, person="x")]
        assert proj.project(events) == {}


class TestTimeline:
    def test_timeline_count(self, proj):
        events = make_growth_events()
        result = proj.project(events)
        assert len(result["我自己"].timeline) == 5

    def test_timeline_sorted(self, proj):
        events = make_growth_events()
        result = proj.project(events)
        dates = [n.date for n in result["我自己"].timeline]
        assert dates == sorted(dates)

    def test_timeline_node_fields(self, proj):
        events = make_growth_events()
        result = proj.project(events)
        node = result["我自己"].timeline[0]
        assert node.title == "学习口腔医学"
        assert node.category == "milestone"
        assert node.impact_level == 7


class TestMilestones:
    def test_milestones_high_impact(self, proj):
        events = make_growth_events()
        result = proj.project(events)
        milestones = result["我自己"].milestones
        # impact >= 8 的节点
        assert len(milestones) == 3
        assert all(m.impact_level >= 8 for m in milestones)

    def test_milestone_is_growth_milestone(self, proj):
        events = make_growth_events()
        result = proj.project(events)
        assert isinstance(result["我自己"].milestones[0], GrowthMilestone)


class TestTrajectory:
    def test_trajectory_exists(self, proj):
        events = make_growth_events()
        result = proj.project(events)
        t = result["我自己"].trajectory
        assert t is not None
        assert isinstance(t, GrowthTrajectory)

    def test_trajectory_dominant_category(self, proj):
        events = make_growth_events()
        result = proj.project(events)
        t = result["我自己"].trajectory
        # 2个achievement, 1个milestone, 1个skill, 1个realization
        assert t.dominant_category == "achievement"

    def test_trajectory_direction(self, proj):
        events = make_growth_events()
        result = proj.project(events)
        t = result["我自己"].trajectory
        assert t.direction in ("technical", "personal")

    def test_trajectory_recent_categories(self, proj):
        events = make_growth_events()
        result = proj.project(events)
        t = result["我自己"].trajectory
        assert len(t.recent_categories) == 3

    def test_trajectory_high_impact_count(self, proj):
        events = make_growth_events()
        result = proj.project(events)
        t = result["我自己"].trajectory
        assert t.high_impact_count == 3


class TestMetadata:
    def test_metadata(self, proj):
        events = make_growth_events()
        result = proj.project(events)
        m = result["我自己"].metadata
        assert "generated_at" in m
        assert "source_event_count" in m


class TestDataclassOutput:
    def test_output_is_profile(self, proj):
        events = make_growth_events()
        result = proj.project(events)
        assert isinstance(result["我自己"], GrowthProfile)

    def test_to_dict(self, proj):
        events = make_growth_events()
        result = proj.project(events)
        d = result["我自己"].to_dict()
        assert isinstance(d, dict)
        assert isinstance(d["timeline"], list)
        assert isinstance(d["milestones"], list)
        assert isinstance(d["trajectory"], dict)


class TestProjectOne:
    def test_project_one(self, proj):
        events = make_growth_events()
        p = proj.project_one(events, "我自己")
        assert p is not None
        assert p.total_nodes == 5

    def test_project_one_not_found(self, proj):
        assert proj.project_one([], "不存在") is None


class TestMultiplePersons:
    def test_multiple_persons(self, proj):
        events = [
            create_event(type=EventType.GROWTH, data={"title": "A", "category": "skill", "impact_level": 5, "date": "2025-01"}, person="小雨"),
            create_event(type=EventType.GROWTH, data={"title": "B", "category": "realization", "impact_level": 6, "date": "2025-06"}, person="老王"),
        ]
        result = proj.project(events)
        assert len(result) == 2
        assert "小雨" in result
        assert "老王" in result
