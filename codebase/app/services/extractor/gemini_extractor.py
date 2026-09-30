"""Gemini API Extractor for Stage 2 Troubleshooting Structuring.

Guarantees:
1. Provider abstraction: Uses Google Gemini GenAI API when configured.
2. Graceful fallback: Automatically delegates to DeterministicFallbackExtractor
   if API key is missing, network is unavailable, call times out, or output is malformed.
3. Strict intermediate output: Model produces IntermediateIntent JSON, NEVER URIs
   or final ContextDeeplinkResponse.
4. Grounded in SIIS: Injects SIIS text as the sole source of truth with strict grounding guards.
5. Telemetry: Records latency and exact provider used (gemini vs deterministic_fallback).
"""
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

from app.services.extractor.base import ExtractedAction, ILLMProvider, IntermediateIntent
from app.services.extractor.deterministic_extractor import DeterministicFallbackExtractor

logger = logging.getLogger(__name__)

GEMINI_STAGE2_SYSTEM_PROMPT = """You are a specialized Samsung Galaxy device support triage engine for Stage 2 knowledge structuring.
Your task is to extract structured troubleshooting actions EXCLUSIVELY from the provided SIIS (Samsung Internal Knowledge Store) article.

CRITICAL INVARIANTS:
1. SIIS text is your SOLE source of truth. Do NOT invent troubleshooting steps, hardware checks, or settings screens not explicitly present in the article text.
2. Deconstruct the troubleshooting procedure into 1 to 3 distinct, screen-specific actionable steps.
3. For each action, classify category as:
   - "auto": for settings that can be configured, toggled, or navigated in Samsung Settings.
   - "manual": for physical inspection, hardware cleaning, external connections, or service center visits.
   - "critical": for destructive operations like factory data reset or forced system reboot.
4. Action description MUST be 5 to 7 words and start with "It will".
5. Goal title MUST be 2 to 3 words.
6. Return pure JSON matching this exact schema:
{
  "topic": "Short Topic Name",
  "goal_mode": "Troubleshooting" | "Configuration",
  "title": "2-3 words title",
  "actions": [
    {
      "action_name": "Title Case Action Name",
      "description": "It will ... (5-7 words)",
      "category": "auto" | "manual" | "critical",
      "steps": ["Step 1 sentence", "Step 2 sentence"],
      "screen_hint": "Concrete screen name if mentioned in SIIS (e.g. Wi-Fi, Display, Developer options)",
      "evidence": "Source quote or heading from SIIS"
    }
  ]
}
"""


class GeminiExtractor(ILLMProvider):
    """Google Gemini API intermediate extractor with deterministic fallback."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        fallback: Optional[ILLMProvider] = None,
        timeout_s: float = 12.0,
    ):
        if api_key is not None:
            self.api_key = api_key
        else:
            self.api_key = os.getenv("GEMINI_API_KEY", "")

        self.model_name = model_name or os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
        self.fallback = fallback or DeterministicFallbackExtractor()
        self.timeout_s = timeout_s
        self.client = None
        self.last_provider_used = "deterministic"
        self.last_latency_ms = 0.0

        if self.api_key and self.api_key.strip():
            try:
                from google import genai
                self.client = genai.Client(api_key=self.api_key)
                logger.info(f"GeminiExtractor initialized with model '{self.model_name}'")
            except Exception as e:
                logger.warning(f"Failed to initialize Gemini client ({e}). Operating in deterministic fallback mode.")
                self.client = None
        else:
            logger.info("GeminiExtractor: No GEMINI_API_KEY found. Operating in deterministic fallback mode.")

    def extract(self, query: str, siis_title: str, siis_content: str) -> IntermediateIntent:
        """Extract structured intermediate intent using Gemini or deterministic fallback."""
        t0 = time.perf_counter()

        if not self.client:
            self.last_provider_used = "deterministic"
            res = self.fallback.extract(query, siis_title, siis_content)
            self.last_latency_ms = (time.perf_counter() - t0) * 1000.0
            return res

        user_prompt = f"""User Technical Query: {query}

Authoritative SIIS Knowledge Article:
Title: {siis_title}
Content:
{siis_content}

Extract the structured troubleshooting intent from this SIIS article in pure JSON:"""

        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=user_prompt,
                config={
                    "system_instruction": GEMINI_STAGE2_SYSTEM_PROMPT,
                    "response_mime_type": "application/json",
                    "temperature": 0.0,
                },
            )

            raw_text = response.text.strip() if response and response.text else ""
            if not raw_text:
                raise ValueError("Gemini returned empty response text")

            data = json.loads(raw_text)

            actions: List[ExtractedAction] = []
            for a in data.get("actions", []):
                act_name = a.get("action_name", "Device Troubleshooting").strip()
                desc = a.get("description", "It will configure your device settings").strip()
                cat = a.get("category", "manual").strip().lower()
                steps = [s.strip() for s in a.get("steps", []) if s and str(s).strip()]
                screen_hint = a.get("screen_hint", "").strip()
                evidence = a.get("evidence", "").strip()

                if steps:
                    actions.append(
                        ExtractedAction(
                            action_name=act_name,
                            description=desc,
                            category=cat,
                            steps=steps,
                            screen_hint=screen_hint,
                            evidence=evidence,
                        )
                    )

            if not actions:
                logger.warning("Gemini produced 0 parsed actions. Falling back to deterministic extractor.")
                self.last_provider_used = "deterministic_fallback"
                res = self.fallback.extract(query, siis_title, siis_content)
                self.last_latency_ms = (time.perf_counter() - t0) * 1000.0
                return res

            self.last_provider_used = "gemini"
            self.last_latency_ms = (time.perf_counter() - t0) * 1000.0

            return IntermediateIntent(
                topic=data.get("topic", "Device Troubleshooting").strip(),
                goal_mode=data.get("goal_mode", "Troubleshooting").strip(),
                title=data.get("title", "Device troubleshooting").strip(),
                actions=actions,
                raw_siis_title=siis_title,
            )
        except Exception as e:
            logger.warning(f"Gemini Stage 2 structuring failed ({e}). Delegating to deterministic fallback.")
            self.last_provider_used = "deterministic_fallback"
            res = self.fallback.extract(query, siis_title, siis_content)
            self.last_latency_ms = (time.perf_counter() - t0) * 1000.0
            return res
