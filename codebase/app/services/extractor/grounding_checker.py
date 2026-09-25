"""Grounding Checker verifying that extracted steps derive strictly from SIIS text.

Enforces:
1. Compares every candidate step against the SIIS article.
2. Rejects unsupported or hallucinated steps.
3. Never silently invents replacement instructions.
4. Retains an audit trail with evidence snippets and token support ratios.
"""
from dataclasses import dataclass, field
import logging
import re
from typing import List, Set, Tuple

logger = logging.getLogger(__name__)

GROUNDING_STOPWORDS = {
    "a", "an", "the", "and", "or", "to", "in", "on", "at", "for", "with", "from",
    "by", "of", "it", "this", "that", "these", "those", "is", "are", "was", "were",
    "be", "been", "being", "have", "has", "had", "do", "does", "did", "can", "could",
    "will", "would", "should", "your", "my", "our", "their", "its", "into", "onto",
    "through", "over", "under", "again", "further", "then", "once", "here", "there",
    "when", "where", "why", "how", "all", "any", "both", "each", "few", "more", "most",
    "other", "some", "such", "no", "nor", "not", "only", "own", "same", "so", "than",
    "too", "very", "s", "t", "can", "will", "just", "don", "should", "now", "please",
}

# Minimum fraction of content tokens that must be grounded in SIIS text
DEFAULT_GROUNDING_THRESHOLD = 0.50


def tokenize_content_words(text: str) -> List[str]:
    """Extract lowercase alphanumeric tokens excluding generic stopwords."""
    if not text:
        return []
    words = re.findall(r"[a-z0-9]+", text.lower())
    return [w for w in words if w not in GROUNDING_STOPWORDS and len(w) > 1]


@dataclass
class GroundingResult:
    """Audit result for a single step grounding evaluation."""
    step: str
    is_grounded: bool
    grounding_score: float
    supported_tokens: List[str] = field(default_factory=list)
    unsupported_tokens: List[str] = field(default_factory=list)
    evidence_snippet: str = ""


class GroundingChecker:
    """Verifies that all extracted steps are semantically grounded in SIIS content."""

    def __init__(self, threshold: float = DEFAULT_GROUNDING_THRESHOLD):
        self.threshold = threshold

    def check_step(self, step: str, siis_text: str) -> GroundingResult:
        """Check if a single step is grounded in the provided SIIS text."""
        if not step or not step.strip():
            return GroundingResult(step="", is_grounded=False, grounding_score=0.0)

        step_tokens = tokenize_content_words(step)
        if not step_tokens:
            # Trivial or empty step
            return GroundingResult(step=step, is_grounded=False, grounding_score=0.0)

        siis_tokens = set(tokenize_content_words(siis_text))
        siis_lower = siis_text.lower()

        supported: List[str] = []
        unsupported: List[str] = []

        for token in step_tokens:
            if token in siis_tokens:
                supported.append(token)
            else:
                unsupported.append(token)

        score = len(supported) / len(step_tokens)

        # Also search for multi-word phrase containment
        phrase_matches = []
        words = step.split()
        for i in range(len(words) - 1):
            pair = f"{words[i].lower()} {words[i+1].lower()}"
            if pair in siis_lower:
                phrase_matches.append(pair)

        # Multi-word phrase matches provide extra grounding confidence
        if phrase_matches:
            score = min(1.0, score + 0.15)

        is_grounded = score >= self.threshold

        # Find best evidence snippet from SIIS text
        evidence_snippet = ""
        if supported:
            # Look for sentence containing the most supported tokens
            sentences = re.split(r"[.\n]+", siis_text)
            best_s = ""
            best_cnt = 0
            for s in sentences:
                s_tokens = set(tokenize_content_words(s))
                common = set(supported).intersection(s_tokens)
                if len(common) > best_cnt:
                    best_cnt = len(common)
                    best_s = s.strip()
            evidence_snippet = best_s[:200]

        return GroundingResult(
            step=step,
            is_grounded=is_grounded,
            grounding_score=round(score, 4),
            supported_tokens=supported,
            unsupported_tokens=unsupported,
            evidence_snippet=evidence_snippet,
        )

    def filter_grounded_steps(
        self,
        steps: List[str],
        siis_text: str,
    ) -> Tuple[List[str], List[GroundingResult]]:
        """Filter list of steps, keeping only those confirmed grounded in SIIS text."""
        grounded_steps: List[str] = []
        results: List[GroundingResult] = []

        for step in steps:
            res = self.check_step(step, siis_text)
            results.append(res)
            if res.is_grounded:
                grounded_steps.append(step)
            else:
                logger.warning(
                    f"Rejected ungrounded step (score: {res.grounding_score:.2f}): '{step}'"
                )

        return grounded_steps, results
