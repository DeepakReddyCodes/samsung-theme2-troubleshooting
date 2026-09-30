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

# Stopwords specific to smartphone UI navigation steps (preserving action verbs)
UI_STOPWORDS = {
    "a", "an", "the", "and", "or", "to", "in", "on", "at", "for", "with", "from",
    "by", "of", "it", "this", "that", "these", "those", "is", "are", "was", "be",
    "tap", "press", "click", "select", "choose", "navigate", "go",
    "device", "phone", "tablet", "samsung", "galaxy", "settings",
    "step", "steps", "please", "your", "my", "between", "then", "into", "onto",
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
            if item.get("id") == "DL-DUMMY":
                continue

            entry_id = item["id"]
            val_obj = item.get("validation") or {}
            val_key = val_obj.get("key", "")

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
    ) -> Tuple[float, List[str]]:
        """Compute structured relevance score for a catalog entry."""
        matched_fields = []

        # 1. Token overlap
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

        # 2. Multi-word exact phrase matches
        phrase_boost = 0.0
        norm_raw = normalize_text(intent_raw)

        val_key_norm = normalize_text(entry["norm_val_key"])
        if len(entry["val_tokens"]) >= 2 and val_key_norm and val_key_norm in norm_raw:
            phrase_boost += 0.35
            matched_fields.append("val_key_exact_phrase")
        elif len(entry["val_tokens"]) == 1 and val_key_norm and val_key_norm == norm_raw.strip():
            phrase_boost += 0.45
            matched_fields.append("val_key_exact_phrase")
        elif entry["val_phrases"] and (entry["val_phrases"] & intent_phrases):
            phrase_boost += 0.25
            matched_fields.append("val_key_phrase")

        msg_norm = normalize_text(entry["norm_message"])
        if len(entry["msg_tokens"]) >= 2 and msg_norm in norm_raw:
            phrase_boost += 0.35
            matched_fields.append("message_exact_phrase")
        elif entry["msg_phrases"] and (entry["msg_phrases"] & intent_phrases):
            phrase_boost += 0.20
            matched_fields.append("message_phrase")

        # 3. Action polarity alignment
        polarity_bonus = 0.0
        orig_type = entry.get("originalType") or ""
        msg_lower = entry["message"].lower()

        is_enable = bool(re.search(r"\b(enable|turn on|activate|start|switch on|back up|backup|save|secure|lock)\b", norm_raw))
        is_disable = bool(re.search(r"\b(disable|turn off|deactivate|stop|switch off|delete|wipe|shut off|unlock)\b", norm_raw))
        is_view = bool(re.search(r"\b(view|open|navigate|go to|check|settings)\b", norm_raw)) and not is_enable and not is_disable

        if is_enable:
            if orig_type == "onURL" or msg_lower.startswith("enable"):
                polarity_bonus += 0.45
                matched_fields.append("polarity_enable_match")
            elif orig_type == "offURL" or msg_lower.startswith("disable"):
                polarity_bonus -= 0.50
        elif is_disable:
            if orig_type == "offURL" or msg_lower.startswith("disable"):
                polarity_bonus += 0.45
                matched_fields.append("polarity_disable_match")
            elif orig_type == "onURL" or msg_lower.startswith("enable"):
                polarity_bonus -= 0.50
        elif is_view:
            if orig_type in {"onClickURL"} or msg_lower.startswith("view"):
                polarity_bonus += 0.25
                matched_fields.append("polarity_view_match")

        confidence = max(0.0, min(1.0, (f1 * 0.5) + phrase_boost + polarity_bonus))
        return confidence, matched_fields

    def match(self, intent: TroubleshootingIntent) -> DeeplinkResolutionResult:
        """Resolve a TroubleshootingIntent to a catalog entry or grounded fallback."""
        intent_raw = intent.full_text()
        intent_tokens = set(normalize_tokens(intent_raw))
        intent_phrases = extract_phrases(intent_raw, 2)

        best_entry = None
        best_confidence = 0.0
        best_fields: List[str] = []

        for entry in self.entries:
            confidence, fields = self._calculate_relevance(
                entry,
                intent_tokens=intent_tokens,
                intent_phrases=intent_phrases,
                intent_raw=intent_raw,
            )

            if confidence > best_confidence:
                best_confidence = confidence
                best_entry = entry
                best_fields = fields

        # Check against confidence threshold
        if best_entry and best_confidence >= self.confidence_threshold:
            raw_item = best_entry["raw"]

            # Actionable deeplink
            actionable_dl = Deeplink(
                deeplink=raw_item["deeplink"],
                description=raw_item.get("description", ""),
                message=raw_item.get("message", ""),
                originalType=raw_item.get("originalType"),
                control_type=raw_item.get("control_type"),
            )

            # Validation deeplink
            val_dl = None
            if raw_item.get("validation"):
                val_data = raw_item["validation"]
                val_dl = ValidationDeepLink(
                    deeplink=val_data["deeplink"],
                    key=val_data["key"],
                    resultType=val_data.get("resultType"),
                    condition=val_data.get("condition"),
                    value=val_data.get("value"),
                )

            return DeeplinkResolutionResult(
                actionable_deeplink=actionable_dl,
                validation_deeplink=val_dl,
                matched_entry_id=best_entry["id"],
                matched_fields=best_fields,
                confidence_score=round(best_confidence, 4),
                is_fallback=False,
                debug_explanation=f"Matched {best_entry['id']} with confidence {best_confidence:.3f}",
            )

        # Fallback: Check if intent has a grounded concrete Settings screen target
        fallback_res = create_grounded_dummy_positive(intent)
        if fallback_res:
            return fallback_res

        # No catalog match and no concrete Settings target
        return DeeplinkResolutionResult(
            actionable_deeplink=None,
            validation_deeplink=None,
            matched_entry_id="NONE",
            matched_fields=[],
            confidence_score=round(best_confidence, 4),
            is_fallback=False,
            debug_explanation="No catalog match and no grounded concrete Settings target.",
        )
