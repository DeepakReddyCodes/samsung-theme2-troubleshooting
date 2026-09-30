"""Deterministic, high-precision lexical and semantic metadata matcher for deeplinks.json.

Enforces:
1. deeplinks.json is the ONLY source of truth.
2. NEVER alters, generates, or repairs a catalog URI.
3. Copies selected catalog URIs and validation objects VERBATIM.
4. Matches using metadata: description, message, qna_description, validation.key, originalType.
5. Emits complete debugging evidence (matched_entry_id, matched_fields, confidence_score, is_fallback).
6. Automatically routes to grounded fallback when confidence < threshold.
7. Guarantees zero URL leaks on all output metadata.
"""
import json
import logging
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from app.core.sanitizer import sanitize_text
from app.core.schema import (
    Condition,
    Deeplink,
    ResultTypes,
    ValidationDeepLink,
)
from app.services.fallback_resolver import create_grounded_dummy_positive
from app.services.retriever.base import (
    DeeplinkResolutionResult,
    IDeeplinkMatcher,
    TroubleshootingIntent,
)

logger = logging.getLogger(__name__)

# Stopwords specific to smartphone UI navigation steps
UI_STOPWORDS = {
    "a", "an", "the", "and", "or", "to", "in", "on", "at", "for", "with", "from",
    "by", "of", "it", "this", "that", "these", "those", "is", "are", "was", "be",
    "tap", "press", "click", "select", "choose", "navigate", "open", "go",
    "device", "phone", "tablet", "samsung", "galaxy", "settings", "screen",
    "step", "steps", "please", "your", "my", "between", "then", "into", "onto",
    "turn", "off", "double",
}

# Negative polarity terms favoring offURL / Disable actions
NEGATIVE_POLARITY_TERMS = {
    "disable", "turn off", "switch off", "deactivate", "stop", "remove", "hide", "mute", "decrease", "close",
}

# Positive polarity terms favoring onURL / Enable actions
POSITIVE_POLARITY_TERMS = {
    "enable", "turn on", "switch on", "activate", "start", "show", "unmute", "increase", "open",
}

DEFAULT_CONFIDENCE_THRESHOLD = 0.35


def normalize_text(text: str) -> str:
    """Normalize domain compound words and punctuation."""
    if not text:
        return ""
    t = text.lower()
    t = re.sub(r"\bbackup\b", "back up", t)
    t = re.sub(r"\bwi-fi\b", "wifi", t)
    t = re.sub(r"\bwi fi\b", "wifi", t)
    t = re.sub(r"\btouchscreen\b", "touch screen", t)
    t = re.sub(r"\blockscreen\b", "lock screen", t)
    t = re.sub(r"\bautosync\b", "auto sync", t)
    return t


def normalize_tokens(text: str) -> List[str]:
    """Lowercase, normalize compounds, strip punctuation, remove UI stopwords."""
    if not text:
        return []
    norm = normalize_text(text)
    raw_tokens = re.findall(r"[a-z0-9]+", norm)
    return [t for t in raw_tokens if t not in UI_STOPWORDS and len(t) > 1]


def extract_phrases(text: str, n: int = 2) -> Set[str]:
    """Extract consecutive content-token n-grams from text, ignoring stopwords."""
    if not text:
        return set()
    words = normalize_tokens(text)
    if len(words) < n:
        return set()
    return {" ".join(words[i : i + n]) for i in range(len(words) - n + 1)}


class LexicalDeeplinkMatcher(IDeeplinkMatcher):
    """Deterministic, metadata-weighted retriever matching intents against deeplinks.json."""

    def __init__(
        self,
        catalog_path: Optional[str] = None,
        confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
    ):
        self.confidence_threshold = confidence_threshold
        self.entries: List[Dict[str, Any]] = []
        self.id_to_entry: Dict[str, Dict[str, Any]] = {}

        path = catalog_path or (Path(__file__).resolve().parent.parent.parent / "data" / "deeplinks.json")
        if not Path(path).exists():
            # Try workspace root
            path = Path(__file__).resolve().parent.parent.parent.parent / "deeplinks.json"

        self.load_catalog(path)

    def load_catalog(self, catalog_path: Path | str) -> None:
        """Load and index all entries from deeplinks.json."""
        p = Path(catalog_path)
        if not p.exists():
            logger.warning(f"Catalog file not found at {p}")
            return

        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)

        raw_entries = data.get("deeplinks", [])
        self.entries = []
        self.id_to_entry = {}

        for item in raw_entries:
            # DL-DUMMY is reserved exclusively for the fallback handler
            if item.get("id") == "DL-DUMMY":
                continue

            entry_id = item["id"]
            val_obj = item.get("validation") or {}
            val_key = val_obj.get("key", "")

            # Pre-compute normalized tokens and phrases
            msg_tokens = set(normalize_tokens(item.get("message", "")))
            val_tokens = set(normalize_tokens(val_key))
            desc_tokens = set(normalize_tokens(item.get("description", "")))
            qna_tokens = set(normalize_tokens(item.get("qna_description", "")))

            msg_phrases = extract_phrases(item.get("message", ""), 2)
            val_phrases = extract_phrases(val_key, 2)

            indexed_item = {
                "id": entry_id,
                "raw": item,
                "deeplink": item["deeplink"],
                "message": item.get("message", ""),
                "description": item.get("description", ""),
                "qna_description": item.get("qna_description", ""),
                "originalType": item.get("originalType"),
                "control_type": item.get("control_type"),
                "validation": item.get("validation"),
                "msg_tokens": msg_tokens,
                "val_tokens": val_tokens,
                "desc_tokens": desc_tokens,
                "qna_tokens": qna_tokens,
                "msg_phrases": msg_phrases,
                "val_phrases": val_phrases,
                "norm_message": item.get("message", "").lower(),
                "norm_val_key": val_key.lower(),
            }
            self.entries.append(indexed_item)
            self.id_to_entry[entry_id] = indexed_item

        logger.info(f"Loaded and indexed {len(self.entries)} catalog deeplinks.")

    def _calculate_relevance(
        self,
        entry: Dict[str, Any],
        intent_tokens: Set[str],
        intent_phrases: Set[str],
        intent_raw: str,
        is_negative_intent: bool,
        is_positive_intent: bool = False,
    ) -> Tuple[float, List[str]]:
        """Compute structured relevance score for a catalog entry."""
        matched_fields = []

        # 1. Tokens
        primary_tokens = entry["msg_tokens"] | entry["val_tokens"]
        all_entry_tokens = primary_tokens | entry["desc_tokens"]
        overlap = intent_tokens & all_entry_tokens

        if not overlap:
            return 0.0, []

        recall = len(overlap) / max(len(intent_tokens), 1)
        precision = len(intent_tokens & primary_tokens) / max(len(primary_tokens), 1)
        f1 = (2 * precision * recall) / (precision + recall + 1e-6)

        if overlap & entry["val_tokens"]:
            matched_fields.append("val_key_tokens")
        if overlap & entry["msg_tokens"]:
            matched_fields.append("message_tokens")
        if overlap & entry["desc_tokens"]:
            matched_fields.append("description_tokens")

        # 2. Multi-word exact phrase matches (must be >= 2 words)
        phrase_boost = 0.0
        norm_raw = intent_raw.lower()

        val_words = entry["val_tokens"]
        if len(val_words) >= 2 and entry["norm_val_key"] in norm_raw:
            phrase_boost += 0.40
            matched_fields.append("val_key_exact_phrase")
        elif entry["val_phrases"] and (entry["val_phrases"] & intent_phrases):
            phrase_boost += 0.25
            matched_fields.append("val_key_phrase")

        msg_words = entry["msg_tokens"]
        if len(msg_words) >= 2 and entry["norm_message"] in norm_raw:
            phrase_boost += 0.35
            matched_fields.append("message_exact_phrase")
        elif entry["msg_phrases"] and (entry["msg_phrases"] & intent_phrases):
            phrase_boost += 0.20
            matched_fields.append("message_phrase")

        # 3. Polarity alignment (Enable vs Disable)
        polarity_bonus = 0.0
        orig_type = entry.get("originalType") or ""
        msg_lower = entry["message"].lower()

        is_entry_negative = orig_type == "offURL" or any(term in msg_lower for term in NEGATIVE_POLARITY_TERMS)
        is_entry_positive = orig_type == "onURL" or any(term in msg_lower for term in POSITIVE_POLARITY_TERMS)

        if is_negative_intent:
            if is_entry_negative:
                polarity_bonus += 0.20
                matched_fields.append("polarity_negative_match")
            elif is_entry_positive:
                polarity_bonus -= 0.30
        elif is_positive_intent:
            if is_entry_positive:
                polarity_bonus += 0.20
                matched_fields.append("polarity_positive_match")
            elif is_entry_negative:
                polarity_bonus -= 0.30
        else:
            if orig_type == "onClickURL" or msg_lower.startswith("view") or msg_lower.startswith("open"):
                polarity_bonus += 0.10
                matched_fields.append("polarity_neutral_match")

        confidence = max(0.0, min(1.0, (f1 * 0.6) + phrase_boost + polarity_bonus))
        return confidence, matched_fields

    def match(self, intent: TroubleshootingIntent) -> DeeplinkResolutionResult:
        """Resolve a TroubleshootingIntent to a catalog entry or grounded fallback."""
        intent_raw = intent.full_text()
        intent_tokens = set(normalize_tokens(intent_raw))
        intent_phrases = extract_phrases(intent_raw, 2)

        # Check polarity
        intent_lower = intent_raw.lower()
        is_negative = any(term in intent_lower for term in NEGATIVE_POLARITY_TERMS)
        is_positive = any(term in intent_lower for term in POSITIVE_POLARITY_TERMS)

        candidates = []

        for entry in self.entries:
            confidence, fields = self._calculate_relevance(
                entry,
                intent_tokens=intent_tokens,
                intent_phrases=intent_phrases,
                intent_raw=intent_raw,
                is_negative_intent=is_negative,
                is_positive_intent=is_positive,
            )
            if confidence > 0:
                candidates.append((confidence, entry, fields))

        candidates.sort(key=lambda x: x[0], reverse=True)

        best_entry = None
        best_confidence = 0.0
        best_fields: List[str] = []

        MARGIN_THRESHOLD = 0.05

        if candidates:
            top_conf, top_entry, top_fields = candidates[0]

            # Check for ambiguity with runner-up
            if len(candidates) > 1:
                runner_up_conf = candidates[1][0]
                if top_conf >= self.confidence_threshold and (top_conf - runner_up_conf) >= MARGIN_THRESHOLD:
                    best_entry = top_entry
                    best_confidence = top_conf
                    best_fields = top_fields
                else:
                    # Ambiguous
                    best_confidence = top_conf
            elif top_conf >= self.confidence_threshold:
                best_entry = top_entry
                best_confidence = top_conf
                best_fields = top_fields

        # If confidence passes threshold, select catalog entry verbatim
        if best_entry and best_confidence >= self.confidence_threshold:
            raw = best_entry["raw"]

            # Verbatim actionable deeplink copy
            actionable_dl = Deeplink(
                deeplink=raw["deeplink"],  # VERBATIM COPY
                description=sanitize_text(raw.get("description", "")),
                message=sanitize_text(raw.get("message", "")),
                originalType=raw.get("originalType"),
                classes=raw.get("classes"),
            )

            # Verbatim validation deeplink copy
            validation_dl = None
            if raw.get("validation"):
                val_raw = raw["validation"]
                res_type = None
                if val_raw.get("resultType") in ResultTypes.__members__.values():
                    res_type = ResultTypes(val_raw["resultType"])

                cond = None
                if val_raw.get("condition") in Condition.__members__.values():
                    cond = Condition(val_raw["condition"])

                validation_dl = ValidationDeepLink(
                    deeplink=val_raw["deeplink"],  # VERBATIM COPY
                    key=sanitize_text(val_raw.get("key", "")),
                    resultType=res_type,
                    condition=cond,
                    value=val_raw.get("value"),
                )

            return DeeplinkResolutionResult(
                actionable_deeplink=actionable_dl,
                validation_deeplink=validation_dl,
                matched_entry_id=raw["id"],
                matched_fields=best_fields,
                confidence_score=round(best_confidence, 4),
                is_fallback=False,
                debug_explanation=(
                    f"Matched catalog entry {raw['id']} ('{raw.get('message')}') "
                    f"with confidence {best_confidence:.3f} on fields: {', '.join(best_fields)}"
                ),
            )

        # Fallback if below confidence threshold
        logger.debug(f"Confidence {best_confidence:.3f} below threshold {self.confidence_threshold}. Triggering fallback.")
        fallback = create_grounded_dummy_positive(intent)

        if fallback:
            return fallback

        # If no concrete target can be found, return a safe null resolution instead of hallucinating.
        return DeeplinkResolutionResult(
            actionable_deeplink=None,
            validation_deeplink=None,
            matched_entry_id="NONE",
            matched_fields=[],
            confidence_score=0.0,
            is_fallback=True,
            debug_explanation="No catalog match and no concrete settings target found for fallback."
        )
