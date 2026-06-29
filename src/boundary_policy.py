"""Boundary Policy — Knowledge Boundary 阈值管理

Business Policy 与 Business Mechanism 解耦。
31d / 61d 是产品策略，不是算法真理。
未来策略调整不修改 _compute_boundary()，只修改这里。
"""


class BoundaryPolicy:
    """知识边界注入策略"""

    # 时间阈值（天数）
    OUTDATED_THRESHOLD = 30         # 超过此天数 → outdated warning
    INSUFFICIENT_THRESHOLD = 60     # 超过此天数 → insufficient evidence

    # 置信度
    OUTDATED_CONFIDENCE = 0.25
    INSUFFICIENT_CONFIDENCE = 0.08

    # 重要性
    OUTDATED_IMPORTANCE = 7
    INSUFFICIENT_IMPORTANCE = 9

    @classmethod
    def outdated_message(cls, person: str, days: int) -> str:
        return (
            f"The engine's knowledge about {person} is becoming outdated. "
            f"Last interaction was {days} days ago."
        )

    @classmethod
    def insufficient_message(cls, person: str, days: int) -> str:
        return (
            f"The engine has insufficient evidence about {person}'s recent state. "
            f"No interaction in {days} days."
        )
