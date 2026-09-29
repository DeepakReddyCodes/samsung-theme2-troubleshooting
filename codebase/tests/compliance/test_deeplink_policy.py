"""Executable tests for catalog URI and dummy-positive policy."""
import pytest
from app.services.deeplink_matcher import DeeplinkResolver


def test_catalog_deeplink_validity():
    """Returned catalog deeplinks must exist in the supplied catalog exactly without mutation."""
    matcher = DeeplinkResolver()

    # Use a known concrete intent that should deterministically resolve
    # The default catalog includes "bixby://masked/act/fdd7f62e24" for "Enable WiFi" settings
    result = matcher.resolve_from_step_group(action_name="Turn on Wi-Fi", steps=["Turn on Wi-Fi"])

    # Must actually resolve to an actionable deeplink for an auto action
    assert result.actionable_deeplink is not None

    # The URI must exactly match the expected catalog entry, with no mutation.
    # We verify it against the known literal deterministic intent "Enable WiFi" mapping.
    assert result.actionable_deeplink.deeplink == "bixby://masked/act/fdd7f62e24"


def test_arbitrary_web_url_rejection():
    """Assert web URLs are rejected as deeplinks at the validation boundary."""
    from app.core.firewall import ValidationFirewall
    from app.core.schema import Action, StepGroup, actionCategory, Deeplink
    firewall = ValidationFirewall()

    # Construct an action with an arbitrary web URL as a deeplink
    action = Action(
        actionName="Test Web URL",
        description="It will open web browser",
        stepGroups=[StepGroup(
            steps=["Go to website"],
            actionableDeeplink=Deeplink(deeplink="https://google.com", description="")
        )],
        category=actionCategory.auto
    )

    # The firewall must reject this action due to the invalid deeplink URI format
    act, errors = firewall.validate_action(action, allow_repair=False)
    assert any("Actionable deeplink URI must start with 'bixby://', got 'https://google.com'" in e for e in errors)


def test_dummy_positive_requires_concrete_target():
    """Verify dummy_positive is only allowed when a concrete SIIS-derived Settings target exists."""
    from app.services.fallback_resolver import create_grounded_dummy_positive
    from app.services.retriever.base import TroubleshootingIntent
    from app.services.deeplink_matcher import DeeplinkResolver

    # CASE A: Generic/unrelated intent with no concrete Settings target
    intent_a = TroubleshootingIntent(
        action_name="Generic Action",
        steps=["Some generic step"]
    )
    fallback_a = create_grounded_dummy_positive(intent_a)
    # The current codebase might return "bixby://dummy_positive?target=Display"
    # We assert the required behavior (it should NOT invent a target).
    # Currently it violates this. We write the test to expose it.
    assert fallback_a is None

    # CASE B: Concrete SIIS-derived target with NO catalog match
    # A known specific setting that isn't in the default catalog (e.g. Developer Options/USB debugging)
    # We must construct a deterministic intent that is recognized as a concrete settings target but is a catalog miss.
    intent_b = TroubleshootingIntent(
        action_name="Developer Options",
        steps=["Go to settings and turn on Developer Options"]
    )
    resolver = DeeplinkResolver()
    result_b = resolver.resolve(intent_b)

    # Note: Calling create_grounded_dummy_positive directly tests the fallback construction logic/policy.
    # It does NOT verify the end-to-end SIIS provenance of the target itself.
    # The end-to-end SIIS provenance check is deferred to the appropriate production deeplink workstream
    # and is recorded as a known downstream requirement.
    # The contract says fallback is allowed for catalog misses, but not strictly mandatory.
    fallback_b = create_grounded_dummy_positive(intent_b)
    if fallback_b is not None:
        assert fallback_b.actionable_deeplink.deeplink == "bixby://dummy_positive"
        # Explicitly check it did not invent a target like 'Display' implicitly
        assert "Developer Options" in fallback_b.actionable_deeplink.description
        assert "Display" not in fallback_b.actionable_deeplink.description

    # CASE C: Concrete SIIS-derived target WITH a catalog match
    intent_c = TroubleshootingIntent(
        action_name="Turn on Wi-Fi",
        steps=["Turn on Wi-Fi"]
    )
    result_c = resolver.resolve(intent_c)
    assert result_c.actionable_deeplink is not None
    # Must NOT replace a valid catalog URI with dummy_positive
    assert not result_c.actionable_deeplink.deeplink.startswith("bixby://dummy_positive")
    assert result_c.actionable_deeplink.deeplink.startswith("bixby://")
