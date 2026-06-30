"""Tests for ProfileProjection — 第 9 号 Projection

ProfileProjection 与其他 8 个 Projection 的模式一致：
  - apply(event):     增量缓存
  - snapshot():       当前状态快照
  - project(events):  批量计算 Profile

测试覆盖：
  - 空事件流 → 空 profiles
  - PERSON 事件初始化 profile
  - PROFILE 事件更新字段
  - user_edit 覆盖 conversation
  - conversation 提取来自动写入
  - apply() 增量路径
  - snapshot() 返回 dict
  - 完成度计算
"""

import pytest
from datetime import datetime, timezone

from src.event_types import Event, EventType, create_event
from src.projections.profile import ProfileProjection, Profile, ProfileField


class TestProfileField:
    def test_default_profile_field(self):
        f = ProfileField()
        assert f.value is None
        assert f.confidence == 0.0
        assert f.source == "onboarding"

    def test_profile_field_with_value(self):
        f = ProfileField(value="蓝色", confidence=0.95, source="user_edit")
        assert f.value == "蓝色"
        assert f.confidence == 0.95
        assert f.source == "user_edit"

    def test_profile_field_to_dict(self):
        f = ProfileField(value="test", confidence=0.8, source="conversation",
                         updated_at="2026-06-30T00:00:00+00:00")
        d = f.to_dict()
        assert d["value"] == "test"
        assert d["confidence"] == 0.8
        assert d["source"] == "conversation"


class TestProfile:
    def test_default_profile(self):
        p = Profile(person_name="Alice")
        assert p.person_name == "Alice"
        assert p.favorite_color is None
        assert p.completeness_pct == 0.0

    def test_profile_to_dict(self):
        p = Profile(person_name="Bob")
        p.favorite_color = ProfileField(value="红色", confidence=0.95, source="user_edit")
        d = p.to_dict()
        assert d["person_name"] == "Bob"
        assert d["preferences"]["favorite_color"]["value"] == "红色"
        assert d["preferences"]["hobbies"] == []

    def test_profile_omits_none_fields(self):
        p = Profile(person_name="Empty")
        d = p.to_dict()
        assert d["basic"]["nickname"] is None
        assert d["basic"]["birthday"] is None


class TestProfileProjection:
    @pytest.fixture
    def proj(self):
        return ProfileProjection()

    def test_empty_events(self, proj):
        profiles = proj.project([])
        assert profiles == {}

    def test_person_event_initializes_profile(self, proj):
        events = [
            create_event(type=EventType.PERSON, person="Alice",
                         data={"birthday": "1998-06-15", "nickname": "阿丽", "tags": ["creative"]}),
        ]
        profiles = proj.project(events)
        assert "Alice" in profiles
        p = profiles["Alice"]
        assert p.person_name == "Alice"
        assert p.birthday.value == "1998-06-15"
        assert p.nickname.value == "阿丽"
        assert "creative" in p.personality_traits

    def test_profile_event_updates_field(self, proj):
        events = [
            create_event(type=EventType.PROFILE, person="Alice",
                         data={"field": "favorite_color", "value": "蓝色",
                               "source": "user_edit", "confidence": 1.0}),
        ]
        profiles = proj.project(events)
        p = profiles["Alice"]
        assert p.favorite_color.value == "蓝色"
        assert p.favorite_color.source == "user_edit"
        assert p.favorite_color.confidence == 1.0

    def test_user_edit_overrides_conversation(self, proj):
        """user_edit 的优先级应高于 conversation"""
        events = [
            # 对话自动提取
            create_event(type=EventType.PROFILE, person="Alice",
                         data={"field": "favorite_color", "value": "红色",
                               "source": "conversation", "confidence": 0.6}),
            # 用户手动修改
            create_event(type=EventType.PROFILE, person="Alice",
                         data={"field": "favorite_color", "value": "蓝色",
                               "source": "user_edit", "confidence": 1.0}),
        ]
        profiles = proj.project(events)
        p = profiles["Alice"]
        assert p.favorite_color.value == "蓝色", "user_edit 应覆盖 conversation"
        assert p.favorite_color.source == "user_edit"

    def test_chat_extraction_adds_fields(self, proj):
        """chat 事件中的 profile_extraction 应自动更新 profile"""
        events = [
            create_event(type=EventType.CHAT, person="Alice",
                         data={"profile_extraction": {"favorite_color": "绿色", "trait": "幽默"}}),
        ]
        profiles = proj.project(events)
        p = profiles["Alice"]
        assert p.favorite_color.value == "绿色"
        assert p.favorite_color.source == "conversation"
        assert "幽默" in p.personality_traits

    def test_list_fields_accumulate(self, proj):
        """列表字段应累加不重复"""
        events = [
            create_event(type=EventType.PROFILE, person="Alice",
                         data={"field": "hobbies", "value": "阅读"}),
            create_event(type=EventType.PROFILE, person="Alice",
                         data={"field": "hobbies", "value": "游泳"}),
            create_event(type=EventType.PROFILE, person="Alice",
                         data={"field": "hobbies", "value": "阅读"}),  # 重复
        ]
        profiles = proj.project(events)
        p = profiles["Alice"]
        assert "阅读" in p.hobbies
        assert "游泳" in p.hobbies
        assert len(p.hobbies) == 2  # no duplicates

    def test_completeness_calculation(self, proj):
        """设置字段后完成度应正确计算"""
        events = [
            create_event(type=EventType.PROFILE, person="Alice",
                         data={"field": "favorite_color", "value": "蓝色", "source": "user_edit"}),
            create_event(type=EventType.PROFILE, person="Alice",
                         data={"field": "values", "value": "honesty"}),
            create_event(type=EventType.PROFILE, person="Alice",
                         data={"field": "dreams", "value": "环游世界"}),
        ]
        profiles = proj.project(events)
        p = profiles["Alice"]
        assert p.completeness_pct > 0
        assert p.total_fields_set >= 3

    # ---- 增量路径 ----

    def test_apply_caches_person_event(self, proj):
        e = create_event(type=EventType.PERSON, person="Alice",
                         data={"birthday": "1999-01-01"})
        proj.apply(e)
        assert len(proj._cache) == 1
        assert proj._cache[0].person == "Alice"

    def test_apply_caches_profile_event(self, proj):
        e = create_event(type=EventType.PROFILE, person="Alice",
                         data={"field": "favorite_color", "value": "blue"})
        proj.apply(e)
        assert len(proj._cache) == 1

    def test_apply_caches_chat_with_extraction(self, proj):
        e = create_event(type=EventType.CHAT, person="Alice",
                         data={"profile_extraction": {"favorite_food": "pizza"}})
        proj.apply(e)
        assert len(proj._cache) == 1

    def test_apply_ignores_chat_without_extraction(self, proj):
        e = create_event(type=EventType.CHAT, person="Alice",
                         data={"role": "user", "content": "hello"})
        proj.apply(e)
        assert len(proj._cache) == 0

    def test_snapshot_returns_cached_state(self, proj):
        proj.apply(create_event(type=EventType.PERSON, person="Alice",
                                data={"birthday": "1999-01-01"}))
        snap = proj.snapshot()
        assert "Alice" in snap
        assert snap["Alice"]["basic"]["birthday"]["value"] == "1999-01-01"

    # ---- 边界条件 ----

    def test_multiple_persons_separate_profiles(self, proj):
        events = [
            create_event(type=EventType.PERSON, person="Alice", data={"tags": ["creative"]}),
            create_event(type=EventType.PERSON, person="Bob", data={"tags": ["analytical"]}),
        ]
        profiles = proj.project(events)
        assert "Alice" in profiles
        assert "Bob" in profiles
        assert profiles["Alice"].person_name == "Alice"

    def test_empty_person_name_ignored(self, proj):
        events = [
            create_event(type=EventType.PROFILE, person="",
                         data={"field": "favorite_color", "value": "red"}),
        ]
        profiles = proj.project(events)
        assert "" not in profiles

    def test_none_value_field_skipped(self, proj):
        events = [
            create_event(type=EventType.PROFILE, person="Alice",
                         data={"field": "favorite_color", "value": None,
                               "source": "user_edit"}),
        ]
        profiles = proj.project(events)
        p = profiles.get("Alice")
        if p:
            assert p.favorite_color is None or p.favorite_color.value is None
            # 不应该 crash
