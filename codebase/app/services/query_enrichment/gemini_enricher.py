"""Gemini LLM Provider for Stage 1 Query Enrichment.

Uses Google GenAI structured output to normalize complaints, identify Galaxy domains,
extract entities, and detect polarity while strictly avoiding solution generation.
Delegates to DeterministicQueryEnricher on missing credentials, network errors, or timeouts.
"""
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional, Union

from app.services.query_enrichment.deterministic_enricher import DeterministicQueryEnricher
from app.services.query_enrichment.models import EnrichedQuery
from app.services.query_enrichment.normalizer import normalize_query_text

logger = logging.getLogger(__name__)

GEMINI_STAGE1_SYSTEM_PROMPT = """You are a specialized Samsung Galaxy device technical query analyzer for Stage 1 triage.
Your task is to analyze the user's raw complaint and extract technical metadata.

CRITICAL RULES:
1. Do NOT provide troubleshooting steps, solutions, or recommendations.
2. Normalize the technical terminology (e.g. 'wifi' -> 'Wi-Fi', 'won't charge' -> 'unresponsive to charger').
3. Identify the Galaxy hardware/software domain (Display, Connections, Battery, Accounts and backup, Camera, Accessibility, etc.).
4. Detect the exact user polarity (negative issue, enable request, disable request, reset, backup, restore).
5. Output pure JSON matching this schema:
{
  "technical_query": "Concise 1-sentence technical description of the problem/request",
  "domain": "Domain Name",
  "symptoms": ["symptom 1", "symptom 2"],
  "entities": ["entity 1", "entity 2"],
  "polarity": "negative" | "positive" | "enable" | "disable" | "reset" | "backup" | "restore",
  "requested_action": "enable" | "disable" | "configure" | "reset" | "backup" | "restore" | null,
  "intent_category": "troubleshooting" | "configuration" | "inquiry"
}
"""


class GeminiQueryEnricher:
    """Stage 1 LLM query enricher with deterministic fallback."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        fallback: Optional[DeterministicQueryEnricher] = None,
        timeout_s: float = 8.0,
    ):
        if api_key is not None:
            self.api_key = api_key
        else:
            self.api_key = os.getenv("GEMINI_API_KEY", "")

        self.model_name = model_name or os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
        self.fallback = fallback or DeterministicQueryEnricher()
        self.timeout_s = timeout_s
        self.client = None
        self.last_provider_used = "deterministic"
        self.last_latency_ms = 0.0

        if self.api_key and self.api_key.strip():
            try:
                from google import genai
                self.client = genai.Client(api_key=self.api_key)
                logger.info(f"GeminiQueryEnricher initialized with model '{self.model_name}'")
            except Exception as e:
                logger.warning(f"Failed to initialize GenAI client in GeminiQueryEnricher ({e}). Operating in fallback mode.")
                self.client = None
        else:
            logger.info("GeminiQueryEnricher: No GEMINI_API_KEY found. Operating in deterministic fallback mode.")

    def enrich(
        self,
        query: str,
        siis_response: Optional[Union[Dict[str, Any], str]] = None,
    ) -> EnrichedQuery:
        """Enrich raw query using Gemini API or fallback."""
        t0 = time.perf_counter()

        # Always compute baseline deterministic fields for safety and fallback consistency
        siis_title = None
        siis_content = None
        if isinstance(siis_response, dict):
            siis_title = str(siis_response.get("title", ""))
            siis_content = str(siis_response.get("content", ""))
        elif isinstance(siis_response, str):
            siis_title = siis_response[:100]
            siis_content = siis_response

        det_enriched = self.fallback.enrich(
            raw_query=query,
            siis_title=siis_title,
            siis_content=siis_content,
        )

        if not self.client:
            self.last_provider_used = "deterministic"
            self.last_latency_ms = (time.perf_counter() - t0) * 1000.0
            det_enriched.provider_used = "deterministic"
            return det_enriched

        prompt = f"""User Raw Complaint: {query}
Initial Normalized Text: {det_enriched.normalized_query}
Context Article Title (if any): {siis_title or 'None'}

Analyze and return the structured technical query metadata in JSON:"""

        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config={
                    "system_instruction": GEMINI_STAGE1_SYSTEM_PROMPT,
                    "response_mime_type": "application/json",
                    "temperature": 0.0,
                },
            )

            raw_text = response.text.strip()
            data = json.loads(raw_text)

            # Validate that LLM did not hallucinate troubleshooting steps in technical query
            tech_q = data.get("technical_query", det_enriched.technical_query)
            if any(kw in tech_q.lower() for kw in ["step 1", "first,", "to fix this", "you must", "navigate to"]):
                tech_q = det_enriched.technical_query

            domain = data.get("domain") or det_enriched.domain
            polarity = data.get("polarity") or det_enriched.polarity
            req_act = data.get("requested_action") or det_enriched.requested_action
            intent_cat = data.get("intent_category") or det_enriched.intent_category
            symptoms = data.get("symptoms") or det_enriched.symptoms
            entities = data.get("entities") or det_enriched.entities

            self.last_provider_used = "gemini"
            self.last_latency_ms = (time.perf_counter() - t0) * 1000.0

            return EnrichedQuery(
                raw_query=query,
                normalized_query=det_enriched.normalized_query,
                technical_query=tech_q,
                domain=domain,
                symptoms=symptoms,
                entities=entities,
                polarity=polarity,
                requested_action=req_act,
                constraints=det_enriched.constraints,
                intent_category=intent_cat,
                candidate_settings_screens=det_enriched.candidate_settings_screens,
                siis_fingerprint=det_enriched.siis_fingerprint,
                stage1_confidence=0.95,
                provider_used="gemini",
            )
        except Exception as e:
            logger.warning(f"Gemini Stage 1 query enrichment failed ({e}). Falling back to deterministic enricher.")
            self.last_provider_used = "deterministic_fallback"
            self.last_latency_ms = (time.perf_counter() - t0) * 1000.0
            det_enriched.provider_used = "deterministic_fallback"
            return det_enriched
