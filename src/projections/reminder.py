"""Reminder Projection — 智能提醒投影

综合多种事件生成提醒，不是简单的日期检查。

提醒类型：
  - Event Reminder:       生日、纪念日（固定日期）
  - Relationship Reminder: 失联警告（计算得出）
  - Emotion Reminder:     情绪关怀（趋势分析）
  - Growth Reminder:      成长停滞（时间跨度）
  - Custom Reminder:      用户手动创建

触发机制（ReminderTrigger）：
  - date:      固定日期触发（生日、纪念日）
  - inactivity: 沉默天数触发（45天没联系）
  - emotion:   情绪条件触发（连续5天低落）
  - stage:     关系阶段触发（进入冷淡期）

状态（ReminderStatus）：
  - pending:   待提醒
  - dismissed: 用户忽略
  - completed: 用户完成
  - expired:   已过期
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum

from ..event_types import Event, EventType
from .base import Projection


# ---- 枚举 ----

class ReminderType(str, Enum):
    EVENT = "event"
    RELATIONSHIP = "relationship"
    EMOTION = "emotion"
    GROWTH = "growth"
    CUSTOM = "custom"


class ReminderStatus(str, Enum):
    PENDING = "pending"
    DISMISSED = "dismissed"
    COMPLETED = "completed"
    EXPIRED = "expired"


class TriggerType(str, Enum):
    DATE = "date"
    INACTIVITY = "inactivity"
    EMOTION = "emotion"
    STAGE = "stage"


class Urgency(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


# ---- 数据结构 ----

@dataclass
class ReminderTrigger:
    """触发条件（多态：日期 / 沉默 / 情绪 / 阶段）"""
    type: TriggerType
    date: str = ""              # type=date 时使用
    days: int = 0               # type=inactivity 时使用
    condition: str = ""         # type=emotion/stage 时使用

    def to_dict(self) -> dict:
        d = {"type": self.type.value}
        if self.date:
            d["date"] = self.date
        if self.days:
            d["days"] = self.days
        if self.condition:
            d["condition"] = self.condition
        return d


@dataclass
class ReminderItem:
    """一条提醒"""
    person_name: str
    reminder_type: ReminderType
    message: str
    urgency: Urgency
    trigger: ReminderTrigger
    status: ReminderStatus = ReminderStatus.PENDING
    days_until: int = 0
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "person_name": self.person_name,
            "reminder_type": self.reminder_type.value,
            "message": self.message,
            "urgency": self.urgency.value,
            "trigger": self.trigger.to_dict(),
            "status": self.status.value,
            "days_until": self.days_until,
            "metadata": self.metadata,
        }


@dataclass
class ReminderProfile:
    """提醒集合"""
    items: list[ReminderItem] = field(default_factory=list)
    total: int = 0
    pending: int = 0
    high_urgency: int = 0
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "items": [i.to_dict() for i in self.items],
            "total": self.total,
            "pending": self.pending,
            "high_urgency": self.high_urgency,
            "metadata": self.metadata,
        }


# ---- Projection ----

class ReminderProjection(Projection):
    """智能提醒投影"""

    def project(self, events) -> ReminderProfile:
        event_list = list(events)
        now = datetime.now(timezone.utc)
        items: list[ReminderItem] = []

        # 按人物分组
        by_person: dict[str, list[Event]] = {}
        for e in event_list:
            if e.person:
                by_person.setdefault(e.person, []).append(e)

        for name, person_events in by_person.items():
            items.extend(self._check_event_reminders(name, person_events, now))
            items.extend(self._check_relationship_reminders(name, person_events, now))
            items.extend(self._check_emotion_reminders(name, person_events, now))
            items.extend(self._check_growth_reminders(name, person_events, now))
            items.extend(self._check_custom_reminders(name, person_events, now))

        # 排序：urgency 高的在前
        urgency_order = {Urgency.HIGH: 0, Urgency.MEDIUM: 1, Urgency.LOW: 2}
        items.sort(key=lambda i: (urgency_order.get(i.urgency, 3), i.days_until))

        pending = [i for i in items if i.status == ReminderStatus.PENDING]
        high = [i for i in items if i.urgency == Urgency.HIGH and i.status == ReminderStatus.PENDING]

        return ReminderProfile(
            items=items,
            total=len(items),
            pending=len(pending),
            high_urgency=len(high),
            metadata={
                "generated_at": now.isoformat(),
                "source_event_count": len(event_list),
                "version": "1.0",
            },
        )

    # ---- Event Reminder（生日、纪念日） ----

    def _check_event_reminders(self, name: str, events: list[Event], now: datetime) -> list[ReminderItem]:
        items = []
        for e in events:
            if e.type == EventType.PERSON:
                birthday = e.data.get("birthday", "")
                if birthday:
                    item = self._check_birthday(name, birthday, now)
                    if item:
                        items.append(item)

            if e.type == EventType.MILESTONE:
                # 纪念日提醒
                ts = self._parse_ts(e.timestamp)
                if ts:
                    days_since = (now - ts).days
                    for n in [100, 200, 365]:
                        target = ts + timedelta(days=n)
                        days_until = (target - now).days
                        if 0 <= days_until <= 7:
                            items.append(ReminderItem(
                                person_name=name,
                                reminder_type=ReminderType.EVENT,
                                message=f"{e.data.get('description', '纪念日')}的第{n}天纪念还有{days_until}天",
                                urgency=Urgency.MEDIUM,
                                trigger=ReminderTrigger(type=TriggerType.DATE, date=target.strftime("%Y-%m-%d")),
                                days_until=days_until,
                            ))
        return items

    def _check_birthday(self, name: str, birthday: str, now: datetime) -> ReminderItem | None:
        try:
            bd = datetime.strptime(birthday, "%Y-%m-%d")
            now_date = now.date()
            # 今年的生日
            this_year_bd = bd.replace(year=now.year).date()
            days_until = (this_year_bd - now_date).days
            if days_until < 0:
                # 明年的生日
                next_year_bd = bd.replace(year=now.year + 1).date()
                days_until = (next_year_bd - now_date).days
            if 0 <= days_until <= 7:
                urgency = Urgency.HIGH if days_until <= 3 else Urgency.MEDIUM
                label = "今天" if days_until == 0 else f"还有{days_until}天"
                return ReminderItem(
                    person_name=name,
                    reminder_type=ReminderType.EVENT,
                    message=f"{name}的生日{label}！",
                    urgency=urgency,
                    trigger=ReminderTrigger(type=TriggerType.DATE, date=birthday),
                    days_until=days_until,
                )
        except (ValueError, TypeError):
            pass
        return None

    # ---- Relationship Reminder（失联警告） ----

    def _check_relationship_reminders(self, name: str, events: list[Event], now: datetime) -> list[ReminderItem]:
        items = []
        # 找最后一条 chat 事件
        chat_events = [e for e in events if e.type == EventType.CHAT]
        if chat_events:
            latest = max(chat_events, key=lambda e: e.timestamp)
            ts = self._parse_ts(latest.timestamp)
            if ts:
                days = (now - ts).days
                if days >= 7:
                    urgency = Urgency.HIGH if days >= 14 else Urgency.MEDIUM
                    items.append(ReminderItem(
                        person_name=name,
                        reminder_type=ReminderType.RELATIONSHIP,
                        message=f"已经{days}天没有联系{name}了",
                        urgency=urgency,
                        trigger=ReminderTrigger(type=TriggerType.INACTIVITY, days=days),
                        days_until=0,
                    ))
        return items

    # ---- Emotion Reminder（情绪关怀） ----

    def _check_emotion_reminders(self, name: str, events: list[Event], now: datetime) -> list[ReminderItem]:
        items = []
        emotion_events = [e for e in events if e.type == EventType.EMOTION]
        if len(emotion_events) < 3:
            return items

        # 最近 5 条情绪
        recent = sorted(emotion_events, key=lambda e: e.timestamp)[-5:]
        recent_vals = [e.data.get("valence", 0) for e in recent]

        if len(recent_vals) >= 3 and all(v < -0.3 for v in recent_vals[-3:]):
            items.append(ReminderItem(
                person_name=name,
                reminder_type=ReminderType.EMOTION,
                message=f"{name}最近情绪持续低落，聊天时可以多关心一下",
                urgency=Urgency.HIGH,
                trigger=ReminderTrigger(type=TriggerType.EMOTION, condition="negative_3_days"),
                days_until=0,
            ))
        return items

    # ---- Growth Reminder（成长停滞） ----

    def _check_growth_reminders(self, name: str, events: list[Event], now: datetime) -> list[ReminderItem]:
        items = []
        growth_events = [e for e in events if e.type == EventType.GROWTH]
        if not growth_events:
            return items

        latest = max(growth_events, key=lambda e: e.timestamp)
        ts = self._parse_ts(latest.timestamp)
        if ts:
            days = (now - ts).days
            if days >= 90:
                items.append(ReminderItem(
                    person_name=name,
                    reminder_type=ReminderType.GROWTH,
                    message=f"已经{days}天没有记录{name}的成长了",
                    urgency=Urgency.LOW,
                    trigger=ReminderTrigger(type=TriggerType.INACTIVITY, days=days),
                    days_until=0,
                ))
        return items

    # ---- Custom Reminder（用户手动创建） ----

    def _check_custom_reminders(self, name: str, events: list[Event], now: datetime) -> list[ReminderItem]:
        items = []
        for e in events:
            if e.type == EventType.REMINDER:
                data = e.data
                status = ReminderStatus(data.get("status", "pending"))
                if status != ReminderStatus.PENDING:
                    continue
                trigger_date = data.get("trigger_date", "")
                days_until = 0
                if trigger_date:
                    try:
                        td = datetime.strptime(trigger_date, "%Y-%m-%d")
                        days_until = (td - now).days
                    except (ValueError, TypeError):
                        pass
                items.append(ReminderItem(
                    person_name=name,
                    reminder_type=ReminderType.CUSTOM,
                    message=data.get("message", ""),
                    urgency=Urgency(data.get("urgency", "medium")),
                    trigger=ReminderTrigger(type=TriggerType.DATE, date=trigger_date),
                    status=status,
                    days_until=days_until,
                ))
        return items

    @staticmethod
    def _parse_ts(ts_str: str) -> datetime | None:
        try:
            ts = datetime.fromisoformat(ts_str)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            return ts
        except (ValueError, TypeError):
            return None
