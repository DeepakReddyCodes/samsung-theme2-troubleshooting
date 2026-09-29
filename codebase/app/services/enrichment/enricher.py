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

        # Contraction normalization before punctuation removal
        self.contractions_map = {
            r"(?i)\bdon't\b": "do not",
            r"(?i)\bdoesn't\b": "does not",
            r"(?i)\bcan't\b": "cannot",
            r"(?i)\bwon't\b": "will not",
            r"(?i)\bshouldn't\b": "should not",
            r"(?i)\bwouldn't\b": "would not",
            r"(?i)\bcouldn't\b": "could not",
            r"(?i)\baren't\b": "are not",
            r"(?i)\bisn't\b": "is not",
        }

        # Exact explicit operations for polarity scoped by word boundaries
        enable_terms = ["enable", "turn on", "activate"]
        disable_terms = ["disable", "turn off", "deactivate"]

        self.enable_regex = re.compile(rf"\b({'|'.join(enable_terms)})\b")
        self.disable_regex = re.compile(rf"\b({'|'.join(disable_terms)})\b")

        # Negation matcher bound to operations
        self.negation_enable_regex = re.compile(rf"\b(?:do not|cannot|will not|does not)\s+(?:{'|'.join(enable_terms)})\b")
        self.negation_disable_regex = re.compile(rf"\b(?:do not|cannot|will not|does not)\s+(?:{'|'.join(disable_terms)})\b")

        # Entities
        self.entity_keywords = {"backup", "restore", "reset", "lock", "unlock"}

    def _determine_polarity(self, text: str) -> str:
        """Deterministically determine polarity using token-bounded operations and local scoped negation."""
        has_negated_enable = bool(self.negation_enable_regex.search(text))
        has_negated_disable = bool(self.negation_disable_regex.search(text))

        # Remove negated phrases from the text to check for unnegated operations safely
        # We don't modify the actual query text passed outwards, only for this local check
        reduced_text = self.negation_enable_regex.sub("", text)
        reduced_text = self.negation_disable_regex.sub("", reduced_text)

        has_enable = bool(self.enable_regex.search(reduced_text))
        has_disable = bool(self.disable_regex.search(reduced_text))

        # Count total operations found
        total_ops = sum([has_enable, has_disable, has_negated_enable, has_negated_disable])

        # If more than one conflicting intent is detected, fall back to neutral
        if total_ops > 1:
            return "neutral"
        if has_negated_enable:
            return "negated_enable"
        if has_negated_disable:
            return "negated_disable"
        if has_enable:
            return "enable"
        if has_disable:
            return "disable"

        return "neutral"

    def enrich(self, query: str) -> EnrichedQuery:
        """Enrich a raw query into an EnrichedQuery object."""
        if not query or not query.strip():
            return EnrichedQuery(normalized_query="", polarity="neutral", entities=[])

        # Truncate at 1024 chars for safety against pathological inputs
        query = query[:1024]

        # Expand contractions safely before any punctuation stripping
        cleaned = query
        for pat, rep in self.contractions_map.items():
            cleaned = re.sub(pat, rep, cleaned)

        # Strip conversational noise
        cleaned = self.noise_regex.sub("", cleaned).strip()

        # Remove leading numbering like '1. ', '1. "', '2. '
        cleaned = re.sub(r"^\d+[\.\)]\s*[\"']?", "", cleaned)
        # Remove trailing quotes
        cleaned = re.sub(r"[\"']\s*$", "", cleaned)
        cleaned = cleaned.lower()

        # Normalize domain compounds
        for pat, rep in COMPOUND_MAP.items():
            cleaned = re.sub(pat, rep, cleaned)

        # Replace punctuation with spaces to safely check words
        cleaned = re.sub(r"[^\w\s-]", " ", cleaned)
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
