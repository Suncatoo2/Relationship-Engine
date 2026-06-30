"""
Alice Demo — Relationship OS 端到端演示

运行: python examples/alice_demo.py

展示完整数据流:
  Interaction → Pipeline → Event → Dispatcher → Projection
  → Reasoner → Composer → ContextObject → JSON → LLM
"""

import sys
import os
import json
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.storage import JSONLStorage
from src.dispatcher import ProjectionDispatcher
from src.interaction_pipeline import (
    InteractionPipeline, Interaction,
    FactInput, EmotionInput, RelationInput,
)
from src.projections.fact_state import FactProjection
from src.projections.person import PersonProjection
from src.projections.relationship import RelationshipProjection
from src.projections.time_context import TimeContextProjection
from src.projections.emotion import EmotionProjection
from src.projections.growth import GrowthProjection
from src.memory_reasoner import MemoryReasoner
from src.prompt_adapter import get_adapter


def build_pipeline(data_dir: str) -> InteractionPipeline:
    """构建含所有 Projection 的 Pipeline"""
    store = JSONLStorage(data_dir)
    disp = ProjectionDispatcher()
    for proj, types in [
        (FactProjection(),          ["fact"]),
        (PersonProjection(),        ["person", "fact"]),
        (RelationshipProjection(),  ["relation", "chat", "milestone", "person"]),
        (TimeContextProjection(),   ["chat", "person", "milestone"]),
        (EmotionProjection(),       ["emotion"]),
        (GrowthProjection(),        ["growth"]),
    ]:
        disp.register(proj, event_types=types)
    return InteractionPipeline(storage=store, dispatcher=disp)


def seed_alice(pipeline: InteractionPipeline):
    """模拟与 Alice 的多轮交互"""
    interactions = [
        # 第一次见面
        Interaction(
            message="你好，我是 Alice",
            person="Alice",
            facts=[
                FactInput(content="Alice 是口腔专业学生", category="general", importance=7),
                FactInput(content="喜欢蓝色", category="preference", importance=6),
            ],
            emotion=EmotionInput(valence=0.6, label="平静"),
            relation_change=RelationInput(stage="认识", delta=10, event="初次见面"),
        ),
        # 聊了几天后
        Interaction(
            message="今天一起吃了火锅，聊得很开心",
            person="Alice",
            facts=[
                FactInput(content="喜欢吃火锅", category="preference", importance=5),
            ],
            emotion=EmotionInput(valence=0.9, label="开心", context="一起吃火锅"),
            relation_change=RelationInput(delta=15, event="一起吃火锅"),
        ),
        # Alice 说了梦想
        Interaction(
            message="我以后想开一家自己的牙科诊所",
            person="Alice",
            facts=[
                FactInput(content="想开牙科诊所", category="goal", importance=9),
            ],
            emotion=EmotionInput(valence=0.7, label="兴奋"),
        ),
        # 最近一次聊天
        Interaction(
            message="最近在准备考试，有点焦虑",
            person="Alice",
            emotion=EmotionInput(valence=-0.3, label="焦虑", context="准备考试"),
        ),
    ]

    print("=" * 60)
    print("  Step 1: 发布交互 (Interaction → Pipeline → Event)")
    print("=" * 60)

    for i, interaction in enumerate(interactions, 1):
        result = pipeline.publish(interaction)
        print(f"  [{i}] {interaction.message[:30]}...")
        print(f"      → event_id: {result.event_id[:12]}...")
        print(f"      → derived:  {len(result.derived_event_ids)} events")


def show_projection_state(pipeline: InteractionPipeline):
    """展示 Projection 状态"""
    print()
    print("=" * 60)
    print("  Step 2: Projection 状态 (Dispatcher → Projection)")
    print("=" * 60)

    all_events = list(pipeline.storage.read_all())
    print(f"  总事件数: {len(all_events)}")

    for info in pipeline.dispatcher.info():
        has_apply = "[apply]" if info["has_apply"] else "[      ]"
        has_snap = "[snapshot]" if info["has_snapshot"] else "[        ]"
        print(f"  {info['name']:30s} {has_apply} {has_snap}")


def show_context(pipeline: InteractionPipeline):
    """展示最终 ContextObject"""
    print()
    print("=" * 60)
    print("  Step 3: ContextObject (Reasoner → Composer → JSON)")
    print("=" * 60)

    response = pipeline.recall("Alice")
    ctx = response.context
    d = ctx.to_dict()

    # 分块打印
    print(f"\n  identity:  {d['identity']['name']}")
    print(f"  memory:    {d['memory']['fact_count']} facts, summary: {d['memory']['memory_summary'][:60]}...")
    print(f"  relationship: stage={d['relationship']['stage']}, chemistry={d['relationship']['chemistry']}")
    print(f"  emotion:   {d.get('emotion', {}).get('dominant_emotion', 'N/A')}")
    print(f"  goals:     {d.get('goals', {}).get('goal_count', 0)} active")
    print(f"  events:    {d['system']['event_count']}")
    print(f"  version:   {d['last_consumed_event_id'][:12]}...")

    # 完整 JSON
    print()
    print("  --- ContextObject JSON ---")
    print(json.dumps(d, ensure_ascii=False, indent=2))

    return ctx


def show_prompt(ctx):
    """展示生成的 Prompt（使用 PromptAdapter）"""
    print()
    print("=" * 60)
    print("  Step 4: PromptAdapter (ContextObject → Prompt)")
    print("=" * 60)

    # 展示 v0.6 新能力
    d = ctx.to_dict()

    # Relationship Lifecycle
    rel = d.get("relationship", {})
    if rel.get("lifecycle"):
        print(f"\n  Relationship Lifecycle: {rel['lifecycle']} ({rel.get('lifecycle_detail', '')})")

    # Emotion Momentum
    emotion = d.get("emotion", {})

    # Suggestions
    suggestions = d.get("suggestions", [])
    if suggestions:
        print(f"\n  Proactive Suggestions (Engine Detects):")
        for s in suggestions:
            print(f"    - {s}")

    # 用 3 个 Adapter 展示
    for name in ["claude", "gpt", "deepseek"]:
        adapter = get_adapter(name)
        prompt = adapter.build(ctx)
        print(f"\n  --- {name.upper()} Adapter ---")
        for line in prompt.split("\n")[:8]:
            print(f"    {line}")
        if prompt.count("\n") > 8:
            print(f"    ... ({prompt.count(chr(10)) + 1} lines total)")

    adapter = get_adapter("deepseek")
    return adapter.build(ctx)


def main():
    print()
    print("  Relationship OS — Alice Demo")
    print("  完整数据流: Interaction → Pipeline → Projection → Context → LLM")
    print()

    with tempfile.TemporaryDirectory() as data_dir:
        pipeline = build_pipeline(data_dir)
        seed_alice(pipeline)
        show_projection_state(pipeline)
        ctx = show_context(pipeline)
        prompt = show_prompt(ctx)

        # 验证
        d = ctx.to_dict()
        assert d['identity']['name'] == 'Alice'
        assert d['memory']['fact_count'] >= 3
        assert d['memory']['memory_summary']
        assert d['relationship']['stage'] != '陌生人'
        assert d['relationship']['chemistry'] > 0
        assert d.get('emotion') is not None
        assert d.get('goals') is not None
        assert d['system']['event_count'] >= 6

        print()
        print("=" * 60)
        print("  ALL CHECKS PASSED")
        print("=" * 60)
        print()


if __name__ == "__main__":
    main()
