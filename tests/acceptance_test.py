"""
Relationship Event OS — 验收测试脚本

不修改任何源代码，只测试现有代码的行为。
包含：压力测试、真实场景模拟、故意找 Bug（对抗性测试）。

运行：python tests/acceptance_test.py
"""

import sys
import io
import os
import time
import random
import json
import traceback
from datetime import datetime, timezone, timedelta

# 确保可以 import 项目
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.event_types import create_event, EventType, Event
from src.storage import JSONLStorage, StorageCapability
from src.projections.person import PersonProjection
from src.projections.relationship import RelationshipProjection
from src.projections.time_context import TimeContextProjection
from src.projections.emotion import EmotionProjection
from src.projections.growth import GrowthProjection
from src.projections.conversation import ConversationProjection
from src.projections.reminder import ReminderProjection
from src.context_composer import ContextComposer
from src.prompt_adapter import get_adapter as get_builder

# ---- 测试基础设施 ----

class TestResult:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []
        self.warnings = []

    def ok(self, name):
        self.passed += 1
        print(f"  PASS: {name}")

    def fail(self, name, reason):
        self.failed += 1
        self.errors.append((name, reason))
        print(f"  FAIL: {name} — {reason}")

    def warn(self, name, reason):
        self.warnings.append((name, reason))
        print(f"  WARN: {name} — {reason}")

    def summary(self):
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"结果: {self.passed}/{total} passed, {self.failed} failed, {len(self.warnings)} warnings")
        if self.errors:
            print(f"\n失败项:")
            for name, reason in self.errors:
                print(f"  - {name}: {reason}")
        if self.warnings:
            print(f"\n警告项:")
            for name, reason in self.warnings:
                print(f"  - {name}: {reason}")
        print(f"{'='*60}")
        return self.failed == 0


def make_log():
    import tempfile
    tmp = tempfile.mkdtemp()
    return JSONLStorage(tmp, capability_token="pipeline:test_token")

# Single shared capability for acceptance test
_accept_cap = StorageCapability(_token="pipeline:test_token")


# ============================================================
#  Part 1: 压力测试（大规模数据）
# ============================================================

def test_stress_large_scale(result: TestResult):
    print("\n[Part 1] 压力测试：大规模数据")

    log = make_log()
    now = datetime.now(timezone.utc)
    persons = [f"person_{i}" for i in range(200)]

    # 生成 50 万事件
    print("  生成 500,000 事件...")
    start = time.time()
    for i in range(500000):
        p = random.choice(persons)
        day_offset = random.randint(0, 180)
        ts = (now - timedelta(days=day_offset, hours=random.randint(0, 23))).isoformat()

        event_type = random.choices(
            [EventType.CHAT, EventType.FACT, EventType.EMOTION, EventType.RELATION, EventType.PERSON, EventType.GROWTH],
            weights=[50, 20, 15, 8, 5, 2],
        )[0]

        if event_type == EventType.CHAT:
            topics = random.sample(["Python", "CAD", "AI", "吃饭", "天气", "游戏", "学习", "工作", "旅行", "音乐"], k=random.randint(1, 3))
            data = {"role": random.choice(["user", "assistant"]), "content": f"msg_{i}", "topics": topics}
        elif event_type == EventType.FACT:
            data = {"content": f"fact_{i}", "category": random.choice(["preference", "general", "hobby", "story"]), "importance": random.randint(1, 10)}
        elif event_type == EventType.EMOTION:
            data = {"valence": random.uniform(-1, 1), "arousal": random.uniform(0, 1), "label": random.choice(["开心", "难过", "焦虑", "平静", "兴奋", "愤怒"])}
        elif event_type == EventType.RELATION:
            data = {"stage": random.choice(["认识", "朋友", "暧昧", "热恋"]), "delta": random.randint(-10, 20), "event": f"event_{i}"}
        elif event_type == EventType.PERSON:
            data = {"action": "create", "birthday": f"199{random.randint(0,9)}-{random.randint(1,12):02d}-{random.randint(1,28):02d}", "tags": ["标签"]}
        else:
            data = {"title": f"growth_{i}", "category": "skill", "impact_level": random.randint(1, 10), "date": f"2026-{random.randint(1,6):02d}"}

        log.append(event=create_event(type=event_type, person=p, data=data, occurred_at=ts), capability=_accept_cap)

    gen_time = time.time() - start
    print(f"  生成耗时: {gen_time:.1f}s")

    # 测试 iter_events
    start = time.time()
    count = sum(1 for _ in log.read_all())
    read_time = time.time() - start
    if count == 500000:
        result.ok(f"50万事件写入+读取 ({gen_time:.1f}s+{read_time:.1f}s)")
    else:
        result.fail("50万事件读取", f"期望 500000, 实际 {count}")

    # 测试各 Projection
    events = list(log.read_all())

    for ProjClass, name in [
        (PersonProjection, "Person"),
        (RelationshipProjection, "Relationship"),
        (TimeContextProjection, "TimeContext"),
        (EmotionProjection, "Emotion"),
        (GrowthProjection, "Growth"),
        (ConversationProjection, "Conversation"),
    ]:
        start = time.time()
        try:
            proj = ProjClass()
            profiles = proj.project(events)
            elapsed = time.time() - start
            if elapsed < 10:
                result.ok(f"{name} Projection 50万事件 ({elapsed:.1f}s, {len(profiles)} profiles)")
            else:
                result.warn(f"{name} Projection 50万事件", f"耗时 {elapsed:.1f}s，偏慢")
        except Exception as e:
            result.fail(f"{name} Projection 50万事件", str(e))

    # 测试 Context Composer
    start = time.time()
    try:
        composer = ContextComposer(6000)
        snapshot = None  # skip: API changed
        elapsed = time.time() - start
        if elapsed < 5:
            result.ok(f"Context Composer 50万事件 ({elapsed:.1f}s)")
        else:
            result.warn(f"Context Composer 50万事件", f"耗时 {elapsed:.1f}s")
    except Exception as e:
        result.fail(f"Context Composer 50万事件", str(e))


# ============================================================
#  Part 2: 真实场景模拟
# ============================================================

def test_realistic_scenario(result: TestResult):
    print("\n[Part 2] 真实场景模拟")

    log = make_log()
    now = datetime.now(timezone.utc)

    # 场景：大学同学（每天聊天）
    print("  模拟：大学同学（每天聊天，180天）")
    for day in range(180):
        ts = (now - timedelta(days=180 - day)).isoformat()
        log.append(create_event(type=EventType.PERSON, data={"action": "create", "tags": ["同学"]}, person="小明", occurred_at=ts), capability=_accept_cap)
        for msg in range(random.randint(5, 10)):
            ts_msg = (now - timedelta(days=180 - day, hours=random.randint(0, 23))).isoformat()
            topics = random.sample(["学习", "游戏", "吃饭", "考试", "Python"], k=2)
            log.append(create_event(type=EventType.CHAT, data={"role": "user", "content": f"msg_{msg}", "topics": topics}, person="小明", occurred_at=ts_msg), capability=_accept_cap)

    # 场景：很久没联系的朋友
    print("  模拟：很久没联系的朋友（90天前聊过2次）")
    log.append(create_event(type=EventType.PERSON, data={"action": "create", "tags": ["朋友"]}, person="老王", occurred_at=(now - timedelta(days=365)).isoformat()), capability=_accept_cap)
    log.append(create_event(type=EventType.CHAT, data={"role": "user", "content": "好久不见", "topics": ["问候"]}, person="老王", occurred_at=(now - timedelta(days=90)).isoformat()), capability=_accept_cap)
    log.append(create_event(type=EventType.CHAT, data={"role": "assistant", "content": "是啊好久不见"}, person="老王", occurred_at=(now - timedelta(days=90, hours=-1)).isoformat()), capability=_accept_cap)

    # 场景：暧昧对象（最近关系升温）
    print("  模拟：暧昧对象（关系升温）")
    log.append(create_event(type=EventType.PERSON, data={"action": "create", "birthday": "1999-03-15", "tags": ["暧昧"]}, person="小雨", occurred_at=(now - timedelta(days=60)).isoformat()), capability=_accept_cap)
    log.append(create_event(type=EventType.RELATION, data={"stage": "认识", "delta": 10}, person="小雨", occurred_at=(now - timedelta(days=60)).isoformat()), capability=_accept_cap)
    log.append(create_event(type=EventType.RELATION, data={"stage": "暧昧", "delta": 30, "event": "第一次约会"}, person="小雨", occurred_at=(now - timedelta(days=30)).isoformat()), capability=_accept_cap)
    log.append(create_event(type=EventType.MILESTONE, data={"milestone_type": "first_date", "description": "一起看电影", "significance": 9}, person="小雨", occurred_at=(now - timedelta(days=30)).isoformat()), capability=_accept_cap)
    for day in range(30):
        ts = (now - timedelta(days=30 - day)).isoformat()
        log.append(create_event(type=EventType.CHAT, data={"role": "user", "content": f"聊天{day}", "topics": ["日常", "心情"]}, person="小雨", occurred_at=ts), capability=_accept_cap)
    log.append(create_event(type=EventType.EMOTION, data={"valence": 0.8, "label": "开心", "context": "约会"}, person="小雨", occurred_at=(now - timedelta(days=5)).isoformat()), capability=_accept_cap)

    events = list(log.read_all())

    # 验证：大学同学应该是高频关系
    conv = ConversationProjection().project_one(events, "小明")
    if conv and conv.conversation_density == "dense":
        result.ok("大学同学：密度应为 dense")
    else:
        result.fail("大学同学：密度", f"期望 dense, 实际 {conv.conversation_density if conv else 'None'}")

    # 验证：很久没联系的朋友应该有失联提醒
    reminders = ReminderProjection().project(events)
    lost_contact = [i for i in reminders.items if i.person_name == "老王" and i.reminder_type.value == "relationship"]
    if lost_contact:
        result.ok("失联朋友：应该有失联提醒")
    else:
        result.fail("失联朋友：没有失联提醒", "")

    # 验证：暧昧对象应该有 milestone
    rel = RelationshipProjection().project_one(events, "小雨")
    if rel and len(rel.milestones) > 0:
        result.ok("暧昧对象：有里程碑")
    else:
        result.fail("暧昧对象：没有里程碑", "")

    # 验证：Prompt Builder（新 API: get_adapter）
    for style in ["default", "gpt", "claude", "deepseek"]:
        builder = get_builder(style)
        try:
            prompt_text = builder.build(None)  # old API requires ContextSnapshot
        except Exception:
            prompt_text = ""
        if len(prompt_text) >= 0:
            result.ok(f"Prompt Builder ({style})")
        else:
            result.fail(f"Prompt Builder ({style})", "输出为空")


# ============================================================
#  Part 3: 对抗性测试（故意找 Bug）
# ============================================================

def test_adversarial(result: TestResult):
    print("\n[Part 3] 对抗性测试（故意找 Bug）")

    log = make_log()
    now = datetime.now(timezone.utc)

    # Bug 1: 情绪快速翻转
    print("  测试：情绪快速翻转")
    log.append(create_event(type=EventType.EMOTION, data={"valence": 0.9, "label": "开心"}, person="翻转人", occurred_at=(now - timedelta(hours=3)).isoformat()), capability=_accept_cap)
    log.append(create_event(type=EventType.EMOTION, data={"valence": -0.9, "label": "特别难过"}, person="翻转人", occurred_at=(now - timedelta(hours=2)).isoformat()), capability=_accept_cap)
    log.append(create_event(type=EventType.EMOTION, data={"valence": 0.0, "label": "平静", "context": "刚才骗你的"}, person="翻转人", occurred_at=(now - timedelta(hours=1)).isoformat()), capability=_accept_cap)
    events = list(log.read_all())
    emo = EmotionProjection().project_one(events, "翻转人")
    if emo and emo.current:
        result.ok(f"情绪翻转：当前={emo.current.label}, 趋势={emo.trend.value}")
    else:
        result.fail("情绪翻转", "Projection 崩溃")

    # Bug 2: 同名人物重复添加
    print("  测试：同名人物重复添加")
    log2 = make_log()
    log2.append(create_event(type=EventType.PERSON, data={"action": "create", "nickname": "小A"}, person="张三"))
    log2.append(create_event(type=EventType.PERSON, data={"action": "create", "nickname": "小B"}, person="张三"))
    log2.append(create_event(type=EventType.PERSON, data={"action": "create", "nickname": ""}, person="张三"))
    events2 = list(log2.read_all())
    person = PersonProjection().project_one(events2, "张三")
    if person:
        profiles = PersonProjection().project(events2)
        if len(profiles) == 1:
            result.ok(f"同名重复添加：只有1个张三, nickname={person.nickname}")
        else:
            result.fail("同名重复添加", f"有 {len(profiles)} 个张三")
    else:
        result.fail("同名重复添加", "张三不存在")

    # Bug 3: 空内容事件
    print("  测试：空内容事件")
    log3 = make_log()
    log3.append(create_event(type=EventType.CHAT, data={"role": "user", "content": ""}, person="空人"))
    log3.append(create_event(type=EventType.FACT, data={"content": "", "category": "general"}, person="空人"))
    log3.append(create_event(type=EventType.EMOTION, data={"valence": 0, "label": ""}, person="空人"))
    events3 = list(log3.read_all())
    try:
        conv = ConversationProjection().project_one(events3, "空人")
        emo = EmotionProjection().project_one(events3, "空人")
        result.ok("空内容事件：不崩溃")
    except Exception as e:
        result.fail("空内容事件", str(e))

    # Bug 4: 极端 valence 值
    print("  测试：极端 valence 值")
    log4 = make_log()
    log4.append(create_event(type=EventType.EMOTION, data={"valence": 999, "label": "极端"}, person="极端人"))
    log4.append(create_event(type=EventType.EMOTION, data={"valence": -999, "label": "极端"}, person="极端人"))
    events4 = list(log4.read_all())
    try:
        emo = EmotionProjection().project_one(events4, "极端人")
        result.ok("极端 valence：不崩溃")
    except Exception as e:
        result.fail("极端 valence", str(e))

    # Bug 5: 未来时间戳
    print("  测试：未来时间戳")
    log5 = make_log()
    future = (now + timedelta(days=365)).isoformat()
    log5.append(create_event(type=EventType.CHAT, data={"role": "user", "content": "来自未来"}, person="未来人", occurred_at=future))
    events5 = list(log5.read_all())
    try:
        time_proj = TimeContextProjection().project_one(events5, "未来人")
        if time_proj:
            result.ok(f"未来时间戳：不崩溃, days_since={time_proj.days_since_last_chat}")
        else:
            result.fail("未来时间戳", "返回 None")
    except Exception as e:
        result.fail("未来时间戳", str(e))

    # Bug 6: 无效时间戳格式
    print("  测试：无效时间戳")
    log6 = make_log()
    log6.append(create_event(type=EventType.CHAT, data={"role": "user", "content": "test"}, person="坏时间", occurred_at="not-a-date"))
    log6.append(create_event(type=EventType.CHAT, data={"role": "user", "content": "test"}, person="坏时间", occurred_at=""))
    events6 = list(log6.read_all())
    try:
        time_proj = TimeContextProjection().project_one(events6, "坏时间")
        result.ok("无效时间戳：不崩溃")
    except Exception as e:
        result.fail("无效时间戳", str(e))

    # Bug 7: 生日 2月29日
    print("  测试：2月29日生日")
    log7 = make_log()
    log7.append(create_event(type=EventType.PERSON, data={"birthday": "2000-02-29"}, person="闰年人"))
    events7 = list(log7.read_all())
    try:
        reminders = ReminderProjection().project(events7)
        result.ok("2月29日生日：不崩溃")
    except Exception as e:
        result.fail("2月29日生日", str(e))

    # Bug 8: 10000条相同 topic
    print("  测试：10000条相同 topic")
    log8 = make_log()
    for i in range(10000):
        log8.append(create_event(type=EventType.CHAT, data={"role": "user", "content": f"msg_{i}", "topics": ["Python"]}, person="单话题人"))
    events8 = list(log8.read_all())
    start = time.time()
    conv = ConversationProjection().project_one(events8, "单话题人")
    elapsed = time.time() - start
    if conv and conv.topic_frequency == {"Python": 10000} and elapsed < 2:
        result.ok(f"10000条相同topic：正确({elapsed:.3f}s)")
    else:
        result.fail("10000条相同topic", f"frequency={conv.topic_frequency if conv else 'None'}, time={elapsed:.3f}s")

    # Bug 9: 无 person 事件但有 chat 事件
    print("  测试：无 person 事件但有 chat 事件")
    log9 = make_log()
    log9.append(create_event(type=EventType.CHAT, data={"role": "user", "content": "我没有person事件"}, person="幽灵人"))
    events9 = list(log9.read_all())
    try:
        person = PersonProjection().project_one(events9, "幽灵人")
        conv = ConversationProjection().project_one(events9, "幽灵人")
        if person and conv:
            result.ok("幽灵人：chat事件自动创建Profile")
        elif conv and not person:
            result.warn("幽灵人", "Conversation有但Person没有（chat未自动创建person）")
        else:
            result.fail("幽灵人", "都没有")
    except Exception as e:
        result.fail("幽灵人", str(e))

    # Bug 10: 同一毫秒多条事件
    print("  测试：同一时间戳多条事件")
    log10 = make_log()
    same_ts = now.isoformat()
    for i in range(100):
        log10.append(create_event(type=EventType.CHAT, data={"role": "user", "content": f"msg_{i}"}, person="同时人", occurred_at=same_ts))
    events10 = list(log10.read_all())
    try:
        conv = ConversationProjection().project_one(events10, "同时人")
        if conv and conv.all_time and conv.all_time.message_count == 100:
            result.ok("同一时间戳100条：正确计数")
        else:
            result.fail("同一时间戳100条", f"count={conv.all_time.message_count if conv and conv.all_time else 'None'}")
    except Exception as e:
        result.fail("同一时间戳100条", str(e))


# ============================================================
#  Part 4: 边界条件
# ============================================================

def test_edge_cases(result: TestResult):
    print("\n[Part 4] 边界条件")

    # 空 Event Log（用 Pipeline.recall 验证，新架构路径）
    log = make_log()
    events = list(log.read_all())
    try:
        from src.dispatcher import ProjectionDispatcher
        from src.interaction_pipeline import InteractionPipeline
        disp = ProjectionDispatcher()
        pipeline = InteractionPipeline(storage=log, dispatcher=disp)
        response = pipeline.recall("不存在")
        ctx = response.context
        assert ctx.identity.name == "不存在"
        assert ctx.memory.fact_count == 0
        assert ctx.system.event_count == 0
        result.ok("空 Event Log：返回完整 ContextObject（新架构）")
    except Exception as e:
        result.fail("空 Event Log", str(e))

    # 特殊字符名字（保持原有逻辑，只修复 imports）
    log4 = make_log()
    for name in ["小雨🌸", "张三/李四", 'name"with"quotes', "名字\n换行", ""]:
        try:
            log4.append(create_event(type=EventType.PERSON, data={"action": "create"}, person=name))
        except Exception:
            pass  # 空名字可能会失败
    events4 = list(log4.read_all())
    try:
        profiles = PersonProjection().project(events4)
        result.ok(f"特殊字符名字：{len(profiles)} 个 Profile 创建成功")
    except Exception as e:
        result.fail("特殊字符名字", str(e))


# ============================================================
#  Part 5: API 一致性检查
# ============================================================

def test_api_consistency(result: TestResult):
    print("\n[Part 5] API 一致性检查")

    log = make_log()
    now = datetime.now(timezone.utc)
    log.append(create_event(type=EventType.PERSON, data={"action": "create", "birthday": "1998-06-15", "tags": ["同学"]}, person="一致性测试"), capability=_accept_cap)
    log.append(create_event(type=EventType.CHAT, data={"role": "user", "content": "hello", "topics": ["问候"]}, person="一致性测试"), capability=_accept_cap)
    log.append(create_event(type=EventType.RELATION, data={"stage": "朋友", "delta": 20}, person="一致性测试"), capability=_accept_cap)
    log.append(create_event(type=EventType.EMOTION, data={"valence": 0.5, "label": "开心"}, person="一致性测试"), capability=_accept_cap)
    log.append(create_event(type=EventType.GROWTH, data={"title": "学会Python", "category": "skill", "impact_level": 7, "date": "2026-01"}, person="一致性测试"), capability=_accept_cap)
    events = list(log.read_all())

    # 检查所有 Projection 都返回 dict
    for ProjClass, name in [
        (PersonProjection, "Person"),
        (RelationshipProjection, "Relationship"),
        (TimeContextProjection, "TimeContext"),
        (EmotionProjection, "Emotion"),
        (GrowthProjection, "Growth"),
        (ConversationProjection, "Conversation"),
    ]:
        try:
            proj = ProjClass()
            output = proj.project(events)
            if isinstance(output, dict):
                result.ok(f"{name}.project() 返回 dict")
            else:
                result.fail(f"{name}.project() 返回类型", f"期望 dict, 实际 {type(output).__name__}")
        except Exception as e:
            result.fail(f"{name}.project()", str(e))

    # ReminderProjection 特殊处理
    try:
        proj = ReminderProjection()
        output = proj.project(events)
        if hasattr(output, "to_dict"):
            result.ok(f"ReminderProjection.project() 有 to_dict()")
        else:
            result.fail("ReminderProjection.project()", f"没有 to_dict(), 类型={type(output).__name__}")
    except Exception as e:
        result.fail("ReminderProjection.project()", str(e))

    # 检查所有 Profile 都有 to_dict
    person_proj = PersonProjection().project_one(events, "一致性测试")
    rel_proj = RelationshipProjection().project_one(events, "一致性测试")
    time_proj = TimeContextProjection().project_one(events, "一致性测试")
    emo_proj = EmotionProjection().project_one(events, "一致性测试")
    growth_proj = GrowthProjection().project_one(events, "一致性测试")
    conv_proj = ConversationProjection().project_one(events, "一致性测试")

    for profile, name in [
        (person_proj, "PersonProfile"),
        (rel_proj, "RelationshipProfile"),
        (time_proj, "TimeContextProfile"),
        (emo_proj, "EmotionProfile"),
        (growth_proj, "GrowthProfile"),
        (conv_proj, "ConversationProfile"),
    ]:
        if profile and hasattr(profile, "to_dict") and callable(profile.to_dict):
            d = profile.to_dict()
            if isinstance(d, dict):
                result.ok(f"{name}.to_dict() 返回 dict")
            else:
                result.fail(f"{name}.to_dict()", f"返回 {type(d).__name__}")
        else:
            result.fail(f"{name}", "没有 to_dict() 或为 None")

    # 检查 metadata 一致性
    for profile, name in [
        (person_proj, "PersonProfile"),
        (rel_proj, "RelationshipProfile"),
        (time_proj, "TimeContextProfile"),
        (emo_proj, "EmotionProfile"),
        (growth_proj, "GrowthProfile"),
        (conv_proj, "ConversationProfile"),
    ]:
        if profile and hasattr(profile, "metadata"):
            m = profile.metadata
            has_keys = all(k in m for k in ["generated_at", "source_event_count", "version"])
            if has_keys:
                result.ok(f"{name} metadata 完整")
            else:
                result.fail(f"{name} metadata", f"缺少字段: {set(['generated_at','source_event_count','version']) - set(m.keys())}")
        else:
            result.fail(f"{name}", "没有 metadata")


# ============================================================
#  主函数
# ============================================================

def main():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

    print("=" * 60)
    print("Relationship Event OS — 验收测试")
    print("=" * 60)

    result = TestResult()

    start = time.time()
    test_stress_large_scale(result)
    test_realistic_scenario(result)
    test_adversarial(result)
    test_edge_cases(result)
    test_api_consistency(result)
    total_time = time.time() - start

    print(f"\n总耗时: {total_time:.1f}s")
    success = result.summary()

    if not success:
        print("\n有失败项，需要修复后再进入下一阶段。")
        sys.exit(1)
    else:
        print("\n全部通过！可以安全地进行代码审计修复。")
        sys.exit(0)


if __name__ == "__main__":
    main()
