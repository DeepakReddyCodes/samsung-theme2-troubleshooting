"""Comprehensive tests for Phase 1: Schema, Sanitizer, Rewrite Controller, and Firewall.

Ensures strict enforcement of all gates (G4, G5), formatting constraints (A1),
catalog integrity (A2), and negative tests for invalid inputs.
"""
import json
from pathlib import Path
import pytest

from app.core.firewall import ValidationFirewall
from app.core.rewrite_controller import (
    count_words,
    format_goal,
    rewrite_action_description,
    rewrite_title,
    validate_description_format,
    validate_goal_format,
    validate_title_format,
)
from app.core.sanitizer import find_url_leaks, has_url_leaks, is_bixby_uri, sanitize_text
from app.core.schema import (
    Action,
    ContextDeeplinkResponse,
    Deeplink,
    Goal,
    StepGroup,
    ValidationDeepLink,
    actionCategory,
)
import schema as root_schema

CATALOG_PATH = Path(__file__).resolve().parent.parent / "deeplinks.json"
SAMPLE_OUTPUT_PATH = Path(__file__).resolve().parent.parent / "sample_output.json"


@pytest.fixture(scope="module")
def firewall():
    return ValidationFirewall(catalog_path=CATALOG_PATH)


# ============================================================================
# 1. Authoritative Schema Mirroring Tests
# ============================================================================

def test_schema_mirroring():
    """Verify app.core.schema mirrors root workspace schema.py exactly."""
    from app.core import schema as core_schema

    models = [
        "BaseDeeplink",
        "Deeplink",
        "Condition",
        "ResultTypes",
        "actionCategory",
        "ValidationDeepLink",
        "StepGroup",
        "Action",
        "Goal",
        "ContextDeeplinkResponse",
    ]
    for model_name in models:
        root_cls = getattr(root_schema, model_name)
        core_cls = getattr(core_schema, model_name)
        assert root_cls is not None
        assert core_cls is not None
        if hasattr(root_cls, "model_fields"):
            assert set(root_cls.model_fields.keys()) == set(core_cls.model_fields.keys())


# ============================================================================
# 2. Deeplink Catalog Integrity Tests
# ============================================================================

def test_catalog_loaded_integrity(firewall):
    """Verify that all 578 masked catalog URIs and dummy_positive are loaded."""
    assert len(firewall.actionable_uris) >= 578
    assert "bixby://dummy_positive" in firewall.actionable_uris
    assert "bixby://masked/act/b3ed3ed663" in firewall.actionable_uris
    assert "bixby://masked/val/266037d0c5" in firewall.validation_uris
    assert len(firewall.validation_uris) >= 400


# ============================================================================
# 3. Sanitizer & Gate G5 (Zero URL Leaks) Tests
# ============================================================================

def test_legitimate_bixby_uri_not_flagged():
    """Verify legitimate Samsung bixby URIs are NOT flagged as URL leaks."""
    bixby_uri = "bixby://masked/act/b3ed3ed663"
    assert is_bixby_uri(bixby_uri) is True
    assert has_url_leaks(bixby_uri) is False
    assert find_url_leaks(bixby_uri) == []


def test_url_leak_detection():
    """Negative test: verify web URLs, markdown links, and bare domains are caught."""
    bad_texts = [
        "Please visit https://www.samsung.com/support for repair details.",
        "Check out http://samsung.com for warranty info.",
        "Go to www.samsung.com to register.",
        "See [Samsung Repair Services](http://example.com/repair).",
        "Visit samsung.com to learn more about terms.",
    ]
    for bad_text in bad_texts:
        assert has_url_leaks(bad_text) is True, f"Failed to detect leak in: {bad_text}"


def test_url_sanitization():
    """Verify sanitize_text cleanly removes web URLs without destroying text."""
    text = "Visit https://samsung.com/support or contact Samsung Authorized Service Center."
    cleaned = sanitize_text(text)
    assert has_url_leaks(cleaned) is False
    assert "Samsung Authorized Service Center" in cleaned
    assert "https://" not in cleaned


# ============================================================================
# 4. Rewrite Controller Tests (Semantic Preservation, No Invention)
# ============================================================================

def test_goal_formatting():
    """Verify goal regex formatting and validation."""
    valid_goal = "Follow these steps to perform this Screen Damage Troubleshooting"
    assert validate_goal_format(valid_goal) is True

    # Negative test: invalid goal syntax
    invalid_goal = "Repair your broken screen now"
    assert validate_goal_format(invalid_goal) is False

    # Repair without inventing
    repaired = format_goal("Screen Damage", mode="Troubleshooting")
    assert validate_goal_format(repaired) is True
    assert repaired == "Follow these steps to perform this Screen Damage Troubleshooting"


def test_title_word_count():
    """Verify 2 to 3 words title constraint."""
    assert validate_title_format("Screen display damage") is True  # 3 words
    assert validate_title_format("Screen damage") is True  # 2 words

    # Negative tests: 1 word, 4+ words
    assert validate_title_format("Damage") is False
    assert validate_title_format("My galaxy screen display is broken") is False

    # Rewrite loop
    rewritten_1 = rewrite_title("Damage")
    assert validate_title_format(rewritten_1) is True

    rewritten_multi = rewrite_title("My galaxy screen display is broken")
    assert validate_title_format(rewritten_multi) is True


def test_description_format():
    """Verify 5 to 7 words description constraint starting with 'It will'."""
    valid_desc = "It will let you choose navigation type"  # 7 words
    assert validate_description_format(valid_desc) is True

    # Negative tests: missing 'It will', wrong word counts
    assert validate_description_format("Let you choose navigation type") is False
    assert validate_description_format("It will work") is False  # 3 words
    assert validate_description_format("It will facilitate secure data transfer between your multiple Galaxy devices") is False  # 10 words

    # Rewrite loop preserving meaning
    rewritten = rewrite_action_description("facilitate secure data transfer between your devices")
    assert validate_description_format(rewritten) is True
    assert rewritten.startswith("It will ")
    assert 5 <= count_words(rewritten) <= 7


# ============================================================================
# 5. Validation Firewall Negative Tests (Ensuring Violations are Caught)
# ============================================================================

def test_negative_firewall_url_leak_in_step(firewall):
    """Negative test: step containing web URL fails firewall."""
    goal = Goal(
        goal="Follow these steps to perform this Screen Damage Troubleshooting",
        title="Screen display damage",
        score=0.95,
        actions=[
            Action(
                actionName="Schedule Repair",
                description="It will schedule your repair appointment",
                category=actionCategory.manual,
                stepGroups=[
                    StepGroup(
                        steps=[
                            "Visit https://samsung.com/support to book an appointment.",
                        ],
                        actionableDeeplink=None,
                        validationDeeplink=None,
                    )
                ],
            )
        ],
    )
    # Without repair: must detect error
    _, errors = firewall.validate_goal(goal, allow_repair=False)
    assert any("URL leak in step text" in err for err in errors)

    # With repair: scrubs URL and passes
    repaired, rep_errors = firewall.validate_goal(goal, allow_repair=True)
    assert not any("URL leak" in err for err in rep_errors)
    assert has_url_leaks(repaired.actions[0].stepGroups[0].steps[0]) is False


def test_negative_firewall_hallucinated_deeplink(firewall):
    """Negative test: unindexed masked URI is flagged as invalid."""
    goal = Goal(
        goal="Follow these steps to perform this Screen Damage Troubleshooting",
        title="Screen display damage",
        score=0.95,
        actions=[
            Action(
                actionName="Back Up Data",
                description="It will facilitate your data backup",
                category=actionCategory.auto,
                stepGroups=[
                    StepGroup(
                        steps=["Navigate to Settings."],
                        actionableDeeplink=Deeplink(
                            deeplink="bixby://masked/act/fake99999999",  # Hallucinated!
                            description="Fake deeplink description",
                        ),
                    )
                ],
            )
        ],
    )
    _, errors = firewall.validate_goal(goal, allow_repair=False)
    assert any("not in authoritative deeplinks catalog" in err for err in errors)


def test_negative_firewall_auto_action_missing_deeplink(firewall):
    """Negative test: category='auto' without actionableDeeplink fails firewall."""
    goal = Goal(
        goal="Follow these steps to perform this Screen Damage Troubleshooting",
        title="Screen display damage",
        score=0.95,
        actions=[
            Action(
                actionName="Back Up Data",
                description="It will facilitate your data backup",
                category=actionCategory.auto,
                stepGroups=[
                    StepGroup(
                        steps=["Navigate to Settings."],
                        actionableDeeplink=None,  # Missing!
                    )
                ],
            )
        ],
    )
    _, errors = firewall.validate_goal(goal, allow_repair=False)
    assert any("has no actionableDeeplink" in err for err in errors)


def test_negative_firewall_score_out_of_bounds(firewall):
    """Negative test: score outside [0.0, 1.0] fails firewall."""
    goal = Goal(
        goal="Follow these steps to perform this Screen Damage Troubleshooting",
        title="Screen display damage",
        score=1.5,  # Out of range!
        actions=[
            Action(
                actionName="Schedule Repair",
                description="It will schedule your repair appointment",
                category=actionCategory.manual,
                stepGroups=[
                    StepGroup(steps=["Contact service center."])
                ],
            )
        ],
    )
    _, errors = firewall.validate_goal(goal, allow_repair=False)
    assert any("Score must be between 0.0 and 1.0" in err for err in errors)


def test_negative_firewall_inverted_action_categories(firewall):
    """Negative test: critical action placed before auto action is detected."""
    goal = Goal(
        goal="Follow these steps to perform this Screen Damage Troubleshooting",
        title="Screen display damage",
        score=0.9,
        actions=[
            Action(
                actionName="Factory Reset Device",
                description="It will reset device to defaults",
                category=actionCategory.critical,  # Critical first!
                stepGroups=[
                    StepGroup(steps=["Perform factory reset."])
                ],
            ),
            Action(
                actionName="Back Up Data",
                description="It will facilitate your data backup",
                category=actionCategory.auto,
                stepGroups=[
                    StepGroup(
                        steps=["Open backup settings."],
                        actionableDeeplink=Deeplink(
                            deeplink="bixby://masked/act/b3ed3ed663",
                            description="Enables data backup",
                        ),
                    )
                ],
            ),
        ],
    )
    # Without repair: reports error
    _, errors = firewall.validate_goal(goal, allow_repair=False)
    assert any("Actions not ordered correctly" in err for err in errors)

    # With repair: explicitly reorders auto -> manual -> critical
    repaired, rep_errors = firewall.validate_goal(goal, allow_repair=True)
    assert repaired.actions[0].category == actionCategory.auto
    assert repaired.actions[1].category == actionCategory.critical


# ============================================================================
# 6. Reference Sample Output Validation Test
# ============================================================================

def test_sample_output_validation_with_firewall(firewall):
    """Verify sample_output.json passes firewall with repair of word-count drift."""
    with open(SAMPLE_OUTPUT_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Parse through Pydantic model
    contexts_data = data["response"]["contexts"]
    goals = [Goal(**g) for g in contexts_data]
    resp = ContextDeeplinkResponse(contexts=goals)

    # Validate through firewall with repair enabled
    validated_resp, errors = firewall.validate_response(resp, allow_repair=True)
    assert len(errors) == 0, f"Errors in validated sample_output: {errors}"
    assert len(validated_resp.contexts) == 1

    goal = validated_resp.contexts[0]
    assert validate_goal_format(goal.goal)
    assert validate_title_format(goal.title)
    for action in goal.actions:
        assert validate_description_format(action.description)
        if action.category == actionCategory.auto:
            assert action.stepGroups[0].actionableDeeplink is not None
            assert action.stepGroups[0].actionableDeeplink.deeplink in firewall.actionable_uris
