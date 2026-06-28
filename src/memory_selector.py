"""Memory Selector — 从记忆中选择当前最相关的信息

为什么需要？
  一个人可能有几百条事实（生日、专业、偏好、习惯...）
  LLM 的 Context Window 有限，不能全塞进去
  必须根据用户的问题选择最相关的记忆

策略：
  v0.35: 关键词匹配（简单高效）
  v0.5:  语义匹配（embedding）

输入：用户消息 + 所有事实列表
输出：筛选后的相关事实（按 relevance_score 排序）
"""

import re
from dataclasses import dataclass


@dataclass
class FactItem:
    """一条结构化事实"""
    content: str
    category: str
    importance: int
    importance_reason: str
    source: str
    confidence: float
    created_at: str
    times_confirmed: int
    status: str = "active"

    def to_dict(self) -> dict:
        return {
            "content": self.content,
            "category": self.category,
            "importance": self.importance,
            "importance_reason": self.importance_reason,
            "source": self.source,
            "confidence": self.confidence,
            "created_at": self.created_at[:10],
            "times_confirmed": self.times_confirmed,
            "status": self.status,
        }


def extract_facts(events) -> list[FactItem]:
    """从 Event Log 事件列表中提取所有事实"""
    facts = []
    for e in events:
        if e.type == "fact":
            facts.append(FactItem(
                content=e.data.get("content", ""),
                category=e.data.get("category", "general"),
                importance=e.data.get("importance", 5),
                importance_reason=e.data.get("importance_reason", ""),
                source=e.data.get("source", "user_direct"),
                confidence=e.data.get("confidence", 0.9),
                created_at=e.occurred_at,
                times_confirmed=e.data.get("times_confirmed", 1),
            ))
    return facts


class MemorySelector:
    """记忆选择器

    根据用户消息，从所有事实中选择最相关的。
    """

    def select(self, query: str, facts: list[FactItem], max_facts: int = 10) -> list[FactItem]:
        """选择与当前问题最相关的记忆

        Args:
            query: 用户当前消息
            facts: 所有事实列表
            max_facts: 最多返回几条

        Returns:
            按相关性排序的 FactItem 列表
        """
        if not query or not facts:
            return facts[:max_facts]

        # Step 1: 提取查询关键词
        query_keywords = self._tokenize(query)

        # Step 2: 计算每条事实的相关性得分
        scored = []
        for f in facts:
            score = self._compute_score(query_keywords, f)
            if score > 0:
                scored.append((score, f))

        # Step 3: 按得分排序
        scored.sort(key=lambda x: x[0], reverse=True)

        # Step 4: 返回 top N
        return [f for _, f in scored[:max_facts]]

    def _tokenize(self, text: str) -> list[str]:
        """简单中文分词 + 提取关键词"""
        cleaned = re.sub(r'[？？！！，。、]+', ' ', text)
        tokens = cleaned.strip().split()
        # 提取双字词和三字词（中文常用）
        for i in range(len(text) - 1):
            if text[i] not in '？？！！，。、 ' and text[i + 1] not in '？？！！，。、 ':
                tokens.append(text[i:i + 2])
        for i in range(len(text) - 2):
            if text[i] not in '？？！！，。、 ' and text[i + 1] not in '？？！！，。、 ' and text[i + 2] not in '？？！！，。、 ':
                tokens.append(text[i:i + 3])
        return list(set(tokens))

    def _compute_score(self, query_keywords: list[str], fact: FactItem) -> float:
        """计算事实与查询的相关性得分

        score = 关键词命中 + importance 加权 + 活跃状态加权
        """
        content_lower = fact.content.lower()
        score = 0.0

        # 关键词命中
        for kw in query_keywords:
            if kw.lower() in content_lower:
                score += 10  # 直接匹配
            # 部分匹配（如"颜色"匹配"蓝色"）
            elif len(kw) >= 2:
                for i in range(len(kw) - 1):
                    if kw[i:i + 2].lower() in content_lower:
                        score += 3
                        break

        # 类别加分（问"什么颜色"→ preference 类加分）
        category_hints = {
            "颜色": "preference",
            "喜欢": "preference",
            "生日": "birthday",
            "爱好": "hobby",
            "怕": "secret",
            "电话": "general",
            "名字": "general",
            "岁": "birthday",
            "多大": "birthday",
        }
        for kw in query_keywords:
            if kw in category_hints and fact.category == category_hints[kw]:
                score += 5

        # importance 加权
        score *= (0.5 + fact.importance / 20)

        # 活跃状态加权
        if fact.status == "active":
            score *= 1.0
        elif fact.status == "deprecated":
            score *= 0.3

        return score
