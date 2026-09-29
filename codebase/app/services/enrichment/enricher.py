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
    technical_terms: List[str] = field(default_factory=list)
    intent_candidates: List[str] = field(default_factory=list)


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
        self.enable_terms = ["enable", "turn on", "activate"]
        self.disable_terms = ["disable", "turn off", "deactivate"]

        self.enable_regex = re.compile(rf"\b({'|'.join(self.enable_terms)})\b")
        self.disable_regex = re.compile(rf"\b({'|'.join(self.disable_terms)})\b")

        # Negation matcher bound to operations
        # Differentiating between problem/failure semantics ("cannot", "will not") and active negations ("do not")
        self.problem_prefixes = ["cannot", "will not", "does not", "can not", "won t", "can t", "cannot be", "can not be", "will not be"]
        self.negation_prefixes = ["do not", "don t"]

        self.problem_enable_regex = re.compile(rf"\b(?:{'|'.join(self.problem_prefixes)})\s+(?:{'|'.join(self.enable_terms)})\b")
        self.problem_disable_regex = re.compile(rf"\b(?:{'|'.join(self.problem_prefixes)})\s+(?:{'|'.join(self.disable_terms)})\b")

        self.negation_enable_regex = re.compile(rf"\b(?:{'|'.join(self.negation_prefixes)})\s+(?:{'|'.join(self.enable_terms)})\b")
        self.negation_disable_regex = re.compile(rf"\b(?:{'|'.join(self.negation_prefixes)})\s+(?:{'|'.join(self.disable_terms)})\b")

        # Extra pattern to catch "wifi cannot be enabled"
        # We look for term + problem prefix + enable word (with optional 'd')
        # E.g., "wifi cannot be enabled" -> problem enable
        self.problem_postfix_enable_regex = re.compile(rf"\b(?:{'|'.join(self.problem_prefixes)})\s+(?:{'|'.join([t+'d' for t in self.enable_terms] + self.enable_terms)})\b")
        self.problem_postfix_disable_regex = re.compile(rf"\b(?:{'|'.join(self.problem_prefixes)})\s+(?:{'|'.join([t+'d' for t in self.disable_terms] + self.disable_terms)})\b")

        # Entities
        self.entity_keywords = {"backup", "restore", "reset", "lock", "unlock"}

    def _determine_polarity(self, text: str) -> str:
        """Deterministically determine polarity using token-bounded operations and local scoped negation."""
        has_problem_enable = bool(self.problem_enable_regex.search(text)) or bool(self.problem_postfix_enable_regex.search(text))
        has_problem_disable = bool(self.problem_disable_regex.search(text)) or bool(self.problem_postfix_disable_regex.search(text))
        has_negated_enable = bool(self.negation_enable_regex.search(text))
        has_negated_disable = bool(self.negation_disable_regex.search(text))

        # Remove negated phrases from the text to check for unnegated operations safely
        # We don't modify the actual query text passed outwards, only for this local check
        reduced_text = self.problem_enable_regex.sub("", text)
        reduced_text = self.problem_postfix_enable_regex.sub("", reduced_text)
        reduced_text = self.problem_disable_regex.sub("", reduced_text)
        reduced_text = self.problem_postfix_disable_regex.sub("", reduced_text)
        reduced_text = self.negation_enable_regex.sub("", reduced_text)
        reduced_text = self.negation_disable_regex.sub("", reduced_text)

        has_enable = bool(self.enable_regex.search(reduced_text))
        has_disable = bool(self.disable_regex.search(reduced_text))

        # Count total operations found
        total_ops = sum([has_enable, has_disable, has_negated_enable, has_negated_disable, has_problem_enable, has_problem_disable])

        # If more than one conflicting intent is detected, fall back to neutral
        if total_ops > 1:
            return "neutral"

        if has_problem_enable or has_problem_disable:
            # "cannot enable" or "cannot disable" -> problem state rather than request negation
            return "problem"

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
            return EnrichedQuery(
                normalized_query="",
                polarity="neutral",
                entities=[],
                technical_terms=[],
                intent_candidates=[]
            )

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

        # Technical Terms (Deterministic domain vocabulary)
        domain_vocab = ["wifi", "bluetooth", "touch screen", "lock screen", "smart switch", "auto sync", "backup", "restore", "reset", "lock", "unlock"]
        technical_terms = []
        for term in domain_vocab:
            if re.search(rf"\b{term}\b", cleaned):
                technical_terms.append(term)

        # Determine entities
        tokens = set(cleaned.split())
        entities = []
        for kw in self.entity_keywords:
            if kw in tokens:
                entities.append(kw)

        # Also map specific phrases that act as entities
        if "back up" in cleaned and "backup" not in entities:
            entities.append("backup")
            if "backup" not in technical_terms:
                technical_terms.append("backup")
        if "factory reset" in cleaned and "reset" not in entities:
            entities.append("reset")
            if "reset" not in technical_terms:
                technical_terms.append("reset")

        # Intent Candidates (Operation + Contextual Target)
        intent_candidates = []

        # Deterministic phrase-scoped operation parsing by chunks
        # We split by 'and', 'but', ',', '.' to evaluate operations locally and preserve pairings.
        chunks = re.split(r'\band\b|\bbut\b|,|\.', cleaned)
        targets = [t for t in technical_terms if t not in self.entity_keywords]

        last_op = None
        for chunk in chunks:
            chunk = chunk.strip()
            if not chunk: continue

            # Find operation in this chunk
            op = None
            if self.enable_regex.search(chunk) or self.problem_enable_regex.search(chunk) or self.negation_enable_regex.search(chunk) or self.problem_postfix_enable_regex.search(chunk):
                op = "enable"
            elif self.disable_regex.search(chunk) or self.problem_disable_regex.search(chunk) or self.negation_disable_regex.search(chunk) or self.problem_postfix_disable_regex.search(chunk):
                op = "disable"

            if op:
                last_op = op

            # If we don't have an op in this chunk but had one in the previous, carry it over if there's a target
            # e.g., "enable smart switch and wifi" -> "enable smart switch", "enable wifi"
            current_op = op if op else last_op

            if current_op:
                chunk_targets = [t for t in targets if t in chunk]
                if chunk_targets:
                    for t in chunk_targets:
                        intent_candidates.append(f"{current_op} {t}")
                elif op:
                    # If there's an explicit op but no target in this chunk,
                    # check if the whole query has exactly 1 target.
                    if len(targets) == 1:
                        intent_candidates.append(f"{op} {targets[0]}")
                    elif not targets:
                        intent_candidates.append(op)

        # Append standalone action intents (e.g. reset, restore)
        for kw in ["reset", "restore", "backup", "lock", "unlock"]:
            if kw in entities:
                intent_candidates.append(kw)

        # Ensure candidates are unique
        intent_candidates = list(set(intent_candidates))

        # Fallback if no specific intents found and polarity isn't neutral
        if not intent_candidates and polarity not in {"neutral", "problem"}:
            intent_candidates.append(polarity)

        return EnrichedQuery(
            normalized_query=cleaned,
            polarity=polarity,
            entities=sorted(entities),
            technical_terms=sorted(list(set(technical_terms))),
            intent_candidates=sorted(list(set(intent_candidates)))
        )
