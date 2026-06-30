"""Interaction Pipeline — 唯一事件入口

ADR-005: 高层只有一个入口 — publish_interaction()
ADR-006: 只有 Pipeline 可以访问 Event Store
ADR-006-SLIM: Pipeline 自身不超过 150 行。只做协调，不负责实现。

Pipeline 不直接操作文件或数据库——所有 IO 必须经过 Storage 接口。
Pipeline 不知道 Dispatcher 里有几个 Projection。
Pipeline 不负责事件分解——分解逻辑在 static factory 方法中。
"""

import uuid
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
import secrets

from .event_types import Event, create_event
from .storage import Storage, StorageCapability
from .dispatcher import ProjectionDispatcher
from .projections.base import Projection
from .protocol import ContextObject
from .context_composer import ContextComposer
from .snapshot_manager import SnapshotManager
from .pipeline_response import PipelineResponse, RecallMetadata, Diagnostics
from .retrieval_ranker import RetrievalRanker


# ============================================================
#  Input DTOs — lightweight, no logic
# ============================================================

@dataclass
class FactInput:
    """LLM 提取的事实"""
    content: str
    category: str = "general"
    importance: int = 5
    confidence: float = 0.9


@dataclass
class EmotionInput:
    """LLM 判断的情绪"""
    valence: float = 0.0
    arousal: float = 0.5
    label: str = ""
    context: str = ""


@dataclass
class RelationInput:
    """LLM 判断的关系变化"""
    stage: str = ""
    delta: int = 0
    event: str = ""


@dataclass
class MilestoneInput:
    """LLM 判断的里程碑"""
    milestone_type: str = ""
    description: str = ""
    significance: int = 8


@dataclass
class GrowthInput:
    """LLM 判断的成长"""
    title: str = ""
    category: str = ""
    description: str = ""
    impact_level: int = 5
    date: str = ""


@dataclass
class Interaction:
    """LLM 结构化后的交互数据"""
    message: str
    person: str = ""
    type: str = "chat"
    facts: list[FactInput] = field(default_factory=list)
    emotion: EmotionInput | None = None
    relation_change: RelationInput | None = None
    milestone: MilestoneInput | None = None
    growth: GrowthInput | None = None
    conversation_id: str = ""
    source: str = "user_input"


@dataclass
class PublishResult:
    """publish() 的返回结果"""
    event_id: str
    derived_event_ids: list[str] = field(default_factory=list)


# ============================================================
#  Event 构造（static，无状态，无业务逻辑）
# ============================================================

def make_chat_event(i: Interaction) -> Event:
    return create_event(type="chat", data={
        "role": "user", "content": i.message,
        "conversation_id": i.conversation_id,
    }, person=i.person, source=i.source)


def make_fact_event(i: Interaction, f: FactInput) -> Event:
    return create_event(type="fact", data={
        "content": f.content, "category": f.category,
        "importance": f.importance, "confidence": f.confidence,
        "source": "llm_extracted",
    }, person=i.person, source=i.source)


def make_emotion_event(i: Interaction) -> Event:
    return create_event(type="emotion", data={
        "valence": i.emotion.valence,
        "arousal": i.emotion.arousal,
        "label": i.emotion.label,
        "context": i.emotion.context,
    }, person=i.person, source=i.source)


def make_relation_event(i: Interaction) -> Event:
    r = i.relation_change
    return create_event(type="relation", data={
        "stage": r.stage or "", "delta": r.delta, "event": r.event or "",
    }, person=i.person, source=i.source)


def make_milestone_event(i: Interaction) -> Event:
    m = i.milestone
    return create_event(type="milestone", data={
        "milestone_type": m.milestone_type,
        "description": m.description,
        "significance": m.significance,
    }, person=i.person, source=i.source)


def make_growth_event(i: Interaction) -> Event:
    g = i.growth
    return create_event(type="growth", data={
        "title": g.title,
        "category": g.category,
        "description": g.description,
        "impact_level": g.impact_level,
        "date": g.date,
    }, person=i.person, source=i.source)


def decompose(i: Interaction) -> list[Event]:
    """将 Interaction 分解为多个 Event（static，无 IO）

    Pipeline 只调用此函数，不自己拆分。
    """
    events = [make_chat_event(i)]
    for f in i.facts:
        events.append(make_fact_event(i, f))
    if i.emotion:
        events.append(make_emotion_event(i))
    if i.relation_change and (i.relation_change.delta or i.relation_change.stage):
        events.append(make_relation_event(i))
    if i.milestone:
        events.append(make_milestone_event(i))
    if i.growth:
        events.append(make_growth_event(i))
    return events


# ============================================================
#  InteractionPipeline — 只做协调，不超过 150 行
# ============================================================

class InteractionPipeline:
    """统一事件总线 — 所有交互的唯一入口

    Pipeline 只做协调：
      publish()  — decompose → Storage.append() × N → Dispatcher.dispatch() × N
      recall()   — Storage.read_all() → Dispatcher.project_all() → ContextObject
      snapshot() — Dispatcher.snapshot_all()
      rebuild()  — Storage.read_all() → Dispatcher.project_all()

    Pipeline 不知道 Dispatcher 里有几个 Projection。
    Pipeline 不负责事件分解逻辑（decompose 是 static）。
    """

    def __init__(self, storage: Storage, dispatcher: ProjectionDispatcher,
                 enable_suggestions: bool = True,
                 enable_lifecycle: bool = True,
                 data_dir: str = "data"):
        self.storage = storage
        self.dispatcher = dispatcher
        self._composer = ContextComposer(
            enable_suggestions=enable_suggestions,
            enable_lifecycle=enable_lifecycle,
        )
        self._ranker = RetrievalRanker()
        self._snapshot_mgr = SnapshotManager(data_dir)

        # Capability token: 注入 Storage，保证只有 Pipeline 能写入
        self._cap_token = secrets.token_hex(16)
        self._storage_capability = StorageCapability(
            _token="pipeline:{}".format(self._cap_token)
        )
        # 如果 Storage 支持 capability 注入，注入之
        if hasattr(storage, '_capability_token'):
            storage._capability_token = self._storage_capability._token

    # ---- Capability Guard Helpers ----

    def _require_write_capability(self) -> StorageCapability:
        """验证 Pipeline 持有写 Capability（内部 sanity check）

        正常路径不走这里——这只是一个 Fail Fast gate，防止
        Pipeline 内部意外丢失 capability 后静默降级。
        """
        if not self._storage_capability:
            raise RuntimeError(
                "Pipeline capability 未初始化 — 可能是 __init__ 顺序错误"
            )
        return self._storage_capability

    def publish(self, interaction: Interaction) -> PublishResult:
        """唯一写入口：Interaction → Events → Storage → Dispatcher"""
        cap = self._require_write_capability()
        events = decompose(interaction)
        event_ids: list[str] = []
        for e in events:
            stored = self.storage.append(e, capability=cap)
            event_ids.append(stored.event_id)
            self.dispatcher.dispatch(stored)
        return PublishResult(event_id=event_ids[0], derived_event_ids=event_ids)

    def recall(self, person: str, query: str = "", max_tokens: int = 6000) -> PipelineResponse:
        """唯一读出口：Storage → Projection → Ranking → ContextObject

        每次 recall 填充完整的 metadata + diagnostics。
        调用方不需要学新接口——PipelineResponse 的形状从 Phase A 就锁定了。

        Args:
            person: 人物名称
            query: 查询文本（空字符串 = 无关键词 boost，靠重要性+新鲜度）
            max_tokens: token 预算上限（默认 6000）
        """
        started_at = time.perf_counter()
        request_id = str(uuid.uuid4())
        trace_id = str(uuid.uuid4())[:8]
        now_iso = datetime.now(timezone.utc).isoformat()
        warnings: list[str] = []

        # 1. 读取
        all_events = list(self.storage.read_all())
        person_events = [e for e in all_events if e.person == person]

        # 2. 投影（计时）
        proj_timing: dict[str, float] = {}
        t0 = time.perf_counter()
        profiles = self.dispatcher.project_all(all_events, person=person)
        proj_timing["project_all_total"] = (time.perf_counter() - t0) * 1000

        # 3. 排名（query-aware retrieval）
        t0 = time.perf_counter()
        pre_ranked = self._composer.extract_facts(profiles, person)
        ranked = self._ranker.rank(
            pre_ranked, query=query, max_tokens=max_tokens
        )
        ranker_stats = self._ranker.stats
        proj_timing["ranking"] = (time.perf_counter() - t0) * 1000

        # 4. 组装上下文（传入排名后的 facts）
        t0 = time.perf_counter()
        ctx = self._composer.compose(person, person_events, profiles,
                                     pre_ranked_facts=ranked)
        proj_timing["compose"] = (time.perf_counter() - t0) * 1000

        # 5. 构建 metadata
        persons_in_events = set(e.person for e in all_events if e.person)
        metadata = RecallMetadata(
            version=1,
            engine_version="v1.0",
            timing_ms=round((time.perf_counter() - started_at) * 1000, 2),
            started_at=now_iso,
            request_id=request_id,
            trace_id=trace_id,
            recall_strategy="ranked_query_aware",
            scoring_method="weighted_sum",
            cache_hit=False,
            snapshot_used=False,
            event_count=len(person_events),
            total_events=len(all_events),
            person_count=len(persons_in_events),
        )

        # 5. 构建 diagnostics
        # Health check
        storage_health = self.storage.health()
        storage_status = storage_health.get("status", "healthy")
        dispatcher_status = "healthy"
        dead_letters = self.dispatcher.dead_letters

        # Warnings
        if not person_events and person:
            warnings.append("no_events_for_person:{}".format(person))
        if len(all_events) == 0:
            warnings.append("empty_event_log")
        if dead_letters:
            warnings.append("dead_letters:{}".format(len(dead_letters)))
        # Storage health warnings
        if storage_health.get("wal_dirty"):
            warnings.append("wal_dirty")
        if storage_health.get("corrupted_records", 0) > 0:
            warnings.append("corrupted:{}".format(storage_health["corrupted_records"]))

        # Per-projection timing from project_all
        for name, stat in self.dispatcher.dispatch_stats.get("timing", {}).items():
            proj_timing["dispatch_{}".format(name)] = stat.get("avg_ms", 0)

        # Snapshot health
        snapshot_age = None
        snapshots = self._snapshot_mgr.list_snapshots() if self._snapshot_mgr else []
        if snapshots:
            # snapshot_age in seconds since last snapshot
            snapshot_age = "{}_projections".format(len(snapshots))

        diagnostics = Diagnostics(
            storage=storage_status,
            dispatcher=dispatcher_status,
            projection_count=self.dispatcher.count(),
            registered_event_types=len(self.dispatcher.registered_types()),
            storage_health=storage_health,
            projection_timing=dict(proj_timing),
            warnings=warnings,
            dead_letter_count=len(dead_letters),
            engine_version="v1.0",
            engine_time=now_iso,
            ranker_stats=ranker_stats,
        )

        return PipelineResponse(
            context=ctx,
            metadata=metadata,
            diagnostics=diagnostics,
        )

    def snapshot(self) -> dict[str, dict]:
        return self.dispatcher.snapshot_all()

    def rebuild(self) -> dict[str, dict]:
        return self.dispatcher.project_all(list(self.storage.read_all()))

    # ================================================================
    #  v0.7: Incremental Recall + Snapshot
    # ================================================================

    def recall_incremental(self, person: str, query: str = "",
                           max_tokens: int = 6000) -> PipelineResponse:
        """增量召回：当前数据量下等同于全量 recall"""
        return self.recall(person, query=query, max_tokens=max_tokens)

    def save_snapshots(self) -> str:
        """保存所有 Projection 快照"""
        all_events = list(self.storage.read_all())
        last_id = all_events[-1].event_id if all_events else ""
        snapshots = self.dispatcher.snapshot_all()
        if snapshots:
            self._snapshot_mgr.save_all(snapshots, last_id)
        return last_id

    def rebuild_from_scratch(self) -> dict[str, dict]:
        """从 Event Log 完全重建所有 Projection 和 Snapshot（停机恢复）"""
        all_events = list(self.storage.read_all())
        last_id = all_events[-1].event_id if all_events else ""
        profiles = self.dispatcher.project_all(all_events)
        for name, state in profiles.items():
            self._snapshot_mgr.save(name,
                state.to_dict() if hasattr(state, "to_dict") else state,
                last_id)
        return profiles


# ============================================================
#  create_pipeline() — 统一工厂，Web/MCP Server 共用
# ============================================================

def create_pipeline(
    data_dir: str = "data",
    user_id: str = "",
    enable_suggestions: bool = True,
    enable_lifecycle: bool = True,
) -> InteractionPipeline:
    """创建预配置的 Pipeline — 包含全部 8 个 Projection

    Web Server 和 MCP Server 通过这个工厂获得完全一致的初始化。
    所有 Projection 注册顺序由这个函数统一管理。

    Args:
        data_dir: 数据根目录
        user_id:  用户 ID（用于多用户隔离，为空则读 USER_ID 环境变量）
        enable_suggestions: 是否启用主动建议
        enable_lifecycle:   是否启用关系生命周期检测

    Returns:
        配置完全的 InteractionPipeline
    """
    import os
    uid = user_id or os.getenv("USER_ID", "local_default")
    base = os.path.join(data_dir, uid)

    # 唯一引用 JSONLStorage 的地方 — 换 adapter 只需改这一行
    from .storage import JSONLStorage as _StorageAdapter
    storage = _StorageAdapter(base)

    dispatcher = ProjectionDispatcher()

    # 导入所有 Projection
    from .projections.fact_state import FactProjection
    from .projections.person import PersonProjection
    from .projections.relationship import RelationshipProjection
    from .projections.time_context import TimeContextProjection
    from .projections.emotion import EmotionProjection
    from .projections.growth import GrowthProjection
    from .projections.conversation import ConversationProjection
    from .projections.reminder import ReminderProjection
    from .projections.profile import ProfileProjection

    # 注册全部 9 个 Projection — 顺序即意义（不影响功能，但决定了 info() 输出顺序）
    dispatcher.register(FactProjection(),          event_types=["fact"])
    dispatcher.register(PersonProjection(),        event_types=["person", "fact"])
    dispatcher.register(RelationshipProjection(),  event_types=["relation", "chat", "milestone", "person"])
    dispatcher.register(TimeContextProjection(),   event_types=["chat", "person", "milestone"])
    dispatcher.register(EmotionProjection(),       event_types=["emotion"])
    dispatcher.register(GrowthProjection(),        event_types=["growth"])
    dispatcher.register(ConversationProjection(),  event_types=["chat"])
    dispatcher.register(ReminderProjection(),      event_types=["person", "milestone", "emotion", "reminder"])
    dispatcher.register(ProfileProjection(),       event_types=["profile", "person"])

    return InteractionPipeline(
        storage=storage,
        dispatcher=dispatcher,
        enable_suggestions=enable_suggestions,
        enable_lifecycle=enable_lifecycle,
        data_dir=base,
    )
