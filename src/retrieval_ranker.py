"""Retrieval Ranker — query-aware memory selection with pluggable strategies

ADR-008: Retrieval Ranking. Engine selects, LLM interprets.

The RetrievalRanker sits between projection and composition:
  9 Projections → Fact extraction → RetrievalRanker.rank() → ContextComposer → ContextObject

Strategies:
  - KeywordMatch:   TF-like keyword relevance to query
  - Recency:        exponential decay scoring (newer facts score higher)
  - Importance:     normalize importance (1-10) to (0-1)
  - WeightedSum:    combine strategies with configurable weights

Token Budgeting:
  - char / 2.5 ≈ token estimation (handles mixed Chinese/English)
  - Select top-N facts that fit within max_tokens budget
  - SYSTEM-category facts (boundary, health) are always preserved

Design:
  - Pure functions where possible — all scoring is deterministic
  - Ranker is independent of Pipeline, Storage, and Dispatcher
  - Pluggable strategies via ABC — add new strategies without touching ranker
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
import math
import re

from .protocol import FactItem


# ============================================================
#  Strategy Interface
# ============================================================

class RetrievalStrategy(ABC):
    """Pluggable scoring strategy.

    Each strategy scores a single fact against a query.
    Score range: [0.0, 1.0].
    Higher = more relevant.
    """

    @abstractmethod
    def score(self, fact: FactItem, query: str = "") -> float:
        ...


# ============================================================
#  Built-in Strategies
# ============================================================

class KeywordStrategy(RetrievalStrategy):
    """Keyword matching — query terms vs fact content + category.

    Uses Jaccard-like token overlap with substring bonuses.
    Handles Chinese text via character-level matching.
    """

    def __init__(self, substring_bonus: float = 0.15, category_bonus: float = 0.10):
        self._substring_bonus = substring_bonus
        self._category_bonus = category_bonus

    def score(self, fact: FactItem, query: str = "") -> float:
        if not query or not query.strip():
            return 0.0

        query_lower = query.lower().strip()
        content_lower = fact.content.lower()
        cat_lower = fact.category.lower()

        # Tokenize — handles both English words and Chinese characters
        query_tokens = self._tokenize(query_lower)
        if not query_tokens:
            return 0.0

        content_tokens = self._tokenize(content_lower)
        cat_tokens = self._tokenize(cat_lower)

        # Jaccard-like: intersection / union across content + category
        all_target_tokens = content_tokens | cat_tokens
        intersection = query_tokens & all_target_tokens
        union = query_tokens | all_target_tokens

        jaccard = len(intersection) / max(len(union), 1)

        # Substring bonus: each query token found inside content/category
        substring_score = 0.0
        for token in query_tokens:
            if len(token) >= 2 and token in content_lower:
                substring_score += self._substring_bonus
            if len(token) >= 2 and token in cat_lower:
                substring_score += self._category_bonus

        # Exact match bonus for multi-word queries
        exact_bonus = 0.0
        if len(query_lower) >= 3 and query_lower in content_lower:
            exact_bonus = 0.30

        return min(1.0, jaccard + substring_score + exact_bonus)

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        """Tokenize text into a set of meaningful tokens.

        English: split on word boundaries.
        Chinese: character-level bigrams.
        Mixed: both approaches combined.
        """
        tokens: set[str] = set()

        # English/alphabetic words (length >= 2)
        words = re.findall(r'[a-zA-Z]{2,}', text)
        tokens.update(w.lower() for w in words)

        # Chinese/Unicode characters (individual chars)
        chinese = re.findall(r'[一-鿿㐀-䶿]', text)
        tokens.update(chinese)

        # Bigrams for longer Chinese sequences
        for i in range(len(chinese) - 1):
            tokens.add(chinese[i] + chinese[i + 1])

        # Numeric tokens
        numbers = re.findall(r'\d+', text)
        tokens.update(numbers)

        return tokens


class RecencyStrategy(RetrievalStrategy):
    """Recency scoring — newer facts score higher.

    Uses exponential decay: score = e^(-λ * days_old)
    Default λ = 0.01 → half-life ≈ 69 days.

    Facts without created_at get neutral score (0.5).
    """

    def __init__(self, decay_lambda: float = 0.01):
        self._lambda = decay_lambda

    def score(self, fact: FactItem, query: str = "") -> float:
        if not fact.created_at:
            return 0.5

        try:
            ts = datetime.fromisoformat(fact.created_at)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            days_old = (datetime.now(timezone.utc) - ts).days
            if days_old < 0:
                days_old = 0
        except (ValueError, TypeError):
            return 0.5

        return math.exp(-self._lambda * days_old)


class ImportanceStrategy(RetrievalStrategy):
    """Importance-based scoring — normalize importance (1–10) to (0–1).

    Uses sqrt normalization so mid-range scores don't collapse to 0.5.
    score = sqrt(importance / 10)
    """

    def score(self, fact: FactItem, query: str = "") -> float:
        imp = max(1, min(10, fact.importance))
        return math.sqrt(imp / 10.0)


class WeightedSumRanker(RetrievalStrategy):
    """Combine multiple strategies with configurable weights.

    score = Σ (strategy.score(fact, query) × weight)

    Weights do NOT need to sum to 1.0 (they are normalized internally).
    """

    def __init__(self, strategies: list[tuple[RetrievalStrategy, float]]):
        total_weight = sum(w for _, w in strategies)
        if total_weight <= 0:
            raise ValueError("Total strategy weight must be > 0")
        self._strategies = [(s, w / total_weight) for s, w in strategies]
        self._names = [s.__class__.__name__ for s, _ in self._strategies]

    @property
    def strategy_names(self) -> list[str]:
        return self._names

    @property
    def weights(self) -> list[float]:
        return [round(w, 3) for _, w in self._strategies]

    def score(self, fact: FactItem, query: str = "") -> float:
        total = 0.0
        for strategy, weight in self._strategies:
            total += strategy.score(fact, query) * weight
        return min(1.0, max(0.0, total))


# ============================================================
#  Scored Fact
# ============================================================

@dataclass
class ScoredFact:
    """A fact with its retrieval score and metadata."""
    fact: FactItem
    score: float = 0.0

    @property
    def content(self) -> str:
        return self.fact.content

    @property
    def category(self) -> str:
        return self.fact.category


# ============================================================
#  Token Estimation
# ============================================================

# Conservative estimate: average char-per-token ratio
# English: ~4 chars/token, Chinese: ~1.5 chars/token
# Mixed content defaults to ~2.5 as a safe midpoint
CHARS_PER_TOKEN = 2.5
SYSTEM_FACT_TOKEN_RESERVE = 200  # Reserve tokens for boundary/system facts


def estimate_tokens(text: str) -> int:
    """Estimate token count from text length.

    Conservative: chars / 2.5 rounds up slightly.
    Handles empty string → 0.
    """
    if not text:
        return 0
    return max(1, int(math.ceil(len(text) / CHARS_PER_TOKEN)))


def estimate_fact_tokens(fact: FactItem) -> int:
    """Estimate tokens for a single fact (content + metadata overhead).

    Includes ~6 token overhead for JSON structure.
    """
    text = fact.content
    if fact.category and fact.category != "general":
        text += f" [{fact.category}]"
    if fact.source and fact.source != "user_direct":
        text += f" (source: {fact.source})"
    return estimate_tokens(text) + 6


# ============================================================
#  RetrievalRanker
# ============================================================

class RetrievalRanker:
    """Query-aware fact ranking with token budgeting.

    Usage:
        ranker = RetrievalRanker()
        ranked = ranker.rank(facts, query="考试", max_tokens=2000)
        # Returns ScoredFact list, sorted by score, within token budget

        # Custom strategy:
        ranker = RetrievalRanker(strategy=KeywordStrategy())

        # With custom weights:
        ranker = RetrievalRanker(strategy=WeightedSumRanker([
            (KeywordStrategy(), 0.5),
            (ImportanceStrategy(), 0.3),
            (RecencyStrategy(), 0.2),
        ]))
    """

    def __init__(self, strategy: RetrievalStrategy | None = None):
        if strategy is None:
            # Default: balanced retrieval
            strategy = WeightedSumRanker([
                (KeywordStrategy(), 0.40),
                (ImportanceStrategy(), 0.35),
                (RecencyStrategy(), 0.25),
            ])
        self._strategy = strategy
        self._total_scored: int = 0
        self._total_selected: int = 0
        self._tokens_used: int = 0

    @property
    def strategy(self) -> RetrievalStrategy:
        return self._strategy

    @property
    def stats(self) -> dict:
        """Last ranking statistics."""
        return {
            "total_scored": self._total_scored,
            "total_selected": self._total_selected,
            "tokens_used": self._tokens_used,
        }

    def score_all(self, facts: list[FactItem], query: str = "") -> list[ScoredFact]:
        """Score all facts without token limit.

        Returns sorted list (highest score first).
        """
        if not facts:
            return []

        scored = []
        for f in facts:
            s = self._strategy.score(f, query)
            scored.append(ScoredFact(fact=f, score=round(s, 4)))

        scored.sort(key=lambda sf: sf.score, reverse=True)
        return scored

    def rank(
        self,
        facts: list[FactItem],
        query: str = "",
        max_tokens: int = 4000,
    ) -> list[ScoredFact]:
        """Rank facts by relevance to query, respecting token budget.

        Algorithm:
          1. Score all facts against query
          2. Sort by score descending
          3. Greedy select top-N that fit within max_tokens
          4. SYSTEM facts are preserved regardless of score

        Args:
            facts: all available facts (from FactProjection + boundary)
            query: search query (empty string = ranking only, no keyword boost)
            max_tokens: token budget ceiling

        Returns:
            Ranked list of ScoredFact, ordered by score (highest first),
            truncated to fit within max_tokens.
        """
        if not facts:
            self._total_scored = 0
            self._total_selected = 0
            self._tokens_used = 0
            return []

        # Separate SYSTEM facts (always preserved)
        system_facts = [f for f in facts if f.category == "SYSTEM"]
        regular_facts = [f for f in facts if f.category != "SYSTEM"]

        # Score regular facts
        scored = self.score_all(regular_facts, query)

        # Token budgeting: greedy top-N selection
        available_budget = max_tokens - SYSTEM_FACT_TOKEN_RESERVE
        selected: list[ScoredFact] = []
        tokens_used = 0

        for sf in scored:
            fact_tokens = estimate_fact_tokens(sf.fact)
            if tokens_used + fact_tokens <= available_budget:
                selected.append(sf)
                tokens_used += fact_tokens
            # Don't break — we might still fit smaller facts
            # But if we exceed budget, stop trying to add more
            elif tokens_used >= available_budget:
                break

        # Prepend SYSTEM facts (they go first, before regular facts)
        for sys_fact in system_facts:
            selected.insert(0, ScoredFact(fact=sys_fact, score=1.0))

        self._total_scored = len(facts)
        self._total_selected = len(selected)
        self._tokens_used = tokens_used

        return selected

    def select_top_k(self, facts: list[FactItem], k: int = 10,
                     query: str = "") -> list[ScoredFact]:
        """Select top-k facts by score, no token budgeting."""
        if not facts:
            return []
        return self.score_all(facts, query)[:k]
