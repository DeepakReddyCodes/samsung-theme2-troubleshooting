"""Comprehensive test suite for Phase 4: Cold-Path Knowledge Extractor & Generalization Engine.

Verifies:
1. All 20 canonical SIIS scenarios extract into schema-compliant plans
2. SIIS with different wording
3. Unseen troubleshooting scenario
4. Unseen configuration scenario
5. Multiple-step SIIS article
6. Short SIIS article
7. Ambiguous SIIS article
8. Unsupported/invented-step rejection
9. Deeplink resolver integration
10. Auto-action deeplink enforcement
11. Validation object preservation
12. Zero URL leak prevention
13. Deterministic fallback when Gemini is unavailable
14. Malformed LLM output recovery
15. Final response schema validation
16. Grounding verification audit trail
"""
import json
from pathlib import Path
import pytest

from app.core.firewall import ValidationFirewall
from app.core.sanitizer import has_url_leaks
from app.core.schema import ContextDeeplinkResponse, actionCategory
from app.services.deeplink_matcher import DeeplinkResolver
from app.services.extractor.base import ExtractedAction, ILLMProvider, IntermediateIntent
from app.services.extractor.deterministic_extractor import DeterministicFallbackExtractor
from app.services.extractor.engine import ColdPathExtractionEngine
from app.services.extractor.gemini_extractor import GeminiExtractor
from app.services.extractor.grounding_checker import GroundingChecker

SIIS_PATH = Path(__file__).resolve().parent.parent / "siis_responses.json"
CATALOG_PATH = Path(__file__).resolve().parent.parent / "deeplinks.json"


@pytest.fixture(scope="module")
def siis_data():
    with open(SIIS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def engine():
    resolver = DeeplinkResolver(catalog_path=CATALOG_PATH)
    firewall = ValidationFirewall(catalog_path=CATALOG_PATH)
    fallback = DeterministicFallbackExtractor()
    provider = GeminiExtractor(api_key=None, fallback=fallback)
    return ColdPathExtractionEngine(
        provider=provider,
        resolver=resolver,
        firewall=firewall,
    )


# ============================================================================
# 1. All 20 Canonical Scenarios
# ============================================================================

def test_all_20_canonical_siis_scenarios_extraction(engine, siis_data):
    """Verify that all 20 canonical SIIS articles produce valid ContextDeeplinkResponses."""
    firewall = engine.firewall
    for sc in siis_data["responses"]:
        query = sc["original_query"]
        siis_resp = sc["siis_response"]
        sc_id = sc["id"]

        plan = engine.extract_and_build(query=query, siis_response=siis_resp, scenario_id=sc_id)
        assert isinstance(plan, ContextDeeplinkResponse)

        # Since actions without valid deeplinks are dropped, if no actions survive
        # the plan will have 0 contexts. Otherwise, exactly 1 context.
        assert len(plan.contexts) in [0, 1]

        if len(plan.contexts) == 1:
            goal = plan.contexts[0]
            # Validate through firewall
            _, errors = firewall.validate_response(plan, allow_repair=False)
            assert len(errors) == 0, f"Validation errors on {sc_id}: {errors}"
            assert len(goal.actions) >= 1


# ============================================================================
# 2. SIIS with Different Wording & Paraphrases
# ============================================================================

def test_siis_with_different_wording(engine):
    """Verify extraction when SIIS article uses alternative phrasing."""
    query = "Why does my Galaxy screen rotate upside down?"
    siis_payload = {
        "title": "Orientation and display rotation on Samsung Galaxy devices",
        "content": (
            "## Step 1: Open the Quick Panel\n"
            "Swipe downwards from the upper portion of the display to access the Quick settings.\n"
            "## Step 2: Toggle Orientation Lock\n"
            "Tap on the Auto rotate or Portrait icon to toggle the screen orientation lock."
        ),
    }
    plan = engine.extract_and_build(query=query, siis_response=siis_payload)
    assert len(plan.contexts) == 1
    goal = plan.contexts[0]
    assert "Rotation" in goal.goal or "Orientation" in goal.goal or "Troubleshooting" in goal.goal
    assert len(goal.actions) >= 1


# ============================================================================
# 3. Unseen Troubleshooting & Configuration Scenarios
# ============================================================================

def test_unseen_troubleshooting_scenario(engine):
    """Verify cold-path extraction for an unseen Bluetooth troubleshooting scenario."""
    query = "My Galaxy Buds keep disconnecting during phone calls."
    siis_payload = {
        "title": "Bluetooth audio accessory disconnects during calls",
        "content": (
            "## Step 1: Unpair and Reconnect Bluetooth Device\n"
            "Go to Settings, tap Connections, and select Bluetooth.\n"
            "Locate your paired earbuds, tap the gear icon, and select Unpair.\n"
            "## Step 2: Reset Network Configuration\n"
            "Navigate to Settings, tap General management, tap Reset, and select Reset network settings."
        ),
    }
    plan = engine.extract_and_build(query=query, siis_response=siis_payload)
    goal = plan.contexts[0]
    assert goal.goal.endswith("Troubleshooting")
    assert any(a.category == actionCategory.auto for a in goal.actions)


def test_unseen_configuration_scenario(engine):
    """Verify cold-path extraction for an unseen Configuration scenario."""
    query = "How do I set up Always On Display clock styles?"
    siis_payload = {
        "title": "How to configure Always On Display clock on your Galaxy device",
        "content": (
            "## Step 1: Access Lock Screen Settings\n"
            "Navigate to and open Settings, then tap Lock screen and AOD.\n"
            "## Step 2: Select Clock Style\n"
            "Tap on Always On Display and select your preferred clock style and color."
        ),
    }
    plan = engine.extract_and_build(query=query, siis_response=siis_payload)
    goal = plan.contexts[0]
    assert goal.goal.endswith("Configuration")


# ============================================================================
# 4. Multi-Step, Short, and Ambiguous Articles
# ============================================================================

def test_multiple_step_siis_article(engine):
    """Verify handling of complex 4-step article with sorted action categories."""
    query = "Device is completely frozen and lagging."
    siis_payload = {
        "title": "Resolving severe freezing on Samsung phone",
        "content": (
            "## Step 1: Optimize Device Care\n"
            "Go to Settings, tap Device care, and tap Optimize now.\n"
            "## Step 2: Inspect Hardware and Clean Port\n"
            "Inspect the USB port with a flashlight for debris and clean gently.\n"
            "## Step 3: Force Device System Restart\n"
            "Press and hold Power and Volume down buttons for 20 seconds to force restart."
        ),
    }
    plan = engine.extract_and_build(query=query, siis_response=siis_payload)
    actions = plan.contexts[0].actions

    # Verify action category ordering: auto -> manual -> critical
    categories = [a.category for a in actions]
    assert categories == sorted(categories, key=lambda c: 0 if c == actionCategory.auto else (1 if c == actionCategory.manual else 2))


def test_short_siis_article(engine):
    """Verify handling of short 2-sentence article without markdown headers."""
    query = "Battery draining fast."
    siis_payload = {
        "title": "Battery Life Optimization",
        "content": "Navigate to Settings, tap Battery, and enable Power saving mode to extend your battery.",
    }
    plan = engine.extract_and_build(query=query, siis_response=siis_payload)
    assert len(plan.contexts) == 1
    assert len(plan.contexts[0].actions) >= 1


def test_ambiguous_siis_article(engine):
    """Verify handling of narrative conversational article."""
    query = "I'm having general audio difficulties."
    siis_payload = {
        "title": "Audio and Sound Clarity",
        "content": "Sometimes your speakers can experience muffled audio. Make sure cases do not cover speakers.",
    }
    plan = engine.extract_and_build(query=query, siis_response=siis_payload)
    assert len(plan.contexts) == 1


# ============================================================================
# 5. Grounding Verification & Unsupported Step Rejection
# ============================================================================

def test_unsupported_invented_step_rejection():
    """Verify GroundingChecker rejects steps invented by models not in SIIS."""
    checker = GroundingChecker(threshold=0.50)
    siis_text = "To fix email, check your Wi-Fi connection in Settings. Also remove and re-add your email account."

    # Grounded step
    grounded_step = "Check your Wi-Fi connection in Settings."
    res_grounded = checker.check_step(grounded_step, siis_text)
    assert res_grounded.is_grounded is True
    assert res_grounded.grounding_score >= 0.50

    # Invented step
    invented_step = "Download CleanMaster antivirus app from Google Play Store to scan malware."
    res_invented = checker.check_step(invented_step, siis_text)
    assert res_invented.is_grounded is False
    assert res_invented.grounding_score < 0.30


def test_grounding_verification_audit_trail():
    """Verify GroundingChecker returns audit trail with supported tokens and snippets."""
    checker = GroundingChecker()
    siis_text = "Connect a USB mouse to the phone using an OTG adapter to navigate the screen."
    step = "Connect a USB mouse using an adapter."

    res = checker.check_step(step, siis_text)
    assert res.is_grounded is True
    assert len(res.supported_tokens) >= 3
    assert "mouse" in res.supported_tokens
    assert len(res.evidence_snippet) > 0


# ============================================================================
# 6. Deeplink & Validation Enforcement
# ============================================================================

def test_auto_action_deeplink_enforcement(engine):
    """Verify auto actions with concrete targets receive non-null actionableDeeplinks."""
    query = "Backup phone files."
    siis_payload = {
        "title": "Backing up personal data",
        "content": "Navigate to Settings, tap Accounts and backup, and select Back up data to secure your files.",
    }
    plan = engine.extract_and_build(query=query, siis_response=siis_payload)
    for action in plan.contexts[0].actions:
        if action.category == actionCategory.auto:
            assert action.stepGroups[0].actionableDeeplink is not None
            assert action.stepGroups[0].actionableDeeplink.deeplink.startswith("bixby://")

def test_auto_action_without_concrete_target_receives_none_deeplink(engine):
    """Verify actions without concrete targets are dropped, resulting in an empty response (no hallucinated deeplinks)."""
    query = "What is screen mirroring?"
    siis_payload = {
        "title": "Screen Mirroring explained",
        "content": "Screen mirroring lets you mirror your phone's screen to a bigger screen, like a Smart TV. Navigate to and open device Settings.",
    }
    plan = engine.extract_and_build(query=query, siis_response=siis_payload)
    # The engine drops actions with missing deeplinks. Since all actions get dropped,
    # the engine returns an empty ContextDeeplinkResponse.
    assert len(plan.contexts) == 0


def test_validation_object_preservation_in_extracted_plan(engine):
    """Verify validation object is attached when matching catalog entry has validation."""
    query = "Backup phone files."
    siis_payload = {
        "title": "Backing up personal data",
        "content": "Navigate to Settings, tap Accounts and backup, and select Back up data to Samsung Cloud.",
    }
    plan = engine.extract_and_build(query=query, siis_response=siis_payload)
    auto_act = next(a for a in plan.contexts[0].actions if a.category == actionCategory.auto)
    step_group = auto_act.stepGroups[0]
    # DL-0542 has validation deeplink
    if step_group.actionableDeeplink.deeplink == "bixby://masked/act/b3ed3ed663":
        assert step_group.validationDeeplink is not None
        assert step_group.validationDeeplink.deeplink == "bixby://masked/val/266037d0c5"


# ============================================================================
# 7. URL Safety & Fallback Recovery
# ============================================================================

def test_url_leak_prevention_on_extracted_plans(engine):
    """Verify extraneous web URLs in SIIS content are strictly stripped (Gate G5)."""
    query = "Screen is broken."
    siis_payload = {
        "title": "Service Options for Screens",
        "content": (
            "Visit https://samsung.com/support for repair details. "
            "See [Samsung Repair](http://repair.samsung.com/schedule) to book. "
            "Go to www.samsung.com to check warranty."
        ),
    }
    plan = engine.extract_and_build(query=query, siis_response=siis_payload)
    goal = plan.contexts[0]
    for action in goal.actions:
        assert not has_url_leaks(action.actionName)
        assert not has_url_leaks(action.description)
        for sg in action.stepGroups:
            for s in sg.steps:
                assert not has_url_leaks(s)


def test_deterministic_fallback_when_gemini_unavailable():
    """Verify system operates seamlessly when GEMINI_API_KEY is not set."""
    fallback = DeterministicFallbackExtractor()
    provider = GeminiExtractor(api_key=None, fallback=fallback)
    res = provider.extract("query", "Title", "## Step 1\nNavigate to Settings.")
    assert isinstance(res, IntermediateIntent)
    assert len(res.actions) >= 1


def test_malformed_llm_output_recovery(engine):
    """Verify engine recovers gracefully if intermediate provider produces empty actions by returning empty response per W02 invariant."""
    class BrokenProvider(ILLMProvider):
        def extract(self, query: str, siis_title: str, siis_content: str) -> IntermediateIntent:
            return IntermediateIntent(topic="Error", goal_mode="Troubleshooting", title="Error", actions=[])

    broken_engine = ColdPathExtractionEngine(
        provider=BrokenProvider(),
        resolver=engine.resolver,
        firewall=engine.firewall,
    )
    plan = broken_engine.extract_and_build(
        query="query",
        siis_response={"title": "Some Title", "content": "Some content about device settings."},
    )
    assert isinstance(plan, ContextDeeplinkResponse)
    assert len(plan.contexts) == 0


def test_final_response_schema_validation(engine):
    """Verify extracted plan serializes and conforms strictly to ContextDeeplinkResponse."""
    query = "My screen flickers"
    siis_payload = {
        "title": "Screen Flickering Guide",
        "content": "## Step 1\nNavigate to Settings and adjust Display brightness."
    }
    plan = engine.extract_and_build(query=query, siis_response=siis_payload)
    data = plan.model_dump()
    assert "contexts" in data
    assert isinstance(data["contexts"], list)
    recreated = ContextDeeplinkResponse(**data)
    assert recreated == plan


def test_unsupported_steps_filter_in_action(engine):
    """Verify that an action with mixed grounded and ungrounded steps has ungrounded steps dropped."""
    class MixedProvider(ILLMProvider):
        def extract(self, query: str, siis_title: str, siis_content: str) -> IntermediateIntent:
            return IntermediateIntent(
                topic="Display Flicker",
                goal_mode="Troubleshooting",
                title="Display flicker settings",
                actions=[
                    ExtractedAction(
                        action_name="Adjust Brightness",
                        description="It will adjust your display brightness",
                        category="auto",
                        steps=[
                            "Navigate to Settings and tap on Display.",  # Grounded
                            "Download unauthorized third-party cleaner tool from dubious web forum.",  # Ungrounded!
                        ],
                        screen_hint="Display",
                        evidence="Step 1",
                    )
                ],
            )

    mixed_engine = ColdPathExtractionEngine(
        provider=MixedProvider(),
        resolver=engine.resolver,
        firewall=engine.firewall,
    )
    plan = mixed_engine.extract_and_build(
        query="Display flickers",
        siis_response={"title": "Display Guide", "content": "Navigate to Settings and tap on Display."},
    )
    steps = plan.contexts[0].actions[0].stepGroups[0].steps
    assert len(steps) == 1
    assert "dubious" not in steps[0]
    assert "Navigate to Settings and tap on Display" in steps[0]
