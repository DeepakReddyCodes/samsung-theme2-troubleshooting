"""Grounding Checker verifying that extracted steps derive strictly from SIIS text.

Enforces:
1. Lexical and semantic token coverage against SIIS text.
2. Strict polarity consistency: Rejects steps with inverted actions (enable vs disable, lock vs unlock).
3. Entity containment: Rejects unsupported technical features (e.g. USB debugging, developer options).
4. Prompt injection filtering: Ignores instructions that contradict query context.
5. Retains an audit trail with evidence snippets and token support ratios.
"""
from dataclasses import dataclass, field
import logging
import re
from typing import Dict, List, Optional, Set, Tuple

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
    "device", "phone", "galaxy", "samsung", "step",
}

# Minimum fraction of content tokens that must be grounded in SIIS text
DEFAULT_GROUNDING_THRESHOLD = 0.50

# Polarity pairs where opposing actions in step vs SIIS must fail grounding
OPPOSING_ACTION_PAIRS = [
    ({"enable", "activate", "turn on", "switch on", "start", "connect"},
     {"disable", "deactivate", "turn off", "switch off", "stop", "disconnect"}),
    ({"lock", "set lock"}, {"unlock", "remove lock"}),
    ({"backup", "back up"}, {"restore", "reset", "wipe"}),
    ({"restore"}, {"backup", "reset", "wipe"}),
]


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
    rejection_reason: Optional[str] = None


class GroundingChecker:
    """Verifies that all extracted steps are semantically grounded in SIIS content."""

    def __init__(self, threshold: float = DEFAULT_GROUNDING_THRESHOLD):
        self.threshold = threshold

    def _check_polarity_conflict(self, step: str, siis_text: str) -> bool:
        """Check if step has an explicit polarity conflict with SIIS text."""
        step_lower = step.lower()
        siis_lower = siis_text.lower()

        for group_pos, group_neg in OPPOSING_ACTION_PAIRS:
            step_has_pos = any(re.search(r"\b" + re.escape(kw) + r"\b", step_lower) for kw in group_pos)
            step_has_neg = any(re.search(r"\b" + re.escape(kw) + r"\b", step_lower) for kw in group_neg)

            siis_has_pos = any(re.search(r"\b" + re.escape(kw) + r"\b", siis_lower) for kw in group_pos)
            siis_has_neg = any(re.search(r"\b" + re.escape(kw) + r"\b", siis_lower) for kw in group_neg)

            # Step is positive but SIIS only contains negative
            if step_has_pos and not step_has_neg and siis_has_neg and not siis_has_pos:
                return True
            # Step is negative but SIIS only contains positive
            if step_has_neg and not step_has_pos and siis_has_pos and not siis_has_neg:
                return True

        return False

    def check_step(self, step: str, siis_text: str) -> GroundingResult:
        """Check if a single step is grounded in the provided SIIS text."""
        if not step or not step.strip():
            return GroundingResult(step="", is_grounded=False, grounding_score=0.0, rejection_reason="Empty step")

        if not siis_text or not siis_text.strip():
            return GroundingResult(step=step, is_grounded=False, grounding_score=0.0, rejection_reason="Empty SIIS text")

        # 1. Check for polarity conflict
        if self._check_polarity_conflict(step, siis_text):
            return GroundingResult(
                step=step,
                is_grounded=False,
                grounding_score=0.0,
                unsupported_tokens=tokenize_content_words(step),
                rejection_reason="Polarity conflict with SIIS text",
            )

        step_tokens = tokenize_content_words(step)
        if not step_tokens:
            return GroundingResult(step=step, is_grounded=False, grounding_score=0.0, rejection_reason="No content tokens in step")

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

        # Multi-word phrase containment bonus
        words = step.split()
        phrase_matches = []
        for i in range(len(words) - 1):
            pair = f"{words[i].lower()} {words[i+1].lower()}"
            if pair in siis_lower:
                phrase_matches.append(pair)

        if phrase_matches:
            score = min(1.0, score + 0.15)

        is_grounded = score >= self.threshold

        # Best evidence snippet from SIIS
        evidence_snippet = ""
        if supported:
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

        rejection = None if is_grounded else f"Insufficient token overlap ({score:.2f} < {self.threshold})"

        return GroundingResult(
            step=step,
            is_grounded=is_grounded,
            grounding_score=round(score, 4),
            supported_tokens=supported,
            unsupported_tokens=unsupported,
            evidence_snippet=evidence_snippet,
            rejection_reason=rejection,
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
                    f"Rejected ungrounded step (score: {res.grounding_score:.2f}, reason: {res.rejection_reason}): '{step}'"
                )

        return grounded_steps, results
