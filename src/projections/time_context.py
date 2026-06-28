"""Time Context Projection — 时间感知投影

不是"现在是什么时候"，而是"这件事情发生在什么时间背景下"。

输出的不是绝对时间，而是相对时间：
  - 距离上次聊天多久
  - 距离第一次认识多久
  - 最近互动密度
  - 互动时间段分布
  - 沉默期检测
  - 即将到来的里程碑

输入事件类型：
  - chat:     聊天时间戳 → 密度、时间段、沉默
  - person:   创建时间 → first_met
  - relation: 关系变化时间 → 最后联系
  - milestone: 里程碑时间 → 前瞻提醒
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from collections import Counter

from ..event_types import Event, EventType
from .base import Projection


# ---- 数据结构 ----

@dataclass
class DensityInfo:
    """互动密度"""
    period_days: int        # 统计周期（天）
    event_count: int        # 事件数量
    daily_avg: float        # 日均事件数
    label: str              # "很密集" / "正常" / "稀疏" / "几乎没有"

    def to_dict(self) -> dict:
        return {
            "period_days": self.period_days,
            "event_count": self.event_count,
            "daily_avg": round(self.daily_avg, 1),
            "label": self.label,
        }


@dataclass
class PeriodDistribution:
    """互动时间段分布"""
    morning: int = 0        # 6-12
    afternoon: int = 0      # 12-18
    evening: int = 0        # 18-24
    night: int = 0          # 0-6
    weekday: int = 0        # 工作日
    weekend: int = 0        # 周末
    dominant_period: str = ""
    dominant_day_type: str = ""

    def to_dict(self) -> dict:
        return {
            "morning": self.morning,
            "afternoon": self.afternoon,
            "evening": self.evening,
            "night": self.night,
            "weekday": self.weekday,
            "weekend": self.weekend,
            "dominant_period": self.dominant_period,
            "dominant_day_type": self.dominant_day_type,
        }


@dataclass
class SilenceInfo:
    """沉默信息"""
    silence_days: int       # 连续沉默天数
    status: str             # "active" / "quiet" / "inactive" / "dormant"
    label: str              # "刚聊完" / "几天没聊" / "很久没联系" / "已经失联"

    def to_dict(self) -> dict:
        return {
            "silence_days": self.silence_days,
            "status": self.status,
            "label": self.label,
        }


@dataclass
class ActiveWindow:
    """关系活跃窗口"""
    first_event: str        # 第一个事件时间
    last_event: str         # 最后一个事件时间
    total_days: int         # 总天数
    total_events: int       # 总事件数
    label: str              # "刚认识" / "认识不久" / "认识一段时间了" / "认识很久了"

    def to_dict(self) -> dict:
        return {
            "first_event": self.first_event,
            "last_event": self.last_event,
            "total_days": self.total_days,
            "total_events": self.total_events,
            "label": self.label,
        }


@dataclass
class Landmark:
    """时间锚点"""
    name: str               # "认识一周年" / "第一次聊天100天"
    date: str               # 锚点日期
    days_until: int         # 距今多少天（负数表示已过）
    label: str              # "还有3天" / "今天" / "已经过了"

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "date": self.date,
            "days_until": self.days_until,
            "label": self.label,
        }


@dataclass
class TimeContextProfile:
    """时间感知上下文"""
    person_name: str

    # 相对时间
    days_since_last_chat: int = -1
    days_since_first_met: int = -1
    days_since_last_contact: int = -1
    last_chat_label: str = ""
    first_met_label: str = ""
    memory_freshness: float = 0.0   # 0~1，记忆新鲜度

    # 时间尺度
    time_scale: str = ""            # "刚刚" / "最近" / "前段时间" / "很久以前"

    # 密度
    density_7d: DensityInfo | None = None
    density_30d: DensityInfo | None = None

    # 时间段
    period: PeriodDistribution | None = None

    # 沉默
    silence: SilenceInfo | None = None

    # 活跃窗口
    active_window: ActiveWindow | None = None

    # 锚点
    landmarks: list[Landmark] = field(default_factory=list)

    # 人生阶段
    life_stage: str = ""

    # ---- v2.5 扩展接口（当前为 None，未来填充） ----
    rhythm: dict | None = None          # Relationship Rhythm（节奏模式）
    flow: dict | None = None            # Relationship Flow（关系流向）
    density_detail: dict | None = None  # Memory Density 增强（average_interval, interaction_gap）

    # metadata
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = {
            "person_name": self.person_name,
            "days_since_last_chat": self.days_since_last_chat,
            "days_since_first_met": self.days_since_first_met,
            "days_since_last_contact": self.days_since_last_contact,
            "last_chat_label": self.last_chat_label,
            "first_met_label": self.first_met_label,
            "memory_freshness": round(self.memory_freshness, 2),
            "time_scale": self.time_scale,
            "silence": self.silence.to_dict() if self.silence else None,
            "active_window": self.active_window.to_dict() if self.active_window else None,
            "landmarks": [l.to_dict() for l in self.landmarks],
            "life_stage": self.life_stage,
            "rhythm": self.rhythm,
            "flow": self.flow,
            "density_detail": self.density_detail,
            "metadata": self.metadata,
        }
        if self.density_7d:
            d["density_7d"] = self.density_7d.to_dict()
        if self.density_30d:
            d["density_30d"] = self.density_30d.to_dict()
        if self.period:
            d["period"] = self.period.to_dict()
        return d


# ---- Projection ----

class TimeContextProjection(Projection):
    """时间感知投影"""

    def project(self, events) -> dict[str, TimeContextProfile]:
        profiles: dict[str, TimeContextProfile] = {}
        event_list = list(events)

        # 按人物分组
        by_person: dict[str, list[Event]] = {}
        for e in event_list:
            if e.person:
                if e.person not in by_person:
                    by_person[e.person] = []
                by_person[e.person].append(e)

        for name, person_events in by_person.items():
            profiles[name] = self._build_profile(name, person_events)

        return profiles

    def project_one(self, events, name: str) -> TimeContextProfile | None:
        return self.project(events).get(name)

    def _build_profile(self, name: str, events: list[Event]) -> TimeContextProfile:
        p = TimeContextProfile(person_name=name)
        now = datetime.now(timezone.utc)

        chat_events = [e for e in events if e.type == EventType.CHAT]
        person_events = [e for e in events if e.type == EventType.PERSON]
        milestone_events = [e for e in events if e.type == EventType.MILESTONE]

        all_timestamps = [self.parse_ts(e.occurred_at) for e in events if self.parse_ts(e.occurred_at)]
        chat_timestamps = [self.parse_ts(e.occurred_at) for e in chat_events if self.parse_ts(e.occurred_at)]

        # 相对时间
        if chat_timestamps:
            latest_chat = max(chat_timestamps)
            p.days_since_last_chat = (now - latest_chat).days
            p.last_chat_label = self._interval_label(p.days_since_last_chat)

        if all_timestamps:
            earliest = min(all_timestamps)
            p.days_since_first_met = (now - earliest).days
            p.first_met_label = self._interval_label(p.days_since_first_met)

        # 最后联系（所有事件）
        if all_timestamps:
            p.days_since_last_contact = (now - max(all_timestamps)).days

        # memory_freshness + time_scale
        ref_days = p.days_since_last_chat if p.days_since_last_chat >= 0 else p.days_since_last_contact
        if ref_days >= 0:
            p.memory_freshness = 1.0 / (1.0 + 0.01 * ref_days)
            p.time_scale = self._time_scale(ref_days)

        # 密度
        p.density_7d = self._compute_density(chat_timestamps, now, 7)
        p.density_30d = self._compute_density(chat_timestamps, now, 30)

        # 时间段
        if chat_timestamps:
            p.period = self._compute_period(chat_timestamps)

        # 沉默
        p.silence = self._compute_silence(p.days_since_last_contact)

        # 活跃窗口
        if all_timestamps:
            p.active_window = self._compute_active_window(all_timestamps, len(events))

        # 锚点
        if all_timestamps:
            p.landmarks = self._compute_landmarks(all_timestamps, chat_timestamps, milestone_events, now)

        # metadata
        p.metadata = {
            "generated_at": now.isoformat(),
            "source_event_count": len(events),
            "version": "1.0",
        }

        return p

    # ---- 辅助计算 ----

    def _interval_label(self, days: int) -> str:
        if days < 0:
            return ""
        if days == 0:
            return "今天"
        if days == 1:
            return "昨天"
        if days <= 3:
            return f"{days}天前"
        if days <= 7:
            return "最近几天"
        if days <= 14:
            return "一两周前"
        if days <= 30:
            return "最近一个月"
        if days <= 90:
            return "最近几个月"
        if days <= 180:
            return "半年前"
        if days <= 365:
            return "快一年了"
        years = days // 365
        return f"{years}年多前"

    def _time_scale(self, days: int) -> str:
        """时间尺度：人感受时间的方式"""
        if days <= 1:
            return "刚刚"
        if days <= 7:
            return "最近"
        if days <= 30:
            return "前段时间"
        if days <= 180:
            return "很久以前"
        return "很久很久以前"

    def _compute_density(self, timestamps: list[datetime], now: datetime, days: int) -> DensityInfo | None:
        if not timestamps:
            return None
        cutoff = now - timedelta(days=days)
        count = sum(1 for ts in timestamps if ts >= cutoff)
        daily_avg = count / days if days > 0 else 0

        if daily_avg >= 3:
            label = "很密集"
        elif daily_avg >= 1:
            label = "正常"
        elif daily_avg >= 0.2:
            label = "稀疏"
        else:
            label = "几乎没有"

        return DensityInfo(period_days=days, event_count=count, daily_avg=daily_avg, label=label)

    def _compute_period(self, timestamps: list[datetime]) -> PeriodDistribution:
        dist = PeriodDistribution()
        for ts in timestamps:
            hour = ts.hour
            if 6 <= hour < 12:
                dist.morning += 1
            elif 12 <= hour < 18:
                dist.afternoon += 1
            elif 18 <= hour < 24:
                dist.evening += 1
            else:
                dist.night += 1

            if ts.weekday() < 5:
                dist.weekday += 1
            else:
                dist.weekend += 1

        total = len(timestamps)
        if total > 0:
            period_counts = {
                "morning": dist.morning,
                "afternoon": dist.afternoon,
                "evening": dist.evening,
                "night": dist.night,
            }
            dist.dominant_period = max(period_counts, key=period_counts.get)
            dist.dominant_day_type = "weekday" if dist.weekday >= dist.weekend else "weekend"

        return dist

    def _compute_silence(self, days_since_last: int) -> SilenceInfo:
        if days_since_last < 0:
            return SilenceInfo(silence_days=0, status="active", label="暂无记录")
        if days_since_last == 0:
            return SilenceInfo(silence_days=0, status="active", label="今天聊过")
        if days_since_last <= 3:
            return SilenceInfo(silence_days=days_since_last, status="active", label=f"{days_since_last}天没聊")
        if days_since_last <= 7:
            return SilenceInfo(silence_days=days_since_last, status="quiet", label="几天没聊了")
        if days_since_last <= 30:
            return SilenceInfo(silence_days=days_since_last, status="inactive", label="很久没联系了")
        return SilenceInfo(silence_days=days_since_last, status="dormant", label="已经失联了")

    def _compute_active_window(self, timestamps: list[datetime], event_count: int) -> ActiveWindow:
        first = min(timestamps)
        last = max(timestamps)
        total_days = (last - first).days

        if total_days <= 7:
            label = "刚认识"
        elif total_days <= 30:
            label = "认识不久"
        elif total_days <= 180:
            label = "认识一段时间了"
        else:
            label = "认识很久了"

        return ActiveWindow(
            first_event=first.isoformat(),
            last_event=last.isoformat(),
            total_days=total_days,
            total_events=event_count,
            label=label,
        )

    def _compute_landmarks(self, all_ts: list[datetime], chat_ts: list[datetime],
                           milestones: list[Event], now: datetime) -> list[Landmark]:
        landmarks = []
        earliest = min(all_ts)

        # 认识 N 周年
        for year in range(1, 10):
            anniversary = earliest.replace(year=earliest.year + year)
            if anniversary > now:
                days_until = (anniversary - now).days
                if days_until <= 30:
                    landmarks.append(Landmark(
                        name=f"认识{year}周年",
                        date=anniversary.strftime("%Y-%m-%d"),
                        days_until=days_until,
                        label=f"还有{days_until}天" if days_until > 0 else "今天",
                    ))
                break

        # 认识 100 天、200 天、365 天...
        for n in [100, 200, 365, 500, 1000]:
            target = earliest + timedelta(days=n)
            if target > now:
                days_until = (target - now).days
                if days_until <= 30:
                    landmarks.append(Landmark(
                        name=f"认识第{n}天",
                        date=target.strftime("%Y-%m-%d"),
                        days_until=days_until,
                        label=f"还有{days_until}天" if days_until > 0 else "今天",
                    ))

        return landmarks


