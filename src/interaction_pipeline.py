"""Interaction Pipeline — 唯一事件入口

ADR-005: 高层只有一个入口 — publish_interaction()
ADR-006: 只有 Pipeline 可以访问 Event Store
ADR-006-SLIM: Pipeline 自身不超过 150 行。只做协调，不负责实现。

Pipeline 不直接操作文件或数据库——所有 IO 必须经过 Storage 接口。
Pipeline 不知道 Dispatcher 里有几个 Projection。
Pipeline 不负责事件分解——分解逻辑在 static factory 方法中。
"""

from dataclasses import dataclass, field

from .event_types import Event, create_event
from .storage import Storage
from .dispatcher import ProjectionDispatcher
from .projections.base import Projection
from .protocol import ContextObject
from .context_composer import ContextComposer
from .snapshot_manager import SnapshotManager
from .pipeline_response import PipelineResponse, RecallMetadata


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
class Interaction:
    """LLM 结构化后的交互数据"""
    message: str
    person: str = ""
    type: str = "chat"
    facts: list[FactInput] = field(default_factory=list)
    emotion: EmotionInput | None = None
    relation_change: RelationInput | None = None
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


def decompose(i: Interaction) -> list[Event]:
    """将 Interaction 分解为多个 Event（static，无 IO）

    Pipeline 只调用此函数，不自己拆分。
    """
    events = [make_chat_event(i)]
    for f in i.facts:
        events.append(make_fact_event(i, f))
    if i.emotion:
        events.append(make_emotion_event(i))
    if i.relation_change and i.relation_change.delta:
        events.append(make_relation_event(i))
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
        self._snapshot_mgr = SnapshotManager(data_dir)

    def publish(self, interaction: Interaction) -> PublishResult:
        """唯一写入口：Interaction → Events → Storage → Dispatcher"""
        events = decompose(interaction)
        event_ids: list[str] = []
        for e in events:
            stored = self.storage.append(e)
            event_ids.append(stored.event_id)
            self.dispatcher.dispatch(stored)
        return PublishResult(event_id=event_ids[0], derived_event_ids=event_ids)

    def recall(self, person: str) -> PipelineResponse:
        """唯一读出口：Storage → Projection → ContextObject"""
        all_events = list(self.storage.read_all())
        person_events = [e for e in all_events if e.person == person]
        profiles = self.dispatcher.project_all(all_events, person=person)
        ctx = self._composer.compose(person, person_events, profiles)
        return PipelineResponse(
            context=ctx,
            metadata=RecallMetadata(
                event_count=len(person_events),
            ),
            diagnostics=None,
        )

    def snapshot(self) -> dict[str, dict]:
        return self.dispatcher.snapshot_all()

    def rebuild(self) -> dict[str, dict]:
        return self.dispatcher.project_all(list(self.storage.read_all()))

    # ================================================================
    #  v0.7: Incremental Recall + Snapshot
    # ================================================================

    def recall_incremental(self, person: str) -> PipelineResponse:
        """增量召回：当前数据量下等同于全量 recall"""
        return self.recall(person)

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
