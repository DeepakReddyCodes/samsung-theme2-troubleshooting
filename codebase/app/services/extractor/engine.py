"""Cold-Path Knowledge Extraction & Generalization Engine.

Coordinates the two-stage troubleshooting workflow:
1. Stage 1: Query Enrichment (normalizes complaint, identifies technical domain and polarity).
2. Stage 2: Intermediate Structuring (via Gemini or Deterministic Fallback).
3. Grounding Verification: Filters candidate steps through GroundingChecker.
4. Deeplink Resolution: Binds exact catalog URIs or concrete grounded dummy_positive.
5. Formatting & Ordering: Enforces 5-7 word descriptions, 2-3 word titles, auto->manual->critical order.
6. Validation Firewall: Strict perimeter validation gate.
7. Cache Writeback: Writes validated response to FastPathSemanticCache.
"""
import logging
from pathlib import Path
import re
import time
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
from app.services.nbe import CandidateEvidence, Hypothesis, NBEDecisionLoop, NBEEngine, NBEResult
from app.services.query_enrichment import EnrichedQuery, QueryEnricher

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
        enricher: Optional[QueryEnricher] = None,
        nbe_engine: Optional[NBEEngine] = None,
    ):
        self.provider = provider or GeminiExtractor(fallback=DeterministicFallbackExtractor())
        self.resolver = resolver or DeeplinkResolver()
        self.firewall = firewall or ValidationFirewall()
        self.cache = cache
        self.grounding_checker = grounding_checker or GroundingChecker()
        self.enricher = enricher or QueryEnricher()
        self.nbe_engine = nbe_engine or NBEEngine()
        self.last_provider_used = "deterministic"
        self.last_stage1_provider = "deterministic"
        self.last_stage2_provider = "deterministic"
        self.last_latency_ms = 0.0
        self.last_grounding_audit: List[Any] = []
        self.last_nbe_result: Optional[NBEResult] = None

    def _normalize_siis_payload(
        self,
        siis_response: Optional[Union[Dict[str, Any], str]],
    ) -> Tuple[str, str]:
        """Normalize SIIS input into clean (title, content) tuple."""
        if not siis_response:
            return "General Device Support", ""

        if isinstance(siis_response, dict):
            title = str(siis_response.get("title", "")).strip() or "Device Support"
            content = str(siis_response.get("content", "")).strip()
            # Clean prompt injection from title
            title = re.sub(r"ignore\s+(?:all\s+)?(?:previous\s+)?instructions.*$", "", title, flags=re.IGNORECASE).strip()
            return title or "Device Support", content

        if isinstance(siis_response, str):
            content = siis_response.strip()
            # If the string contains markdown headers, use header as title
            header_match = re.search(r"^#+\s*(.+)$", content, re.MULTILINE)
            if header_match:
                title = header_match.group(1).strip()
            else:
                first_line = content.split("\n")[0].strip()
                if len(first_line.split()) <= 6:
                    title = first_line
                else:
                    title = "Device Troubleshooting"
            title = re.sub(r"ignore\s+(?:all\s+)?(?:previous\s+)?instructions.*$", "", title, flags=re.IGNORECASE).strip()
            return title or "Device Troubleshooting", content

        return "Device Support", str(siis_response)

    def extract_and_build(
        self,
        query: str,
        siis_response: Optional[Union[Dict[str, Any], str]] = None,
        scenario_id: Optional[str] = None,
    ) -> ContextDeeplinkResponse:
        """Execute full cold-path extraction, grounding verification, and validation."""
        t0 = time.perf_counter()
        siis_title, siis_content = self._normalize_siis_payload(siis_response)

        # Handle empty/non-actionable SIIS content early
        if not siis_content or not siis_content.strip():
            logger.info("Empty SIIS content provided. Returning safe empty ContextDeeplinkResponse.")
            self.last_provider_used = "deterministic"
            self.last_latency_ms = (time.perf_counter() - t0) * 1000.0
            return ContextDeeplinkResponse(contexts=[])

        # 1. Stage 1: Query Enrichment
        enriched: EnrichedQuery = self.enricher.enrich(
            query=query,
            siis_response={"title": siis_title, "content": siis_content},
        )
        self.last_stage1_provider = getattr(self.enricher, "last_provider_used", "deterministic")

        # 2. Stage 2: Extract intermediate intent via active provider
        intermediate: IntermediateIntent = self.provider.extract(
            query=enriched.normalized_query,
            siis_title=siis_title,
            siis_content=siis_content,
        )
        self.last_stage2_provider = getattr(self.provider, "last_provider_used", "deterministic")
        self.last_provider_used = (
            "gemini"
            if (self.last_stage1_provider == "gemini" or self.last_stage2_provider == "gemini")
            else "deterministic_fallback"
        )

        # Fallback to deterministic extractor if primary provider produced no actions
        if not intermediate.actions and not isinstance(self.provider, DeterministicFallbackExtractor):
            fallback_extractor = DeterministicFallbackExtractor()
            intermediate = fallback_extractor.extract(
                query=enriched.normalized_query,
                siis_title=siis_title,
                siis_content=siis_content,
            )
            self.last_stage2_provider = "deterministic_fallback"

        # If still no structured actions, check for conservative direct sentence extraction
        if not intermediate.actions:
            # Check if SIIS contains any instruction-like sentences
            lines = [l.strip() for l in siis_content.split("\n") if l.strip()]
            valid_steps = []
            for l in lines:
                if any(kw in l.lower() for kw in ["settings", "device", "press", "turn", "tap", "open", "check", "configure", "connect"]):
                    valid_steps.append(l if l.endswith(".") else l + ".")
            if valid_steps:
                topic = siis_title or enriched.domain or "Device Issue"
                intermediate = IntermediateIntent(
                    topic=topic,
                    goal_mode="Troubleshooting",
                    title=rewrite_title(topic),
                    actions=[
                        ExtractedAction(
                            action_name=f"Check {topic} Settings",
                            description=f"It will configure your {topic.lower()} settings",
                            category="manual",
                            steps=valid_steps[:3],
                            screen_hint="Settings",
                            evidence=siis_title,
                        )
                    ],
                    raw_siis_title=siis_title,
                )

        # Invariant: If still no actionable actions extracted from SIIS, return safe empty response
        if not intermediate.actions:
            logger.info("No actionable intermediate actions extracted from SIIS. Returning empty response.")
            return ContextDeeplinkResponse(contexts=[])

        # Evaluate diagnostic evidence sufficiency via NBE
        if len(intermediate.actions) > 1:
            competing_hypotheses = [
                Hypothesis(
                    id=f"H_{i}",
                    name=act.action_name,
                    prior=1.0 / len(intermediate.actions),
                    target_action=act.action_name,
                )
                for i, act in enumerate(intermediate.actions)
            ]
            self.last_nbe_result = self.nbe_engine.evaluate(competing_hypotheses)
        elif len(intermediate.actions) == 1:
            self.last_nbe_result = self.nbe_engine.evaluate([
                Hypothesis(id="H_0", name=intermediate.actions[0].action_name, prior=1.0)
            ])
        else:
            self.last_nbe_result = None

        # 3. Build Goal metadata
        mode = intermediate.goal_mode or "Troubleshooting"
        topic = intermediate.topic or enriched.domain or "Device Issue"
        goal_str = format_goal(topic, mode=mode)
        title_str = rewrite_title(intermediate.title or topic)

        # 4. Grounding & Action Construction
        built_actions: List[Action] = []
        siis_full_text = f"{siis_title}\n{siis_content}"
        self.last_grounding_audit = []

        for ext_act in intermediate.actions:
            # Verify and filter steps through GroundingChecker
            grounded_steps, audit_results = self.grounding_checker.filter_grounded_steps(
                steps=ext_act.steps,
                siis_text=siis_full_text,
            )
            self.last_grounding_audit.extend(audit_results)

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

            # Resolve Deeplinks for all actions
            resolution = self.resolver.resolve_from_step_group(
                action_name=ext_act.action_name,
                steps=grounded_steps,
                screen_hint=ext_act.screen_hint or "",
                category=category.value,
            )

            actionable_dl = resolution.actionable_deeplink
            val_dl = resolution.validation_deeplink

            # Invariant: Every auto action MUST have an actionable deeplink
            if category == actionCategory.auto and not actionable_dl:
                # If auto action cannot be resolved, downgrade or drop
                logger.warning(f"Auto action '{ext_act.action_name}' missing deeplink. Downgrading to manual.")
                category = actionCategory.manual

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

        # Invariant: If no actions survived grounding, return safe empty response!
        # NEVER invent generic troubleshooting steps!
        if not built_actions:
            logger.info("Zero actions survived grounding verification. Returning empty ContextDeeplinkResponse.")
            self.last_latency_ms = (time.perf_counter() - t0) * 1000.0
            return ContextDeeplinkResponse(contexts=[])

        # 5. Sort Actions strictly: auto -> manual -> critical
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

        # 6. Validation Firewall Gatekeeper
        final_response, errors = self.firewall.validate_response(raw_response, allow_repair=True)
        if errors:
            logger.error(f"Firewall errors during cold-path extraction: {errors}")

        # 7. Cache Writeback
        if self.cache and final_response.contexts:
            self.cache.put(
                query=query,
                response=final_response,
                siis_response=siis_response,
                scenario_id=scenario_id,
                validate=False,  # Already validated
            )

        self.last_latency_ms = (time.perf_counter() - t0) * 1000.0
        return final_response

    def evaluate_diagnostic_evidence(
        self,
        hypotheses: List[Hypothesis],
        candidate_evidence: Optional[List[CandidateEvidence]] = None,
        observed_evidence: Optional[Dict[str, str]] = None,
    ) -> NBEResult:
        """Expose explicit Next-Best-Evidence decision engine for diagnostic disambiguation."""
        return self.nbe_engine.evaluate(
            hypotheses=hypotheses,
            candidate_evidence=candidate_evidence,
            observed_evidence=observed_evidence,
        )
