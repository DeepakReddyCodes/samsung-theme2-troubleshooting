"""Executable tests for unseen-SIIS generalization."""
import pytest
from app.services.extractor.engine import ColdPathExtractionEngine
from app.api.schemas import TroubleshootRequest, SIISResponseInput


def test_unseen_siis_with_actionable_evidence_produces_grounded_output():
    """Verify the pipeline creates valid output from unseen SIIS content."""
    # This requires running the deterministic extractor at least.
    from app.services.extractor.deterministic_extractor import DeterministicFallbackExtractor
    engine = ColdPathExtractionEngine(provider=DeterministicFallbackExtractor())

    query = "How do I clear the cache on my new app?"
    siis_content = "To clear the cache, go to Settings, tap Apps, select the app, and tap Clear Cache."

    # We expect some actions extracted by the deterministic extractor
    response = engine.extract_and_build(query, siis_content)
    assert response is not None
    # Explicitly check there is a response, and it contains actions
    assert response.contexts is not None
    assert len(response.contexts) > 0
    assert len(response.contexts[0].actions) > 0

    # Check that it's grounded to the SIIS by checking multiple facts
    action = response.contexts[0].actions[0]

    # Must identify the cache-clearing action and the application navigation context
    cache_found = "cache" in action.actionName.lower() or "cache" in action.description.lower() or any("cache" in s.lower() for g in action.stepGroups for s in g.steps)
    apps_found = "apps" in action.actionName.lower() or "apps" in action.description.lower() or any("apps" in s.lower() for g in action.stepGroups for s in g.steps)
    settings_found = "settings" in action.actionName.lower() or "settings" in action.description.lower() or any("settings" in s.lower() for g in action.stepGroups for s in g.steps)

    assert cache_found, "Missing 'cache' fact"
    assert apps_found, "Missing 'apps' fact"
    assert settings_found, "Missing 'settings' fact"

    # Negative grounding check: ensure unsupported facts are explicitly absent
    unsupported_terms = ["usb debugging", "factory reset", "developer options"]
    for term in unsupported_terms:
        assert term not in action.actionName.lower(), f"Unsupported fact '{term}' found in actionName"
        assert term not in action.description.lower(), f"Unsupported fact '{term}' found in description"
        for g in action.stepGroups:
            for s in g.steps:
                assert term not in s.lower(), f"Unsupported fact '{term}' found in step"


def test_unseen_siis_with_no_actionable_evidence_rejects():
    """Verify no facts are invented when SIIS has no actionable evidence."""
    from app.services.extractor.deterministic_extractor import DeterministicFallbackExtractor
    engine = ColdPathExtractionEngine(provider=DeterministicFallbackExtractor())

    query = "How do I fly to the moon?"
    siis_content = "The moon is a natural satellite of Earth."

    response = engine.extract_and_build(query, siis_content)

    # It should not invent actions.
    # Currently the baseline might invent generic fallback actions. We assert it shouldn't.
    assert len(response.contexts) == 0 or len(response.contexts[0].actions) == 0
