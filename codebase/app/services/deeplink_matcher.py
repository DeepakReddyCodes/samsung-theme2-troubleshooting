"""High-level Deeplink Resolver orchestrating catalog matching and grounded fallbacks.

Serves as the clean facade for the future SIIS extraction engine and tests.
Enforces:
1. Strict catalog integrity: deeplinks.json is the single source of truth.
2. Verbatim URI and validation preservation without modification.
3. Auto action invariant: every auto action receives an actionable deeplink.
4. Grounded bixby://dummy_positive fallback when confidence < threshold.
5. Zero URL leaks across all returned fields.
"""
import logging
from pathlib import Path
from typing import Dict, List, Optional, Union

from app.core.sanitizer import sanitize_text
from app.services.retriever.base import (
    DeeplinkResolutionResult,
    IDeeplinkMatcher,
    TroubleshootingIntent,
)
from app.services.retriever.lexical_matcher import (
    DEFAULT_CONFIDENCE_THRESHOLD,
    LexicalDeeplinkMatcher,
)
from app.services.retriever.semantic_matcher import SemanticDeeplinkMatcher

logger = logging.getLogger(__name__)


class DeeplinkResolver:
    """High-level resolver managing deeplink resolution and fallback guarantees."""

    def __init__(
        self,
        catalog_path: Optional[Union[str, Path]] = None,
        use_embeddings: bool = False,
        confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
    ):
        self.catalog_path = catalog_path
        self.confidence_threshold = confidence_threshold
        self.use_embeddings = use_embeddings

        # Initialize deterministic baseline
        self.lexical_matcher = LexicalDeeplinkMatcher(
            catalog_path=str(catalog_path) if catalog_path else None,
            confidence_threshold=confidence_threshold,
        )

        if use_embeddings:
            self.matcher: IDeeplinkMatcher = SemanticDeeplinkMatcher(
                catalog_path=str(catalog_path) if catalog_path else None,
                lexical_matcher=self.lexical_matcher,
                confidence_threshold=confidence_threshold,
                enable_embeddings=True,
            )
        else:
            self.matcher = self.lexical_matcher

    def resolve(self, intent: TroubleshootingIntent) -> DeeplinkResolutionResult:
        """Resolve a TroubleshootingIntent to a catalog entry or grounded fallback."""
        result = self.matcher.match(intent)

        # Enforce zero-URL leak sanitization across all returned metadata
        if result.actionable_deeplink:
            result.actionable_deeplink.description = sanitize_text(result.actionable_deeplink.description)
            if result.actionable_deeplink.message:
                result.actionable_deeplink.message = sanitize_text(result.actionable_deeplink.message)

        if result.validation_deeplink:
            result.validation_deeplink.key = sanitize_text(result.validation_deeplink.key)

        return result

    def resolve_from_step_group(
        self,
        action_name: str,
        steps: List[str],
        screen_hint: str = "",
        category: str = "auto",
    ) -> DeeplinkResolutionResult:
        """Convenience method resolving from explicit action details."""
        intent = TroubleshootingIntent(
            action_name=action_name,
            steps=steps,
            screen_hint=screen_hint,
            category=category,
        )
        return self.resolve(intent)

    def get_catalog_stats(self) -> Dict[str, Union[int, str]]:
        """Return catalog statistics for health and debugging audits."""
        entries = self.lexical_matcher.entries
        with_val = sum(1 for e in entries if e.get("validation"))
        return {
            "total_entries": len(entries),
            "entries_with_validation": with_val,
            "matcher_type": type(self.matcher).__name__,
            "confidence_threshold": self.confidence_threshold,
        }
