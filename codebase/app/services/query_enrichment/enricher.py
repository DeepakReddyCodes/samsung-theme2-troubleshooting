"""Stage 1 Query Enrichment Orchestrator for Samsung Guided Troubleshooting Engine.

Converts raw user complaint into a structured EnrichedQuery contract.
Integrates Gemini LLM query reasoning with fast deterministic fallback, maintaining
strict grounding and invariant safety.
"""
import logging
from typing import Any, Dict, Optional, Union

from app.services.query_enrichment.deterministic_enricher import DeterministicQueryEnricher
from app.services.query_enrichment.gemini_enricher import GeminiQueryEnricher
from app.services.query_enrichment.models import EnrichedQuery

logger = logging.getLogger(__name__)


class QueryEnricher:
    """Stage 1 query enricher providing technical interpretation of raw complaints."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        deterministic_fallback: Optional[DeterministicQueryEnricher] = None,
        gemini_enricher: Optional[GeminiQueryEnricher] = None,
    ):
        self.deterministic = deterministic_fallback or DeterministicQueryEnricher()
        self.gemini_enricher = gemini_enricher or GeminiQueryEnricher(
            api_key=api_key,
            model_name=model_name,
            fallback=self.deterministic,
        )

    @property
    def last_provider_used(self) -> str:
        return self.gemini_enricher.last_provider_used

    def enrich(
        self,
        query: str,
        siis_response: Optional[Union[Dict[str, Any], str]] = None,
    ) -> EnrichedQuery:
        """Enrich raw user query into an EnrichedQuery object via Gemini or deterministic fallback."""
        return self.gemini_enricher.enrich(query=query, siis_response=siis_response)
