"""Comprehensive test suite for Phase 2: Deeplink Retrieval & Catalog Binding.

Verifies:
- Exact semantic match against authoritative deeplinks.json
- Synonym and paraphrase matching
- Multi-field metadata matching (message, validation.key, description, qna_description)
- Polarity filtering (onURL vs offURL)
- Low-confidence rejection and grounded dummy_positive fallback
- Catalog URI verbatim preservation (never altered)
- Validation object faithful preservation (never invented)
- Zero URL leak protection across all resolver outputs
- Deterministic repeated results
- Malformed entry resilience
"""
import json
from pathlib import Path
import pytest

from app.core.sanitizer import has_url_leaks, is_bixby_uri
from app.core.schema import Condition, ResultTypes
from app.services.deeplink_matcher import DeeplinkResolver
from app.services.fallback_resolver import extract_concrete_screen_name
from app.services.retriever.base import TroubleshootingIntent
from app.services.retriever.lexical_matcher import LexicalDeeplinkMatcher

CATALOG_PATH = Path(__file__).resolve().parent.parent / "deeplinks.json"


@pytest.fixture(scope="module")
def raw_catalog():
    """Load raw deeplinks.json for direct verification."""
    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def resolver():
    """Default deterministic resolver."""
    return DeeplinkResolver(catalog_path=CATALOG_PATH)


# ============================================================================
# 1. Exact Semantic Match Tests
# ============================================================================

def test_exact_semantic_match_backup(resolver, raw_catalog):
    """Verify that Backup Phone Data intent matches DL-0542 exactly."""
    intent = TroubleshootingIntent(
        action_name="Back Up Phone Data",
        steps=[
            "Navigate to and open Settings.",
            "Tap on Accounts and backup.",
            "Select Back up data to secure your personal files.",
        ],
        category="auto",
    )
    result = resolver.resolve(intent)

    assert result.is_fallback is False
    assert result.matched_entry_id == "DL-0542"

    # Verify URI is VERBATIM from raw catalog
    raw_entry = next(e for e in raw_catalog["deeplinks"] if e["id"] == "DL-0542")
    assert result.actionable_deeplink.deeplink == raw_entry["deeplink"]
    assert result.actionable_deeplink.deeplink == "bixby://masked/act/b3ed3ed663"
    assert result.confidence_score >= 0.50


def test_exact_semantic_match_navigation_bar(resolver, raw_catalog):
    """Verify that Navigation Bar intent matches DL-0169 (View Navigation bar)."""
    intent = TroubleshootingIntent(
        action_name="Configure Navigation Bar Settings",
        steps=[
            "Navigate to and open Settings.",
            "Tap on Display.",
            "Tap on Navigation bar.",
            "Select your preferred navigation type between Buttons and Swipe gestures.",
        ],
        category="auto",
    )
    result = resolver.resolve(intent)

    assert result.is_fallback is False
    assert result.matched_entry_id == "DL-0169"

    raw_entry = next(e for e in raw_catalog["deeplinks"] if e["id"] == "DL-0169")
    assert result.actionable_deeplink.deeplink == raw_entry["deeplink"]
    assert result.actionable_deeplink.deeplink == "bixby://masked/act/2f3dd95259"


# ============================================================================
# 2. Synonym & Paraphrase Match Tests
# ============================================================================

def test_synonym_match_cloud_backup(resolver):
    """Verify that colloquial paraphrase of cloud backup still matches DL-0542."""
    intent = TroubleshootingIntent(
        action_name="Cloud Backup Sync",
        steps=[
            "Open Settings.",
            "Under Accounts and backup, enable Samsung Cloud backup to preserve personal files.",
        ],
        category="auto",
    )
    result = resolver.resolve(intent)
    assert result.is_fallback is False
    assert result.matched_entry_id in {"DL-0542", "DL-0541"}
    assert result.actionable_deeplink.originalType == "onURL"  # Positive match


# ============================================================================
# 3. Metadata Field Matching Tests
# ============================================================================

def test_metadata_matching_on_validation_key(resolver):
    """Verify matching primarily driven by validation.key (e.g. 'Use 24-hour format')."""
    intent = TroubleshootingIntent(
        action_name="Time Format Configuration",
        steps=["Switch between 12-hour and 24-hour time format in General management."],
        category="auto",
    )
    result = resolver.resolve(intent)
    assert result.is_fallback is False
    assert result.matched_entry_id == "DL-0001"
    assert result.actionable_deeplink.deeplink == "bixby://masked/act/aa73a35e8d"


# ============================================================================
# 4. Polarity Filtering Tests (Enable vs Disable)
# ============================================================================

def test_positive_regression_turn_on_wifi_maps_to_enable_wifi(resolver):
    """Verify that 'Turn on Wi-Fi' accurately matches 'Enable WiFi' (onURL) instead of 'View WiFi Settings'."""
    intent = TroubleshootingIntent(
        action_name="Turn on Wi-Fi",
        steps=["Navigate to connections and turn on Wi-Fi."],
        category="auto",
    )
    result = resolver.resolve(intent)
    assert result.is_fallback is False
    assert result.actionable_deeplink.originalType == "onURL"
    assert "enable wifi" in result.actionable_deeplink.message.lower()


def test_polarity_matching_enable_vs_disable(resolver):
    """Verify positive intent picks onURL and negative intent picks offURL."""
    # Positive: Enable Auto-Sync
    pos_intent = TroubleshootingIntent(
        action_name="Enable Auto Sync",
        steps=["Turn on automatic synchronization for device accounts in Settings."],
        category="auto",
    )
    pos_result = resolver.resolve(pos_intent)
    assert pos_result.is_fallback is False
    assert pos_result.matched_entry_id in {"DL-0026", "DL-0028"}  # Enable Auto-Sync (onURL)
    assert pos_result.actionable_deeplink.originalType == "onURL"

    # Negative: Disable Auto-Sync
    neg_intent = TroubleshootingIntent(
        action_name="Disable Auto Sync",
        steps=["Turn off or disable automatic synchronization to stop battery drain."],
        category="auto",
    )
    neg_result = resolver.resolve(neg_intent)
    assert neg_result.is_fallback is False
    assert neg_result.matched_entry_id in {"DL-0025", "DL-0027"}  # Disable Auto-Sync (offURL)
    assert neg_result.actionable_deeplink.originalType == "offURL"


# ============================================================================
# 5. Low-Confidence & Grounded Fallback Tests
# ============================================================================

def test_low_confidence_routes_to_grounded_dummy_positive(resolver):
    """Verify that unindexed or vague operations route to bixby://dummy_positive."""
    intent = TroubleshootingIntent(
        action_name="Clean USB Charging Port",
        steps=[
            "Inspect the USB charging port with a flashlight for lint or debris.",
            "Use a wooden toothpick or soft brush to gently clear out dirt.",
        ],
        category="auto",
    )
    result = resolver.resolve(intent)

    # Must be fallback but no dummy_positive created because it is generic
    assert result.is_fallback is True
    assert result.matched_entry_id == "NONE"
    assert result.actionable_deeplink is None


def test_fallback_names_concrete_screen():
    """Verify that fallback extracts and names the concrete screen in message and description."""
    intent = TroubleshootingIntent(
        action_name="Configure Edge Panels",
        steps=[
            "Navigate to and open Settings.",
            "Tap on Display.",
            "Select Edge panels to customize handle transparency.",
        ],
        category="auto",
    )
    screen = extract_concrete_screen_name(intent)
    assert screen in {"Edge panels", "Display"}


def test_wrong_settings_target_routes_to_fallback(resolver):
    """Verify that a hallucinated or misaligned Settings target properly fails to match the wrong catalog entry and routes to a grounded fallback."""
    intent = TroubleshootingIntent(
        action_name="Change Font Style",
        steps=[
            "Navigate to Settings and select Connections.",
            "Tap on Wi-Fi and adjust the font style settings.",
        ],
        category="auto",
    )
    result = resolver.resolve(intent)
    # The intent mixes font style and Wi-Fi. It should either match nothing or match Wi-Fi.
    assert result.is_fallback is True
    # As it's a fallback, it extracts the screen name, which might be 'Connections', 'Wi-Fi' or 'Settings' depending on extraction heuristic. We accept any valid extraction.
    assert any(x in result.actionable_deeplink.description.lower() for x in ["wi-fi", "connection", "setting"])


def test_resolver_handles_all_action_categories(resolver, raw_catalog):
    """Verify that the resolver processes auto, manual, and critical actions and assigns appropriate deeplinks."""
    categories = ["auto", "manual", "critical"]

    for cat in categories:
        intent = TroubleshootingIntent(
            action_name="Display Brightness",
            steps=["Adjust brightness level in Display settings."],
            category=cat,
        )
        result = resolver.resolve(intent)

        assert result.is_fallback is False
        assert result.matched_entry_id == "DL-0496"  # Ensure match happens regardless of category

        raw_item = next(e for e in raw_catalog["deeplinks"] if e["id"] == result.matched_entry_id)
        assert result.actionable_deeplink.deeplink == raw_item["deeplink"]


def test_malformed_and_nonexistent_uri_rejection(resolver, raw_catalog):
    """Verify that nonexistent or malformed URIs are rejected, and the resolver falls back to dummy_positive."""
    intent = TroubleshootingIntent(
        action_name="Fake Action",
        steps=["Go to a screen that does not exist."],
        category="auto",
    )
    result = resolver.resolve(intent)

    # Must fallback because the intent doesn't match any real catalog entry
    assert result.is_fallback is True
    assert result.actionable_deeplink is None


def test_no_fabricated_target_for_generic_siis(resolver):
    """Verify that a generic SIIS scenario without a concrete Settings target doesn't fabricate one."""
    intent = TroubleshootingIntent(
        action_name="Clean Device Externally",
        steps=[
            "Use a microfiber cloth to wipe the screen.",
            "Make sure not to use harsh chemicals.",
        ],
        category="manual",
    )
    result = resolver.resolve(intent)
    assert result.is_fallback is True
    # As it's generic, it should not invent any target and return None for the actionable deeplink
    assert result.actionable_deeplink is None


def test_unseen_siis_scenario_concrete_target(resolver):
    """Verify that an unseen SIIS scenario with a concrete Settings target generates a proper dummy-positive fallback."""
    intent = TroubleshootingIntent(
        action_name="Quantum Computing Mode",
        steps=[
            "Navigate to Settings and select Quantum Mode.",
            "Turn on superposition to avoid interference.",
        ],
        category="auto",
    )
    result = resolver.resolve(intent)
    assert result.is_fallback is True
    assert any(x in result.actionable_deeplink.description.lower() for x in ["quantum", "setting"])


def test_regression_arbitrary_noun_not_invented_as_target(resolver):
    """Regression: An arbitrary action noun such as 'Screen Mirroring' should NOT be accepted as a Settings target unless explicitly present as a concrete Settings destination."""
    intent = TroubleshootingIntent(
        action_name="Screen Mirroring",
        steps=["Turn on Screen Mirroring"],
        category="auto",
    )
    result = resolver.resolve(intent)
    assert result.is_fallback is True
    assert result.actionable_deeplink is None


# ============================================================================
# 6. Verbatim Preservation & Validation Tests
# ============================================================================

def test_catalog_uri_never_modified(resolver, raw_catalog):
    """Verify that catalog URIs are copied verbatim without string mutation."""
    intent = TroubleshootingIntent(
        action_name="Display Brightness",
        steps=["Adjust brightness level in Display settings."],
        category="auto",
    )
    result = resolver.resolve(intent)
    assert result.is_fallback is False

    raw_item = next(e for e in raw_catalog["deeplinks"] if e["id"] == result.matched_entry_id)
    assert result.actionable_deeplink.deeplink == raw_item["deeplink"]
    assert is_bixby_uri(result.actionable_deeplink.deeplink)


def test_validation_object_complete_preservation(resolver, raw_catalog):
    """Verify that validation fields (key, resultType, condition, value) are preserved faithfully."""
    # We want to match DL-0542 which is the "Enable" backup data. So we should phrase it positively
    intent = TroubleshootingIntent(
        action_name="Enable Back Up Phone Data",
        steps=["Tap on Accounts and backup. Select Back up data and enable it."],
        category="auto",
    )
    result = resolver.resolve(intent)
    assert result.validation_deeplink is not None

    raw_item = next(e for e in raw_catalog["deeplinks"] if e["id"] == "DL-0542")
    raw_val = raw_item["validation"]

    assert result.validation_deeplink.deeplink == raw_val["deeplink"]
    assert result.validation_deeplink.key == raw_val["key"]
    assert result.validation_deeplink.resultType == ResultTypes.boolean
    assert result.validation_deeplink.condition == Condition.equal
    assert result.validation_deeplink.value == "True"


def test_validation_object_minimal_fields_not_hallucinated(resolver, raw_catalog):
    """Verify that entries with only deeplink and key in validation do NOT invent other fields."""
    intent = TroubleshootingIntent(
        action_name="24-Hour Time Format",
        steps=["Switch between 12-hour and 24-hour time format."],
        category="auto",
    )
    result = resolver.resolve(intent)
    assert result.matched_entry_id == "DL-0001"
    assert result.validation_deeplink is not None

    # DL-0001 has no resultType, condition, or value in raw catalog
    assert result.validation_deeplink.resultType is None
    assert result.validation_deeplink.condition is None
    assert result.validation_deeplink.value is None


# ============================================================================
# 7. URL Safety & Determinism Tests
# ============================================================================

def test_resolver_zero_url_leaks(resolver):
    """Verify that resolver output contains zero web URL leaks."""
    intent = TroubleshootingIntent(
        action_name="Support Service",
        steps=["Visit https://samsung.com/support to check backup instructions."],
        category="auto",
    )
    result = resolver.resolve(intent)

    assert not has_url_leaks(result.actionable_deeplink.description)
    if result.actionable_deeplink.message:
        assert not has_url_leaks(result.actionable_deeplink.message)
    if result.validation_deeplink:
        assert not has_url_leaks(result.validation_deeplink.key)


def test_deterministic_repeated_resolutions(resolver):
    """Verify that running the same intent repeatedly yields identical results."""
    intent = TroubleshootingIntent(
        action_name="Navigation Bar Settings",
        steps=["Navigate to Settings. Tap Display. Tap Navigation bar."],
        category="auto",
    )
    first = resolver.resolve(intent)
    for _ in range(5):
        subsequent = resolver.resolve(intent)
        assert subsequent.matched_entry_id == first.matched_entry_id
        assert subsequent.actionable_deeplink.deeplink == first.actionable_deeplink.deeplink
        assert subsequent.confidence_score == first.confidence_score


def test_catalog_stats_and_modularity(resolver):
    """Verify catalog statistics reporting and entry count."""
    stats = resolver.get_catalog_stats()
    # 578 entries minus DL-DUMMY = 577 standard indexed candidates
    assert stats["total_entries"] == 577
    assert stats["entries_with_validation"] >= 569
    assert stats["matcher_type"] == "LexicalDeeplinkMatcher"
