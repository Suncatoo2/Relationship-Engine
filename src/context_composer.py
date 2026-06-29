"""Context Composer — 从 Projection 输出组装 ContextObject

Deep Module: small interface (compose), deep implementation (private methods).
Pipeline 只调用 composer.compose(person, profiles) 一行。

Architecture Notes:
  - _boundary()          — Knowledge Boundary Injection (系统知道"自己不知道什么")
  - _adjust_confidence() — Confidence Engine (recency + confirmation → confidence)
  - _health()            — Relationship Health Score + 14d Forecast

Refactor Triggers (满足任一条件则抽出独立 Engine):
  - 超过 3 个调用方
  - 独立生命周期（例如需要自己的调度/缓存）
  - 独立配置需求（例如 health_scoring_config.json）
  - 圈复杂度持续增长超出 Composer 单一职责范围
"""

from datetime import datetime, timezone

from .protocol import (
    ContextObject, IdentityBlock, MemoryBlock, FactItem,
    RelationshipBlock, TimeBlock, EmotionBlock, GoalsBlock, GoalItem, SystemBlock,
)
from .memory_reasoner import MemoryReasoner


# ============================================================
#  Confidence Engine + Knowledge Boundary + Health Score
#  White-box testable, deterministic algorithms
# ============================================================

def _adjust_confidence(facts: list, fact_state) -> list:
    """动态调整置信度（recency + confirmation count）

    规则:
      - times_confirmed >= 5  AND 30天内有更新  → confidence += 0.05（cap 0.99）
      - 90天未更新  → confidence -= 0.2
      - 180天未更新 → confidence -= 0.4
      - 曾被 deprecated → confidence -= 0.1
    """
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    adjusted = []

    for f in facts:
        conf = f.confidence

        # recency
        created = getattr(f, "created_at", None) or getattr(f, "last_mentioned", None)
        days_old = 0
        if created:
            try:
                ts = datetime.fromisoformat(created)
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                days_old = (now - ts).days
            except (ValueError, TypeError):
                pass

        # confirmation boost
        times = getattr(f, "times_confirmed", 1)
        if times >= 5 and days_old < 30:
            conf = min(0.99, conf + 0.05)

        # recency decay
        if days_old > 180:
            conf = max(0.05, conf - 0.4)
        elif days_old > 90:
            conf = max(0.05, conf - 0.2)

        # deprecation penalty
        if getattr(f, "status", "active") in ("deprecated", "overwritten"):
            conf = max(0.05, conf - 0.1)

        adjusted.append(FactItem(
            content=f.content, category=f.category,
            confidence=round(conf, 2), importance=f.importance,
            source=f.source, status=f.status,
        ))

    return adjusted


def _compute_boundary(profiles: dict, person: str) -> FactItem | None:
    """知识边界注入：time_gap > 阈值 → SYSTEM fact

    当 Engine 没有足够的近期证据时，
    生成一个低置信度的 SYSTEM fact，
    告诉 LLM "我不知道"而不是让它编造。
    """
    from datetime import datetime, timezone

    tp = profiles.get("TimeContextProjection")
    if tp is None or not isinstance(tp, dict):
        return None

    profile = tp.get(person)
    if profile is None:
        return None

    days = getattr(profile, "days_since_last_chat", -1)
    if days < 0:
        return None

    now = datetime.now(timezone.utc).isoformat()

    if days > 60:
        return FactItem(
            content=f"The engine has insufficient evidence about {person}'s recent state. No interaction in {days} days.",
            category="SYSTEM",
            confidence=0.08,
            importance=9,
            source="knowledge_boundary",
            status="active",
        )

    if days > 30:
        return FactItem(
            content=f"The engine's knowledge about {person} is becoming outdated. Last interaction was {days} days ago.",
            category="SYSTEM",
            confidence=0.25,
            importance=7,
            source="knowledge_boundary",
            status="active",
        )

    return None


def _compute_health(profiles: dict, person: str) -> dict | None:
    """Relationship Health Score (0-100) + 14d Forecast

    基于:
      - last_contact_days（距离上次联系的天数）
      - decay_chemistry（衰减后的好感度）
      - lifecycle（关系季节）
      - emotion_momentum（情绪动量）
    """
    rp = profiles.get("RelationshipProjection")
    ep = profiles.get("EmotionProjection")

    if rp is None or not isinstance(rp, dict):
        return None

    rel = rp.get(person)
    if rel is None or not hasattr(rel, "last_contact_days"):
        return None

    # 基础分: chemistry（衰减后的，0-100）
    base = getattr(rel, "decay_chemistry", 50)

    # 联系频率惩罚
    contact_days = getattr(rel, "last_contact_days", 0)
    if contact_days < 0:
        contact_penalty = 0
    elif contact_days == 0:
        contact_penalty = 0
    elif contact_days <= 3:
        contact_penalty = 0
    elif contact_days <= 7:
        contact_penalty = 5
    elif contact_days <= 14:
        contact_penalty = 10
    elif contact_days <= 30:
        contact_penalty = 20
    else:
        contact_penalty = min(40, contact_days)  # cap at 40

    # 生命周期调整
    lifecycle = getattr(rel, "lifecycle", "")
    lifecycle_bonus = {"spring": 10, "summer": 15, "autumn": 0, "winter": -20}
    lc_adj = lifecycle_bonus.get(lifecycle, 0)

    # 情绪动量
    momentum_factor = 0
    if ep and isinstance(ep, dict):
        emo = ep.get(person)
        if emo and hasattr(emo, "momentum") and emo.momentum:
            momentum_val = emo.momentum.get("value", 0)
            momentum_factor = int(momentum_val * 10)  # -10 to +10

    # 计算
    score = base - contact_penalty + lc_adj + momentum_factor
    score = max(0, min(100, score))

    # 14天预测（假设无新联系）
    forecast_contact_penalty = min(40, contact_days + 14) if contact_days > 0 else 14
    forecast = base - forecast_contact_penalty + lc_adj + momentum_factor
    forecast = max(0, min(100, forecast))

    return {
        "score": score,
        "forecast_14d": forecast,
        "factors": {
            "base_chemistry": base,
            "contact_penalty": contact_penalty,
            "lifecycle": lifecycle,
            "lifecycle_adjustment": lc_adj,
            "emotion_momentum": momentum_factor,
        },
    }


# ============================================================


class ContextComposer:
    """从 profiles 组装 ContextObject"""

    def __init__(self,
                 enable_suggestions: bool = True,
                 enable_lifecycle: bool = True):
        self._reasoner = MemoryReasoner()
        self.enable_suggestions = enable_suggestions
        self.enable_lifecycle = enable_lifecycle

    def compose(self, person: str, person_events: list,
                profiles: dict[str, dict]) -> ContextObject:
        """组装 ContextObject，填充所有 Block

        Args:
            person: 人物名称
            person_events: 该人物的事件列表（用于 metadata）
            profiles: Dispatcher.project_all() 的输出
        """
        # 1. 先组装基础 blocks
        memory = self._memory(profiles, person)
        relationship = self._relationship(profiles, person)
        time = self._time(profiles, person)
        emotion = self._emotion(profiles, person)

        # 2. 用 Reasoner 生成 summary，写入 MemoryBlock
        temp_ctx = ContextObject(
            identity=self._identity(person),
            memory=memory,
            relationship=relationship,
            time=time,
            emotion=emotion,
            growth=self._growth(profiles, person),
            system=self._system(person_events),
        )
        reasoner_output = self._reasoner.reason(temp_ctx)

        # 3. 把 summary 写入 MemoryBlock（frozen，需要重建）
        memory_with_summary = MemoryBlock(
            active_facts=memory.active_facts,
            fact_count=memory.fact_count,
            memory_summary=reasoner_output.summary,
            top_topics=memory.top_topics,
        )

        return ContextObject(
            identity=self._identity(person),
            memory=memory_with_summary,
            relationship=relationship,
            time=time,
            emotion=emotion,
            growth=self._growth(profiles, person),
            goals=self._goals(profiles, person),
            suggestions=self._suggestions(profiles, person) if self.enable_suggestions else [],
            system=self._system(person_events),
            last_consumed_event_id=person_events[-1].event_id if person_events else "",
        )

    # ---- 4 must blocks ----

    @staticmethod
    def _identity(person: str) -> IdentityBlock:
        return IdentityBlock(name=person)

    @staticmethod
    def _memory(profiles: dict, person: str) -> MemoryBlock:
        """FactProjection → MemoryBlock + Confidence Adjustment + Knowledge Boundary"""
        active_facts: list = []
        fact_state = profiles.get("FactProjection")
        all_facts = []

        if fact_state is not None and hasattr(fact_state, "active"):
            for _cat, f in fact_state.active.items():
                item = FactItem(
                    content=f.content, category=f.category,
                    confidence=f.confidence, importance=f.importance,
                    source=f.source, status=f.status,
                )
                all_facts.append(item)

        # 置信度动态调整（recency + times_confirmed）
        all_facts = _adjust_confidence(all_facts, fact_state)

        # 知识边界注入（time_gap > 阈值 → SYSTEM fact）
        boundary = _compute_boundary(profiles, person)
        if boundary:
            all_facts.append(boundary)

        return MemoryBlock(active_facts=all_facts, fact_count=len(all_facts))

    @staticmethod
    def _relationship(profiles: dict, person: str) -> RelationshipBlock:
        """RelationshipProjection → RelationshipBlock"""
        rp = profiles.get("RelationshipProjection")
        if rp is None or not isinstance(rp, dict):
            return RelationshipBlock()

        profile = rp.get(person)
        if profile is None or not hasattr(profile, "stage"):
            return RelationshipBlock()

        # last_contact_summary: 从 days 生成人话
        days = getattr(profile, "last_contact_days", -1)
        if days == 0:
            contact_summary = "今天刚聊过"
        elif days == 1:
            contact_summary = "昨天聊过"
        elif days > 1:
            contact_summary = f"{days}天前聊过"
        else:
            contact_summary = ""

        # milestones: 取最近 3 个
        milestones = []
        for m in getattr(profile, "milestones", [])[-3:]:
            milestones.append(m.description if hasattr(m, "description") else str(m))

        return RelationshipBlock(
            stage=getattr(profile, "stage", "陌生人"),
            chemistry=getattr(profile, "base_chemistry", 0),
            decay_chemistry=getattr(profile, "decay_chemistry", 0),
            trend=getattr(profile, "trend", "稳定"),
            last_contact_summary=contact_summary,
            milestones=milestones,
        )

    @staticmethod
    def _time(profiles: dict, person: str) -> TimeBlock:
        """TimeContextProjection → TimeBlock"""
        tp = profiles.get("TimeContextProjection")
        if tp is None or not isinstance(tp, dict):
            return TimeBlock()

        profile = tp.get(person)
        if profile is None or not hasattr(profile, "last_chat_label"):
            return TimeBlock()

        # upcoming: 从 landmarks 提取未来事件
        upcoming = []
        for lm in getattr(profile, "landmarks", []):
            if hasattr(lm, "label") and hasattr(lm, "days_until"):
                if lm.days_until is not None and lm.days_until > 0:
                    upcoming.append(lm.label)

        return TimeBlock(
            last_chat_label=getattr(profile, "last_chat_label", ""),
            silence_label=getattr(profile.silence, "label", "") if getattr(profile, "silence", None) else "",
            upcoming=upcoming,
            days_known=getattr(profile, "days_since_first_met", 0),
        )

    @staticmethod
    def _emotion(profiles: dict, person: str) -> EmotionBlock | None:
        """EmotionProjection → EmotionBlock"""
        ep = profiles.get("EmotionProjection")
        if ep is None or not isinstance(ep, dict):
            return None

        profile = ep.get(person)
        if profile is None:
            return None

        trend_val = getattr(profile, "trend", None)
        trend_str = trend_val.value if hasattr(trend_val, "value") else str(trend_val or "")

        dominant = getattr(profile, "dominant_emotion", "")
        if not dominant:
            return None

        # alert: 取第一个 alert 的 message
        alerts = getattr(profile, "alerts", [])
        alert_msg = getattr(alerts[0], "message", "") if alerts else ""

        return EmotionBlock(
            trend=trend_str,
            dominant_emotion=dominant,
            alert=alert_msg,
        )

    @staticmethod
    def _growth(profiles: dict, person: str) -> dict | None:
        """GrowthProjection → growth dict"""
        gp = profiles.get("GrowthProjection")
        if gp is None or not isinstance(gp, dict):
            return None

        profile = gp.get(person)
        if profile is None:
            return None

        nodes = getattr(profile, "timeline", [])
        if not nodes:
            return None

        recent = []
        for n in nodes[-5:]:
            recent.append({
                "title": getattr(n, "title", ""),
                "category": getattr(n, "category", ""),
                "impact": getattr(n, "impact_level", 0),
            })

        return {
            "total_nodes": getattr(profile, "total_nodes", len(nodes)),
            "recent": recent,
        }

    @staticmethod
    def _system(person_events: list) -> SystemBlock:
        return SystemBlock(
            version=1,
            generated_at=datetime.now(timezone.utc).isoformat(),
            event_count=len(person_events),
        )

    @staticmethod
    def _goals(profiles: dict, person: str) -> GoalsBlock | None:
        """FactProjection(category=goal) → GoalsBlock"""
        fact_state = profiles.get("FactProjection")
        if fact_state is None or not hasattr(fact_state, "active"):
            return None

        active_goals: list = []
        completed_goals: list = []

        for cat, f in fact_state.active.items():
            if cat != "goal":
                continue
            item = GoalItem(
                title=f.content,
                category="goal",
                status=f.status,
                last_mentioned=f.last_confirmed or f.created_at,
                confidence=f.confidence,
            )
            if f.status in ("active", "confirmed"):
                active_goals.append(item)
            elif f.status in ("completed", "achieved"):
                completed_goals.append(item)

        # 也检查 deprecated 里的 goals
        for f in getattr(fact_state, "deprecated", []):
            if getattr(f, "category", "") == "goal":
                completed_goals.append(GoalItem(
                    title=f.content, category="goal",
                    status="completed", confidence=f.confidence,
                ))

        if not active_goals and not completed_goals:
            return None

        return GoalsBlock(
            active_goals=active_goals,
            completed_goals=completed_goals,
            goal_count=len(active_goals) + len(completed_goals),
        )

    def _suggestions(self, profiles: dict, person: str) -> list[str]:
        """Proactive Suggestions（Engine Detects, ADR-007）

        确定性规则检测，不是 LLM 推理。
        每个 suggestion 都是可断言的事实陈述。
        """
        suggestions: list[str] = []

        # 1. 长期未联系
        rp = profiles.get("RelationshipProjection")
        if rp and isinstance(rp, dict):
            profile = rp.get(person)
            if profile and hasattr(profile, "last_contact_days"):
                days = profile.last_contact_days
                if days >= 30:
                    suggestions.append(f"{person} 已经 {days} 天没有联系了")
                elif days >= 14:
                    suggestions.append(f"{person} 已经 {days} 天没有联系")

                # 关系生命周期检测
                if self.enable_lifecycle and hasattr(profile, "lifecycle"):
                    lc = profile.lifecycle
                    if lc == "winter":
                        suggestions.append(f"与 {person} 的关系正在进入冬季（{profile.lifecycle_detail}）")
                    elif lc == "autumn" and days >= 14:
                        suggestions.append(f"与 {person} 的关系正在进入秋季（{profile.lifecycle_detail}）")

        # 2. 生日临近
        tp = profiles.get("TimeContextProjection")
        if tp and isinstance(tp, dict):
            profile = tp.get(person)
            if profile and hasattr(profile, "landmarks"):
                for lm in profile.landmarks:
                    if hasattr(lm, "days_until") and lm.days_until is not None:
                        if 0 < lm.days_until <= 7:
                            suggestions.append(f"{person} 的 {getattr(lm, 'label', '纪念日')} 还有 {lm.days_until} 天")

        # 3. 情绪连续下降
        ep = profiles.get("EmotionProjection")
        if ep and isinstance(ep, dict):
            profile = ep.get(person)
            if profile and hasattr(profile, "alerts") and profile.alerts:
                for alert in profile.alerts:
                    if hasattr(alert, "message"):
                        suggestions.append(f"情绪警报: {alert.message}")

        # 4. 目标长期未提及
        fact_state = profiles.get("FactProjection")
        if fact_state and hasattr(fact_state, "active"):
            for cat, f in fact_state.active.items():
                if cat == "goal" and hasattr(f, "created_at") and f.created_at:
                    from .projections.base import Projection as BaseProj
                    days_since = BaseProj.days_since(f.created_at)
                    if days_since > 90:
                        suggestions.append(f"目标 \"{f.content}\" 已经 {days_since} 天没有更新")

        return suggestions
