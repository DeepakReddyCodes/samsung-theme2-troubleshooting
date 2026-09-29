"""Query enrichment module for normalising and extracting intent/entities."""
import re
from dataclasses import dataclass, field
from typing import List

COMPOUND_MAP = {
    r"\bbackup\b": "back up",
    r"\bwi-fi\b": "wifi",
    r"\bwi fi\b": "wifi",
    r"\btouchscreen\b": "touch screen",
    r"\blockscreen\b": "lock screen",
    r"\bautosync\b": "auto sync",
    r"\bquickshare\b": "quick share",
    r"\bsmartswitch\b": "smart switch",
}


@dataclass
class EnrichedQuery:
    """Structured representation of an enriched user query."""
    normalized_query: str
    polarity: str
    entities: List[str] = field(default_factory=list)


class QueryEnricher:
    """Deterministic enrichment of user queries."""

    def __init__(self):
        # Conversational noise to strip
        self.noise_regex = re.compile(
            r"(?i)\b(please|tell me|how do i|how to|i want to|can you|help me|hi|hello|hey|thanks)\b"
        )

        # Exact explicit operations for polarity
        self.enable_keywords = {"enable", "turn on", "activate"}
        self.disable_keywords = {"disable", "turn off", "deactivate"}

        # Explicit negation phrases
        self.negation_phrases = {"do not", "don t", "dont", "do nt"}

        # Entities
        self.entity_keywords = {"backup", "restore", "reset", "lock", "unlock"}

    def _determine_polarity(self, text: str) -> str:
        """Deterministically determine polarity, handling negations correctly."""
        has_enable = any(kw in text for kw in self.enable_keywords)
        has_disable = any(kw in text for kw in self.disable_keywords)
        has_negation = any(phrase in text for phrase in self.negation_phrases)

        # Do not confidently guess if both are somehow present
        if has_enable and has_disable:
            return "neutral"

        if has_enable:
            return "negated_enable" if has_negation else "enable"
        if has_disable:
            return "negated_disable" if has_negation else "disable"

        return "neutral"

    def enrich(self, query: str) -> EnrichedQuery:
        """Enrich a raw query into an EnrichedQuery object."""
        if not query or not query.strip():
            return EnrichedQuery(normalized_query="", polarity="neutral", entities=[])

        # Truncate at 1024 chars for safety against pathological inputs
        query = query[:1024]

        # Strip conversational noise
        cleaned = self.noise_regex.sub("", query).strip()

        # Remove leading numbering like '1. ', '1. "', '2. '
        cleaned = re.sub(r"^\d+[\.\)]\s*[\"']?", "", cleaned)
        # Remove trailing quotes
        cleaned = re.sub(r"[\"']\s*$", "", cleaned)
        cleaned = cleaned.lower()

        # Normalize domain compounds
        for pat, rep in COMPOUND_MAP.items():
            cleaned = re.sub(pat, rep, cleaned)

        # Replace punctuation with spaces to safely check for negations without apostrophes (don't -> don t)
        cleaned = re.sub(r"[^\w\s]", " ", cleaned)
        # Collapse multiple whitespaces
        cleaned = re.sub(r"\s+", " ", cleaned).strip()

        polarity = self._determine_polarity(cleaned)

        # Determine entities
        tokens = set(cleaned.split())
        entities = []
        for kw in self.entity_keywords:
            if kw in tokens:
                entities.append(kw)

        # Also map specific phrases that act as entities
        if "back up" in cleaned and "backup" not in entities:
            entities.append("backup")
        if "factory reset" in cleaned and "reset" not in entities:
            entities.append("reset")

        return EnrichedQuery(
            normalized_query=cleaned,
            polarity=polarity,
            entities=sorted(entities)
        )
