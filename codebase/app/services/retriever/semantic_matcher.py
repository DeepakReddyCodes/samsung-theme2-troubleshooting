"""Optional dense embedding semantic reranker for deeplink catalog matching.

Designed as an optional enhancement layer over the deterministic lexical baseline.
If sentence-transformers is available, it adds dense cosine similarity ranking.
If not available or disabled, it falls back to the deterministic lexical matcher without errors.
"""
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.schema import Condition, Deeplink, ResultTypes, ValidationDeepLink
from app.core.sanitizer import sanitize_text
from app.services.fallback_resolver import create_grounded_dummy_positive
from app.services.retriever.base import (
    DeeplinkResolutionResult,
    IDeeplinkMatcher,
    TroubleshootingIntent,
)
from app.services.retriever.lexical_matcher import (
    DEFAULT_CONFIDENCE_THRESHOLD,
    LexicalDeeplinkMatcher,
)

logger = logging.getLogger(__name__)


class SemanticDeeplinkMatcher(IDeeplinkMatcher):
    """Hybrid matcher combining deterministic lexical scoring with dense embedding similarity."""

    def __init__(
        self,
        catalog_path: Optional[str] = None,
        lexical_matcher: Optional[LexicalDeeplinkMatcher] = None,
        confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
        enable_embeddings: bool = True,
        model_name: str = "all-MiniLM-L6-v2",
    ):
        self.lexical_matcher = lexical_matcher or LexicalDeeplinkMatcher(
            catalog_path=catalog_path,
            confidence_threshold=confidence_threshold,
        )
        self.confidence_threshold = confidence_threshold
        self.enable_embeddings = enable_embeddings
        self.model = None
        self.catalog_embeddings = None

        if self.enable_embeddings:
            self._init_embeddings(model_name)

    def _init_embeddings(self, model_name: str) -> None:
        """Attempt to load sentence transformer model gracefully."""
        try:
            from sentence_transformers import SentenceTransformer
            logger.info(f"Loading embedding model '{model_name}' for semantic deeplink reranking...")
            self.model = SentenceTransformer(model_name)
            self._precompute_embeddings()
            logger.info("Catalog embeddings precomputed successfully.")
        except Exception as e:
            logger.warning(
                f"Embedding model could not be loaded ({e}). Operating in deterministic lexical mode."
            )
            self.model = None

    def _precompute_embeddings(self) -> None:
        """Pre-encode catalog descriptions and messages."""
        if not self.model or not self.lexical_matcher.entries:
            return

        texts = []
        for entry in self.lexical_matcher.entries:
            msg = entry.get("message", "")
            desc = entry.get("description", "")
            qna = entry.get("qna_description", "")
            val_key = (entry.get("validation") or {}).get("key", "")
            # Composite representation of catalog setting
            combined = f"{msg}. {val_key}. {desc}. {qna}".strip()
            texts.append(combined)

        self.catalog_embeddings = self.model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)

    def match(self, intent: TroubleshootingIntent) -> DeeplinkResolutionResult:
        """Match using hybrid lexical + semantic signals, or pure lexical if embeddings inactive."""
        # 1. Always compute the deterministic lexical baseline
        lexical_result = self.lexical_matcher.match(intent)

        if not self.model or self.catalog_embeddings is None:
            return lexical_result

        # 2. If lexical match has very high confidence (>= 0.70), trust it directly
        if lexical_result.confidence_score >= 0.70 and not lexical_result.is_fallback:
            return lexical_result

        # 3. Dense semantic cosine similarity search
        try:
            import numpy as np

            intent_text = intent.full_text()
            intent_vec = self.model.encode([intent_text], convert_to_numpy=True, normalize_embeddings=True)[0]

            # Cosine similarities
            sims = np.dot(self.catalog_embeddings, intent_vec)
            top_idx = int(np.argmax(sims))
            best_sim = float(sims[top_idx])
            best_entry = self.lexical_matcher.entries[top_idx]

            # Hybrid score
            hybrid_score = (0.5 * lexical_result.confidence_score) + (0.5 * best_sim)

            # If semantic similarity provides a strong match (>= 0.65) and outperforms low-confidence lexical
            if best_sim >= 0.65 and (lexical_result.is_fallback or hybrid_score > lexical_result.confidence_score):
                raw = best_entry["raw"]

                actionable_dl = Deeplink(
                    deeplink=raw["deeplink"],  # VERBATIM COPY
                    description=sanitize_text(raw.get("description", "")),
                    message=sanitize_text(raw.get("message", "")),
                    originalType=raw.get("originalType"),
                    classes=raw.get("classes"),
                )

                validation_dl = None
                if raw.get("validation"):
                    val_raw = raw["validation"]
                    res_type = (
                        ResultTypes(val_raw["resultType"])
                        if val_raw.get("resultType") in ResultTypes.__members__.values()
                        else None
                    )
                    cond = (
                        Condition(val_raw["condition"])
                        if val_raw.get("condition") in Condition.__members__.values()
                        else None
                    )
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
                    matched_fields=["semantic_embedding_cosine", "hybrid_rerank"],
                    confidence_score=round(hybrid_score, 4),
                    is_fallback=False,
                    debug_explanation=(
                        f"Matched catalog entry {raw['id']} ('{raw.get('message')}') "
                        f"via semantic embeddings (cosine: {best_sim:.3f}, hybrid: {hybrid_score:.3f})"
                    ),
                )
        except Exception as e:
            logger.debug(f"Semantic reranking failed ({e}), using lexical result.")

        return lexical_result
