"""Cold-Path Knowledge Extraction & Generalization Engine.

Coordinates the full cold-path workflow:
1. Ingests query + SIIS knowledge payload.
2. Calls active provider (Gemini or Deterministic Fallback) for intermediate intent.
3. Filters steps through GroundingChecker to verify grounding against SIIS text.
4. Binds catalog deeplinks using Phase 2 DeeplinkResolver.
5. Shapes and validates formatting with Phase 1 RewriteController.
6. Enforces schema and zero-URL gates with Phase 1 ValidationFirewall.
7. Writes final validated plan into Phase 3 FastPathSemanticCache.
"""
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from app.cache.semantic_cache import FastPathSemanticCache
from app.core.firewall import CATEGORY_PRIORITY, ValidationFirewall
from app.core.rewrite_controller import (
    format_goal,
    rewrite_action_description,
    rewrite_title,
)
from app.core.sanitizer import sanitize_text
from app.core.schema import (
    Action,
    ContextDeeplinkResponse,
    Goal,
    StepGroup,
    actionCategory,
)
from app.services.deeplink_matcher import DeeplinkResolver
from app.services.extractor.base import ExtractedAction, ILLMProvider, IntermediateIntent
from app.services.extractor.deterministic_extractor import DeterministicFallbackExtractor
from app.services.extractor.gemini_extractor import GeminiExtractor
from app.services.extractor.grounding_checker import GroundingChecker

logger = logging.getLogger(__name__)


class ColdPathExtractionEngine:
    """End-to-end knowledge extraction and plan synthesis engine."""

    def __init__(
        self,
        provider: Optional[ILLMProvider] = None,
        resolver: Optional[DeeplinkResolver] = None,
        firewall: Optional[ValidationFirewall] = None,
        cache: Optional[FastPathSemanticCache] = None,
        grounding_checker: Optional[GroundingChecker] = None,
    ):
        self.provider = provider or GeminiExtractor(fallback=DeterministicFallbackExtractor())
        self.resolver = resolver or DeeplinkResolver()
        self.firewall = firewall or ValidationFirewall()
        self.cache = cache
        self.grounding_checker = grounding_checker or GroundingChecker()

    def _normalize_siis_payload(
        self,
        siis_response: Optional[Union[Dict[str, Any], str]],
    ) -> Tuple[str, str]:
        """Normalize SIIS input into clean (title, content) tuple."""
        if not siis_response:
            return "General Device Support", "Check Samsung device settings and restart phone if needed."

        if isinstance(siis_response, dict):
            title = str(siis_response.get("title", "")).strip() or "Device Support"
            content = str(siis_response.get("content", "")).strip() or title
            return title, content

        if isinstance(siis_response, str):
            lines = [l.strip() for l in siis_response.strip().split("\n") if l.strip()]
            title = lines[0] if lines else "Device Support"
            content = siis_response.strip()
            return title, content

        return "Device Support", str(siis_response)

    def extract_and_build(
        self,
        query: str,
        siis_response: Optional[Union[Dict[str, Any], str]] = None,
        scenario_id: Optional[str] = None,
    ) -> ContextDeeplinkResponse:
        """Execute full cold-path extraction, grounding verification, and validation."""
        siis_title, siis_content = self._normalize_siis_payload(siis_response)

        # 1. Extract intermediate intent via active provider
        intermediate: IntermediateIntent = self.provider.extract(
            query=query,
            siis_title=siis_title,
            siis_content=siis_content,
        )

        # 2. Build Goal metadata
        mode = intermediate.goal_mode or "Troubleshooting"
        topic = intermediate.topic or "Device Issue"
        goal_str = format_goal(topic, mode=mode)
        title_str = rewrite_title(intermediate.title or topic)

        # 3. Grounding & Action Construction
        built_actions: List[Action] = []

        for ext_act in intermediate.actions:
            # Verify and filter steps through GroundingChecker
            grounded_steps, audit_results = self.grounding_checker.filter_grounded_steps(
                steps=ext_act.steps,
                siis_text=f"{siis_title}\n{siis_content}",
            )

            # If all steps were rejected, do not include ungrounded action
            if not grounded_steps:
                logger.warning(f"Dropping action '{ext_act.action_name}' due to 0 grounded steps.")
                continue

            # Map category string to enum
            cat_str = (ext_act.category or "manual").lower()
            if "auto" in cat_str:
                category = actionCategory.auto
            elif "critical" in cat_str:
                category = actionCategory.critical
            else:
                category = actionCategory.manual

            # Resolve Deeplinks using Phase 2 DeeplinkResolver
            actionable_dl = None
            val_dl = None

            resolution = self.resolver.resolve_from_step_group(
                action_name=ext_act.action_name,
                steps=grounded_steps,
                screen_hint=ext_act.screen_hint or "",
                category=category.value,
            )
            actionable_dl = resolution.actionable_deeplink
            val_dl = resolution.validation_deeplink

            # Ensure compliant 5-7 word description starting with 'It will'
            desc_str = rewrite_action_description(ext_act.description, ext_act.action_name)

            step_group = StepGroup(
                steps=[sanitize_text(s) for s in grounded_steps],
                actionableDeeplink=actionable_dl,
                validationDeeplink=val_dl,
            )

            built_actions.append(
                Action(
                    actionName=sanitize_text(ext_act.action_name),
                    description=desc_str,
                    category=category,
                    stepGroups=[step_group],
                )
            )

        # If no actions survived grounding, fallback to grounded overview
        if not built_actions:
            fallback_steps, _ = self.grounding_checker.filter_grounded_steps(
                steps=["Navigate to and open device Settings.", f"Check {topic} configuration."],
                siis_text=f"{siis_title}\n{siis_content}",
            )
            if not fallback_steps:
                lines = [l.strip() for l in siis_content.split("\n") if l.strip()]
                first_line = lines[0] if lines else "Check device settings and configurations."
                fallback_steps = [first_line[:100].rstrip(".") + "."]

            built_actions.append(
                Action(
                    actionName=f"Check {topic} Settings",
                    description=f"It will configure your {topic.lower()} settings",
                    category=actionCategory.manual,
                    stepGroups=[
                        StepGroup(
                            steps=[sanitize_text(s) for s in fallback_steps],
                            actionableDeeplink=None,
                            validationDeeplink=None,
                        )
                    ],
                )
            )

        # 4. Sort Actions strictly: auto -> manual -> critical
        built_actions.sort(
            key=lambda a: CATEGORY_PRIORITY.get(a.category or actionCategory.manual, 1)
        )

        goal = Goal(
            goal=goal_str,
            title=title_str,
            actions=built_actions,
            score=0.92,
        )

        raw_response = ContextDeeplinkResponse(contexts=[goal])

        # 5. Validation Firewall Gatekeeper
        final_response, errors = self.firewall.validate_response(raw_response, allow_repair=True)
        if errors:
            logger.error(f"Firewall errors during cold-path extraction: {errors}")

        # 6. Cache Writeback
        if self.cache:
            self.cache.put(
                query=query,
                response=final_response,
                siis_response=siis_response,
                scenario_id=scenario_id,
                validate=False,  # Already validated
            )

        return final_response
