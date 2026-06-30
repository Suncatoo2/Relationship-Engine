"""Profile Projection — 长期关系档案投影

不是调查问卷。
不是一次性填写。
而是随着时间推移，由 Event 驱动、持续更新的人格记忆层。

每个 Profile 字段包含：
  - value:     实际值
  - confidence: 置信度 (0.0–1.0)
  - source:     onboarding | conversation | user_edit
  - updated_at: 最后更新时间

输入事件类型：
  - profile: profile_update（用户主动修改）
  - chat:    对话中提取的偏好/特质（conversation extraction）
  - person:  人物创建时初始化 profile

设计原则：
  - User Override > Conversation Extraction > Onboarding
  - 每个字段独立 confidence
  - 未被提及的字段保持原值（不退化）
  - apply() 缓存增量事件，snapshot() 返回当前状态
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone

from ..event_types import Event, EventType
from .base import Projection


# ---- 数据结构 ----

@dataclass
class ProfileField:
    """一个 Profile 字段 — value + metadata"""
    value: str | int | bool | list | None = None
    confidence: float = 0.0
    source: str = "onboarding"     # onboarding / conversation / user_edit
    updated_at: str = ""

    def to_dict(self) -> dict:
        return {
            "value": self.value,
            "confidence": round(self.confidence, 2),
            "source": self.source,
            "updated_at": self.updated_at,
        }


@dataclass
class Profile:
    """Relationship Profile — 长期人格档案

    模块化组织，每个模块独立字段。
    未初始化的字段保持 None。
    """
    person_name: str = ""

    # Basic
    nickname: ProfileField | None = None
    birthday: ProfileField | None = None
    contact: ProfileField | None = None

    # Personality
    personality_traits: list[str] = field(default_factory=list)
    communication_style: ProfileField | None = None

    # Preferences
    favorite_color: ProfileField | None = None
    favorite_food: ProfileField | None = None
    favorite_music: ProfileField | None = None
    favorite_movie: ProfileField | None = None
    hobbies: list[str] = field(default_factory=list)

    # Lifestyle
    daily_routine: ProfileField | None = None
    sleep_habit: ProfileField | None = None

    # Emotion
    emotion_baseline: ProfileField | None = None
    triggers: list[str] = field(default_factory=list)

    # Relationship
    attachment_style: ProfileField | None = None
    social_preference: ProfileField | None = None

    # Values
    values: list[str] = field(default_factory=list)
    beliefs: list[str] = field(default_factory=list)

    # Dreams
    dreams: list[str] = field(default_factory=list)
    fears: list[str] = field(default_factory=list)

    # Growth (inferred, not the same as GrowthProjection)
    growth_areas: list[str] = field(default_factory=list)
    strengths: list[str] = field(default_factory=list)

    # Metadata
    total_fields_set: int = 0
    completeness_pct: float = 0.0
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """序列化为 dict — 只输出非空字段"""
        return {
            "person_name": self.person_name,
            "basic": {
                "nickname": self.nickname.to_dict() if self.nickname else None,
                "birthday": self.birthday.to_dict() if self.birthday else None,
                "contact": self.contact.to_dict() if self.contact else None,
            },
            "personality": {
                "traits": self.personality_traits,
                "communication_style": self.communication_style.to_dict() if self.communication_style else None,
            },
            "preferences": {
                "favorite_color": self.favorite_color.to_dict() if self.favorite_color else None,
                "favorite_food": self.favorite_food.to_dict() if self.favorite_food else None,
                "favorite_music": self.favorite_music.to_dict() if self.favorite_music else None,
                "favorite_movie": self.favorite_movie.to_dict() if self.favorite_movie else None,
                "hobbies": self.hobbies,
            },
            "lifestyle": {
                "daily_routine": self.daily_routine.to_dict() if self.daily_routine else None,
                "sleep_habit": self.sleep_habit.to_dict() if self.sleep_habit else None,
            },
            "emotion": {
                "baseline": self.emotion_baseline.to_dict() if self.emotion_baseline else None,
                "triggers": self.triggers,
            },
            "relationship": {
                "attachment_style": self.attachment_style.to_dict() if self.attachment_style else None,
                "social_preference": self.social_preference.to_dict() if self.social_preference else None,
            },
            "values": {
                "values": self.values,
                "beliefs": self.beliefs,
            },
            "dreams": {
                "dreams": self.dreams,
                "fears": self.fears,
            },
            "growth": {
                "areas": self.growth_areas,
                "strengths": self.strengths,
            },
            "total_fields_set": self.total_fields_set,
            "completeness_pct": round(self.completeness_pct, 1),
            "metadata": self.metadata,
        }


# ---- Projection ----

class ProfileProjection(Projection):
    """长期关系档案投影 — 第 9 号 Projection

    从 profile + person + chat 事件重建 Profile。

    apply(event):     增量缓存
    snapshot():       当前状态快照
    project(events):  批量计算 Profile
    """

    def __init__(self):
        self._cache: list = []

    def apply(self, event: Event):
        """增量模式：缓存 profile/person 事件"""
        if event.type in (EventType.PROFILE, EventType.PERSON) and event.person:
            self._cache.append(event)
        # chat 事件中的 profile 提取也缓存
        if event.type == EventType.CHAT and event.person:
            data = event.data or {}
            if data.get("profile_extraction"):
                self._cache.append(event)

    def snapshot(self) -> dict:
        """返回当前缓存状态的序列化快照"""
        return {
            name: p.to_dict()
            for name, p in self.project(self._cache).items()
        }

    def project(self, events) -> dict[str, Profile]:
        """输入事件流，输出 {人名: Profile}"""
        profiles: dict[str, Profile] = {}
        event_list = list(events)

        # Pass 1: 从 person 事件初始化 profile
        for e in event_list:
            if e.type == EventType.PERSON and e.person:
                p = self._get_or_create(profiles, e.person)
                self._apply_person_event(p, e)

        # Pass 2: 从 profile 事件更新
        for e in event_list:
            if e.type == EventType.PROFILE and e.person:
                p = self._get_or_create(profiles, e.person)
                self._apply_profile_event(p, e)

        # Pass 3: 从 chat 事件中的 profile_extraction 更新
        for e in event_list:
            if e.type == EventType.CHAT and e.person:
                data = e.data or {}
                if data.get("profile_extraction"):
                    p = self._get_or_create(profiles, e.person)
                    self._apply_extraction(p, data.get("profile_extraction", {}))

        # Pass 4: 计算 completeness
        for p in profiles.values():
            self._compute_completeness(p)

        return profiles

    def project_one(self, events, name: str) -> Profile | None:
        return self.project(events).get(name)

    # ---- helpers ----

    @staticmethod
    def _get_or_create(profiles: dict, name: str) -> Profile:
        if name not in profiles:
            profiles[name] = Profile(person_name=name)
        return profiles[name]

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _apply_person_event(self, p: Profile, e: Event) -> None:
        """从 person 事件初始化基础字段"""
        data = e.data or {}
        now = self._now()

        if "birthday" in data and data["birthday"]:
            p.birthday = ProfileField(
                value=data["birthday"], confidence=0.9,
                source="onboarding", updated_at=now,
            )
        if "nickname" in data and data["nickname"]:
            p.nickname = ProfileField(
                value=data["nickname"], confidence=0.9,
                source="onboarding", updated_at=now,
            )
        if "tags" in data and data["tags"]:
            for tag in data["tags"]:
                if tag not in p.personality_traits:
                    p.personality_traits.append(tag)

    def _apply_profile_event(self, p: Profile, e: Event) -> None:
        """从 profile 事件更新 Profile 字段

        profile 事件 data 格式:
          {
            "field": "favorite_color",
            "value": "蓝色",
            "source": "user_edit",
            "confidence": 1.0,
          }
        """
        data = e.data or {}
        field_name = data.get("field", "")
        value = data.get("value")
        source = data.get("source", "onboarding")
        confidence = data.get("confidence", 0.5)
        now = self._now()

        # 简单字段映射
        simple_fields = {
            "nickname", "birthday", "contact",
            "communication_style", "favorite_color", "favorite_food",
            "favorite_music", "favorite_movie", "daily_routine",
            "sleep_habit", "emotion_baseline", "attachment_style",
            "social_preference",
        }

        if field_name in simple_fields and hasattr(p, field_name):
            current = getattr(p, field_name)
            # User Override > Conversation > Onboarding
            if current is None or self._source_priority(source) >= self._source_priority(current.source):
                setattr(p, field_name, ProfileField(
                    value=value, confidence=confidence,
                    source=source, updated_at=now,
                ))

        # 列表字段
        list_fields = {
            "personality_traits": p.personality_traits,
            "hobbies": p.hobbies,
            "triggers": p.triggers,
            "values": p.values,
            "beliefs": p.beliefs,
            "dreams": p.dreams,
            "fears": p.fears,
            "growth_areas": p.growth_areas,
            "strengths": p.strengths,
        }
        if field_name in list_fields:
            target_list = list_fields[field_name]
            if isinstance(value, str) and value not in target_list:
                target_list.append(value)
            elif isinstance(value, list):
                for item in value:
                    if item not in target_list:
                        target_list.append(item)

    def _apply_extraction(self, p: Profile, extraction: dict) -> None:
        """从对话提取中更新 Profile（conversation source）"""
        now = self._now()
        for field_name, value in extraction.items():
            simple_fields = {
                "favorite_color", "favorite_food", "favorite_music",
                "favorite_movie", "hobby", "emotion_baseline",
                "communication_style", "attachment_style",
            }
            if field_name in simple_fields and hasattr(p, field_name):
                current = getattr(p, field_name)
                if current is None or current.source != "user_edit":
                    setattr(p, field_name, ProfileField(
                        value=value, confidence=0.6,
                        source="conversation", updated_at=now,
                    ))

            # 提取的 trait / value
            if field_name == "trait" and isinstance(value, str):
                if value not in p.personality_traits:
                    p.personality_traits.append(value)
            if field_name == "value" and isinstance(value, str):
                if value not in p.values:
                    p.values.append(value)
            if field_name == "dream" and isinstance(value, str):
                if value not in p.dreams:
                    p.dreams.append(value)

    @staticmethod
    def _source_priority(source: str) -> int:
        """数据来源优先级：user_edit > conversation > onboarding"""
        return {"user_edit": 3, "conversation": 2, "onboarding": 1}.get(source, 0)

    @staticmethod
    def _compute_completeness(p: Profile) -> None:
        """计算 profile 完成度"""
        all_fields = [
            p.nickname, p.birthday, p.contact,
            p.communication_style, p.favorite_color, p.favorite_food,
            p.favorite_music, p.favorite_movie, p.daily_routine,
            p.sleep_habit, p.emotion_baseline, p.attachment_style,
            p.social_preference,
        ]
        set_count = sum(1 for f in all_fields if f is not None and f.value is not None)
        list_fields = [
            p.personality_traits, p.hobbies, p.triggers,
            p.values, p.beliefs, p.dreams, p.fears,
            p.growth_areas, p.strengths,
        ]
        non_empty_lists = sum(1 for lst in list_fields if lst)
        total_fields = len(all_fields) + len(list_fields)
        filled = set_count + non_empty_lists

        p.total_fields_set = filled
        p.completeness_pct = (filled / total_fields * 100) if total_fields > 0 else 0.0
