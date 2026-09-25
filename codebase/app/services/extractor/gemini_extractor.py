"""Gemini API Extractor for Cold-Path Language Reasoning.

Guarantees:
1. Provider abstraction: Uses Google Gemini API when configured.
2. Graceful fallback: Automatically delegates to DeterministicFallbackExtractor
   if API key is missing, network is unavailable, or call fails.
3. Strict intermediate output: Model produces IntermediateIntent JSON, NEVER URIs
   or final ContextDeeplinkResponse.
4. Grounded in SIIS: Injects SIIS text as the sole source of truth.
"""
import json
import logging
import os
from typing import Optional

from app.services.extractor.base import ExtractedAction, ILLMProvider, IntermediateIntent
from app.services.extractor.deterministic_extractor import DeterministicFallbackExtractor

logger = logging.getLogger(__name__)

GEMINI_SYSTEM_PROMPT = """You are a specialized Samsung support triage engine.
Your task is to extract structured troubleshooting actions exclusively from the provided SIIS (Samsung Internal Knowledge Store) article.

CRITICAL RULES:
1. SIIS text is your ONLY source of truth. Do NOT invent troubleshooting steps or settings not present in the article.
2. Deconstruct the troubleshooting procedure into 1 to 3 distinct screen-specific actions.
3. For each action, classify category as:
   - "auto": for settings that can be configured/toggled in Samsung Settings.
   - "manual": for physical inspection, hardware checks, or service center visits.
   - "critical": for destructive operations like factory reset or forced reboot.
4. Action description MUST be 5 to 7 words and start with "It will".
5. Goal title MUST be 2 to 3 words.
6. Return pure JSON matching this schema:
{
  "topic": "Short Topic Name",
  "goal_mode": "Troubleshooting" or "Configuration",
  "title": "2-3 words title",
  "actions": [
    {
      "action_name": "Title Case Action Name",
      "description": "It will ... (5-7 words)",
      "category": "auto" | "manual" | "critical",
      "steps": ["Step 1 sentence", "Step 2 sentence"],
      "screen_hint": "Concrete screen name if mentioned",
      "evidence": "Source quote from SIIS"
    }
  ]
}
"""


class GeminiExtractor(ILLMProvider):
    """Google Gemini API intermediate extractor with deterministic fallback."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = "gemini-2.5-flash",
        fallback: Optional[ILLMProvider] = None,
    ):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model_name = os.getenv("GEMINI_MODEL", model_name)
        self.fallback = fallback or DeterministicFallbackExtractor()
        self.client = None

        if self.api_key:
            try:
                from google import genai
                self.client = genai.Client(api_key=self.api_key)
                logger.info(f"GeminiExtractor initialized with model '{self.model_name}'")
            except Exception as e:
                logger.warning(f"Failed to initialize Gemini client ({e}). Using deterministic fallback.")
                self.client = None
        else:
            logger.info("No GEMINI_API_KEY found. Operating in deterministic fallback mode.")

    def extract(self, query: str, siis_title: str, siis_content: str) -> IntermediateIntent:
        """Extract intermediate intent using Gemini or deterministic fallback."""
        if not self.client:
            return self.fallback.extract(query, siis_title, siis_content)

        user_prompt = f"""User Complaint: {query}

SIIS Knowledge Article:
Title: {siis_title}
Content:
{siis_content}

Extract the structured troubleshooting intent from this SIIS article in pure JSON:"""

        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=user_prompt,
                config={
                    "system_instruction": GEMINI_SYSTEM_PROMPT,
                    "response_mime_type": "application/json",
                    "temperature": 0.0,
                },
            )

            raw_text = response.text.strip()
            data = json.loads(raw_text)

            actions = []
            for a in data.get("actions", []):
                actions.append(
                    ExtractedAction(
                        action_name=a.get("action_name", "Device Troubleshooting"),
                        description=a.get("description", "It will configure your device settings"),
                        category=a.get("category", "manual"),
                        steps=a.get("steps", []),
                        screen_hint=a.get("screen_hint", ""),
                        evidence=a.get("evidence", ""),
                    )
                )

            return IntermediateIntent(
                topic=data.get("topic", "Device Troubleshooting"),
                goal_mode=data.get("goal_mode", "Troubleshooting"),
                title=data.get("title", "Device troubleshooting"),
                actions=actions,
                raw_siis_title=siis_title,
            )
        except Exception as e:
            logger.warning(f"Gemini API call failed ({e}). Falling back to deterministic extractor.")
            return self.fallback.extract(query, siis_title, siis_content)
