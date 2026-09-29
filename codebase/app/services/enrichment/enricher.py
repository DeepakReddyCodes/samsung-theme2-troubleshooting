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
            r"(?i)\b(please|tell me|how do i|how to|i want to|can you|help me)\b"
        )

        self.enable_keywords = {"enable", "turn on", "activate", "start", "add", "setup"}
        self.disable_keywords = {"disable", "turn off", "deactivate", "stop", "remove", "delete"}
        self.entity_keywords = {"backup", "restore", "reset", "lock", "unlock"}

    def enrich(self, query: str) -> EnrichedQuery:
        """Enrich a raw query into an EnrichedQuery object."""
        if not query or not query.strip():
            return EnrichedQuery(normalized_query="", polarity="neutral", entities=[])

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

        # Replace punctuation with spaces
        cleaned = re.sub(r"[^\w\s]", " ", cleaned)
        # Collapse multiple whitespaces
        cleaned = re.sub(r"\s+", " ", cleaned).strip()

        # Determine polarity
        tokens = set(cleaned.split())
        polarity = "neutral"

        # Check explicit keywords
        has_enable = any(kw in tokens for kw in self.enable_keywords) or "turn on" in cleaned
        has_disable = any(kw in tokens for kw in self.disable_keywords) or "turn off" in cleaned

        if has_enable and not has_disable:
            polarity = "enable"
        elif has_disable and not has_enable:
            polarity = "disable"

        # Determine entities
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
            entities=entities
        )
