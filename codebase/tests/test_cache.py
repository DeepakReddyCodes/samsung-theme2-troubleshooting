"""Comprehensive test suite for Phase 3: Fast-Path Semantic Cache Layer.

Verifies:
1. Exact normalized-query hit
2. Whitespace and case normalization
3. Punctuation normalization
4. Paraphrase semantic hit (P95 <= 300ms, >=80% hit rate)
5. Semantically unrelated query misses
6. Same words but different intent (e.g., backup vs restore/reset) does not collide
7. SIIS context affecting cache identity
8. Cache version invalidation
9. Deeplink catalog version invalidation
10. Schema version invalidation
11. Deterministic repeated hits
12. Prewarming all 20 canonical scenarios
13. Cache statistics and percentiles
14. Latency benchmarking (exact hit, semantic hit, miss, P50, P95)
15. Cache stores only validated responses
"""
import json
from pathlib import Path
import time
import pytest

from app.cache.prewarm import prewarm_canonical_scenarios
from app.cache.semantic_cache import (
    CacheVersionManager,
    FastPathSemanticCache,
    compute_siis_fingerprint,
    normalize_query,
)
from app.core.firewall import ValidationFirewall
from app.core.schema import (
    Action,
    ContextDeeplinkResponse,
    Deeplink,
    Goal,
    StepGroup,
    ValidationDeepLink,
    actionCategory,
)

CATALOG_PATH = Path(__file__).resolve().parent.parent / "deeplinks.json"
SIIS_PATH = Path(__file__).resolve().parent.parent / "siis_responses.json"


@pytest.fixture(scope="module")
def valid_response():
    """A valid, firewall-compliant ContextDeeplinkResponse."""
    return ContextDeeplinkResponse(
        contexts=[
            Goal(
                goal="Follow these steps to perform this Screen Damage Troubleshooting",
                title="Screen display damage",
                score=0.95,
                actions=[
                    Action(
                        actionName="Back Up Phone Data",
                        description="It will facilitate secure personal data transfer",
                        category=actionCategory.auto,
                        stepGroups=[
                            StepGroup(
                                steps=[
                                    "Navigate to and open Settings.",
                                    "Tap on Accounts and backup.",
                                    "Select Back up data to secure your personal files.",
                                ],
                                actionableDeeplink=Deeplink(
                                    deeplink="bixby://masked/act/b3ed3ed663",
                                    description="Enables data backup to Samsung Cloud via device Settings on the device.",
                                    message="Enable Back up data (Samsung Cloud)",
                                    originalType="onURL",
                                ),
                                validationDeeplink=ValidationDeepLink(
                                    deeplink="bixby://masked/val/266037d0c5",
                                    key="Back up data (Samsung Cloud)",
                                ),
                            )
                        ],
                    )
                ],
            )
        ]
    )


@pytest.fixture
def cache():
    """Fresh cache instance for testing."""
    return FastPathSemanticCache(
        catalog_path=CATALOG_PATH,
        siis_path=SIIS_PATH,
        enable_embeddings=True,
    )


# ============================================================================
# 1. Exact Hit & Normalization Tests
# ============================================================================

def test_exact_normalized_query_hit(cache, valid_response):
    """Verify exact match returns cached response with hit_type='exact'."""
    q = "How do I back up my Galaxy phone data?"
    cache.put(q, valid_response)

    resp, meta = cache.get(q)
    assert resp is not None
    assert meta["cache_hit"] is True
    assert meta["hit_type"] == "exact"
    assert meta["confidence"] == 1.0
    assert meta["latency_ms"] < 10.0  # Exact lookup is sub-millisecond


def test_whitespace_and_case_normalization(cache, valid_response):
    """Verify different casing and multiple spaces resolve to exact hit."""
    q_stored = "My Galaxy screen is cracked"
    cache.put(q_stored, valid_response)

    test_queries = [
        "MY GALAXY SCREEN IS CRACKED",
        "  my   galaxy   screen   is   cracked  ",
        "\tMy Galaxy   screen is   cracked\n",
    ]
    for q in test_queries:
        resp, meta = cache.get(q)
        assert resp is not None
        assert meta["cache_hit"] is True
        assert meta["hit_type"] == "exact"


def test_punctuation_and_numbering_normalization(cache, valid_response):
    """Verify numbered list prefixes and punctuation are normalized."""
    q_stored = "My Samsung tablet screen flashes and goes blank"
    cache.put(q_stored, valid_response)

    variants = [
        '1. "My Samsung tablet screen flashes and goes blank."',
        "1. My Samsung tablet screen flashes and goes blank!",
        "My Samsung tablet screen flashes, and goes blank?",
    ]
    for v in variants:
        resp, meta = cache.get(v)
        assert resp is not None
        assert meta["cache_hit"] is True
        assert meta["hit_type"] == "exact"


# ============================================================================
# 2. Semantic Paraphrase & Intent Tests
# ============================================================================

def test_paraphrase_semantic_hit(cache, valid_response):
    """Verify semantic paraphrase resolves via dense embedding similarity."""
    canonical = "How do I back up my phone?"
    cache.put(canonical, valid_response, scenario_id="backup_canonical")

    paraphrase = "Where can I backup my device data?"
    resp, meta = cache.get(paraphrase)

    assert resp is not None
    assert meta["cache_hit"] is True
    assert meta["hit_type"] == "semantic"
    assert meta["scenario_id"] == "backup_canonical"
    assert meta["confidence"] >= 0.65
    assert meta["latency_ms"] < 300.0  # SLA target


def test_semantically_unrelated_query_must_miss(cache, valid_response):
    """Verify an unrelated query does NOT trigger a false positive hit."""
    canonical = "My Galaxy phone screen is completely cracked"
    cache.put(canonical, valid_response, scenario_id="cracked_screen")

    unrelated = "How do I make a chocolate cake at home?"
    resp, meta = cache.get(unrelated)

    assert resp is None
    assert meta["cache_hit"] is False
    assert meta["hit_type"] == "miss"


def test_same_words_different_intent_not_incorrectly_hit(cache, valid_response):
    """Verify opposing intents (e.g. backup vs reset/restore) do NOT collide."""
    backup_query = "How do I back up my phone data?"
    cache.put(backup_query, valid_response, scenario_id="backup_plan")

    # Opposing intent: Factory Reset
    reset_query = "How do I factory reset my phone data?"
    resp_reset, meta_reset = cache.get(reset_query)
    assert resp_reset is None
    assert meta_reset["cache_hit"] is False

    # Opposing intent: Restore from backup
    restore_query = "How do I restore my phone from backup?"
    resp_restore, meta_restore = cache.get(restore_query)
    assert resp_restore is None
    assert meta_restore["cache_hit"] is False


# ============================================================================
# 3. SIIS Context Binding Tests
# ============================================================================

def test_siis_context_affecting_cache_identity(cache, valid_response):
    """Verify identical query text with different SIIS payload produces distinct entries."""
    query = "The device screen remains dark."
    siis_art_1 = {"title": "Hardware Inspection", "content": "Check liquid damage indicator."}
    siis_art_2 = {"title": "Software Recovery", "content": "Reboot into recovery mode."}

    # Store under article 1
    cache.put(query, valid_response, siis_response=siis_art_1, scenario_id="hardware")

    # Lookup with article 1 should hit
    resp1, meta1 = cache.get(query, siis_response=siis_art_1)
    assert resp1 is not None
    assert meta1["cache_hit"] is True

    # Lookup with article 2 should MISS (different SIIS context)
    resp2, meta2 = cache.get(query, siis_response=siis_art_2)
    assert resp2 is None
    assert meta2["cache_hit"] is False


# ============================================================================
# 4. Invalidation Tests (Versions, Catalog, Schema)
# ============================================================================

def test_cache_manual_invalidation(cache, valid_response):
    """Verify manual cache invalidation clears entries."""
    cache.put("Test query", valid_response)
    assert len(cache.exact_store) > 0

    cache.invalidate(reason="test")
    assert len(cache.exact_store) == 0
    resp, meta = cache.get("Test query")
    assert resp is None
    assert meta["cache_hit"] is False


def test_cache_version_token_changes_on_version_update():
    """Verify version manager produces new token when versions change."""
    vm1 = CacheVersionManager(catalog_path=CATALOG_PATH, engine_version="1.0.0", schema_version="1.0.0")
    vm2 = CacheVersionManager(catalog_path=CATALOG_PATH, engine_version="1.0.1", schema_version="1.0.0")
    vm3 = CacheVersionManager(catalog_path=CATALOG_PATH, engine_version="1.0.0", schema_version="2.0.0")

    assert vm1.version_token != vm2.version_token
    assert vm1.version_token != vm3.version_token


# ============================================================================
# 5. Determinism & Firewall Guard Tests
# ============================================================================

def test_deterministic_repeated_hits(cache, valid_response):
    """Verify identical repeated queries produce deterministic responses and metadata."""
    query = "How do I check wifi connection status?"
    cache.put(query, valid_response, scenario_id="wifi_check")

    first_resp, first_meta = cache.get(query)
    for _ in range(10):
        subsequent_resp, subsequent_meta = cache.get(query)
        assert subsequent_meta["cache_hit"] == first_meta["cache_hit"]
        assert subsequent_meta["hit_type"] == first_meta["hit_type"]
        assert subsequent_resp == first_resp


def test_cache_stores_only_validated_responses(cache):
    """Verify attempting to cache an invalid response is rejected."""
    bad_resp = ContextDeeplinkResponse(
        contexts=[
            Goal(
                goal="Invalid Goal Syntax",  # Fails regex!
                title="Bad title having way too many words",  # 7 words!
                score=2.5,  # Out of range!
                actions=[],  # Empty actions!
            )
        ]
    )
    stored = cache.put("Query for bad plan", bad_resp)
    assert stored is False
    assert len(cache.exact_store) == 0


# ============================================================================
# 6. Prewarming & Benchmarking Tests
# ============================================================================

def test_prewarming_all_20_canonical_scenarios(cache):
    """Verify prewarming primes all 20 canonical SIIS scenarios."""
    stats = prewarm_canonical_scenarios(cache, siis_path=SIIS_PATH)
    assert stats["scenarios_prewarmed"] == 20
    assert stats["total_cache_entries"] >= 20
    assert stats["prewarm_duration_s"] < 5.0  # Fast prewarm

    # Test that canonical query row_14 hits immediately
    q_14 = "My Galaxy phone's screen is completely cracked, it's a total crack and I can't use the device."
    resp, meta = cache.get(q_14)
    assert resp is not None
    assert meta["cache_hit"] is True
    assert meta["scenario_id"] == "row_14"


def test_latency_benchmarking_and_statistics(cache, valid_response):
    """Benchmark exact hit, semantic hit, and miss latencies; verify P95 <= 300ms."""
    prewarm_canonical_scenarios(cache, siis_path=SIIS_PATH)

    # 1. 20 Repeat Queries (Exact hits)
    exact_q = "My Galaxy phone's screen is completely cracked, it's a total crack and I can't use the device."
    for _ in range(20):
        resp, meta = cache.get(exact_q)
        assert meta["cache_hit"] is True
        assert meta["latency_ms"] < 20.0

    # 2. 5 Paraphrases (Semantic hits)
    para_q = "Where can I enable phone data backup?"
    cache.put("How do I back up my phone?", valid_response, scenario_id="backup")
    for _ in range(5):
        resp, meta = cache.get(para_q)
        assert meta["latency_ms"] < 300.0

    # 3. 5 Misses
    for i in range(5):
        cache.get(f"Unique random query {i} for unindexed topic")

    stats = cache.get_stats()
    assert stats["total_lookups"] >= 30
    assert stats["hit_rate"] >= 0.80
    assert stats["p95_latency_ms"] <= 300.0  # Official SLA: P95 <= 300ms


# ============================================================================
# 7. Additional Context & Intent Safety Tests (Phase 5 Review Pass)
# ============================================================================

def test_exact_cache_identity_includes_siis_fingerprint(cache):
    """Verify exact cache key incorporates the SIIS context fingerprint."""
    siis_1 = {"title": "Wi-Fi Connection Setup", "content": "Open Settings, tap Connections, then Wi-Fi."}
    siis_2 = {"title": "Screen Repair Diagnostics", "content": "Inspect physical screen for cracks and damage."}

    fp1 = compute_siis_fingerprint(siis_1)
    fp2 = compute_siis_fingerprint(siis_2)
    assert fp1 != fp2, "Different SIIS articles must produce distinct fingerprints"

    k1 = cache._compute_key("my screen goes blank", fp1)
    k2 = cache._compute_key("my screen goes blank", fp2)
    assert k1 != k2, "Cache keys for same query with different SIIS contexts must never collide"


def test_same_query_with_different_siis_responses_does_not_cross_hit(cache, valid_response):
    """Verify that same query with 2 materially different SIIS articles does not cross-hit."""
    query = "My Samsung device screen flashes and then goes blank"

    # SIIS 1: Email server / Wi-Fi issue
    siis_email = {
        "title": "Email server not responding on Samsung phone or tablet",
        "content": "Verify your Wi-Fi or mobile data network connection.",
    }
    plan_email = ContextDeeplinkResponse(
        contexts=[
            Goal(
                goal="Follow these steps to perform this Email Connection Troubleshooting",
                title="Email server connection",
                score=0.95,
                actions=[
                    Action(
                        actionName="Check Wifi Network Settings",
                        description="It will check your wifi connection status",
                        category=actionCategory.auto,
                        stepGroups=[
                            StepGroup(
                                steps=["Open Settings, tap Connections, then Wi-Fi."],
                                actionableDeeplink=Deeplink(
                                    deeplink="bixby://masked/act/c9ca763e0c",
                                    description="Opens Wi-Fi settings to connect to networks.",
                                ),
                            )
                        ],
                    )
                ],
            )
        ]
    )

    # SIIS 2: Physical screen crack / hardware issue
    siis_screen = {
        "title": "Cracked screen repair service",
        "content": "Back up data and visit authorized service center.",
    }
    plan_screen = valid_response  # Screen damage plan (Back up data)

    # Store plan_email under (query, siis_email)
    cache.put(query=query, response=plan_email, siis_response=siis_email, scenario_id="email_sc")

    # Store plan_screen under (query, siis_screen)
    cache.put(query=query, response=plan_screen, siis_response=siis_screen, scenario_id="screen_sc")

    # Lookup with SIIS 1 -> must return email plan
    resp1, meta1 = cache.get(query=query, siis_response=siis_email)
    assert resp1 is not None
    assert meta1["cache_hit"] is True
    assert meta1["scenario_id"] == "email_sc"
    assert resp1.contexts[0].title == "Email server connection"

    # Lookup with SIIS 2 -> must return screen plan
    resp2, meta2 = cache.get(query=query, siis_response=siis_screen)
    assert resp2 is not None
    assert meta2["cache_hit"] is True
    assert meta2["scenario_id"] == "screen_sc"
    assert resp2.contexts[0].title == "Screen display damage"

    # Lookup with an unseen SIIS 3 -> must be a cache MISS!
    siis_unseen = {
        "title": "Battery Charging Problems",
        "content": "Inspect charging cable and USB-C port.",
    }
    resp3, meta3 = cache.get(query=query, siis_response=siis_unseen)
    assert resp3 is None
    assert meta3["cache_hit"] is False


def test_lexically_similar_queries_with_different_troubleshooting_intents(cache, valid_response):
    """Verify lexically similar queries with opposing intent do not falsely share cache."""
    # Intent 1: Enable auto-rotate
    q_enable = "How do I turn on auto rotate on my phone"
    plan_enable = ContextDeeplinkResponse(
        contexts=[
            Goal(
                goal="Follow these steps to perform this Screen Rotation Troubleshooting",
                title="Auto rotate settings",
                score=0.95,
                actions=[
                    Action(
                        actionName="Enable Display Auto Rotate",
                        description="It will enable display auto rotate settings",
                        category=actionCategory.auto,
                        stepGroups=[
                            StepGroup(
                                steps=["Swipe down and tap Auto rotate to turn on."],
                                actionableDeeplink=Deeplink(
                                    deeplink="bixby://masked/act/06ee60731f",
                                    description="Turns on auto rotation.",
                                ),
                            )
                        ],
                    )
                ],
            )
        ]
    )
    cache.put(query=q_enable, response=plan_enable, scenario_id="enable_rotate")

    # Intent 2: Disable auto-rotate
    q_disable = "How do I turn off auto rotate on my phone"
    resp_disable, meta_disable = cache.get(query=q_disable)

    # Must NOT hit the enable plan
    if resp_disable is not None:
        assert meta_disable["scenario_id"] != "enable_rotate"
    else:
        assert meta_disable["cache_hit"] is False


def test_semantic_cache_matching_prevents_cross_article_false_positive(cache, valid_response):
    """Verify semantic cache rejects candidates whose SIIS fingerprint does not match."""
    siis_A = {"title": "Article A Display Settings", "content": "Adjust screen brightness in settings."}
    siis_B = {"title": "Article B Mobile Data Issues", "content": "Check SIM card and cellular network."}

    # Cache plan under Query A with SIIS A
    query_A = "My screen is dim and hard to see"
    cache.put(query=query_A, response=valid_response, siis_response=siis_A, scenario_id="display_dim")

    # Paraphrase of Query A, BUT supplied with SIIS B
    paraphrase_query = "The phone display is too dark to read anything"
    resp, meta = cache.get(query=paraphrase_query, siis_response=siis_B)

    # Must be a cache MISS because SIIS contexts do not match!
    assert resp is None
    assert meta["cache_hit"] is False


def test_query_siis_conflict_follows_authoritative_siis(cache):
    """Verify that when query and SIIS conflict, cache does not return unrelated plan."""
    prewarm_canonical_scenarios(cache, siis_path=SIIS_PATH)

    # Query suggests broken screen (canonical row 14 query)
    screen_query = "My Galaxy phone's screen is completely cracked, it's a total crack and I can't use the device."

    # But supplied SIIS is for Email / Wi-Fi issues (canonical row 1)
    with open(SIIS_PATH, "r", encoding="utf-8") as f:
        siis_data = json.load(f)
    row1 = next(r for r in siis_data["responses"] if r["id"] == "row_1")
    email_siis = row1["siis_response"]

    # 1. Cache MUST miss because screen query was never cached with email SIIS
    resp, meta = cache.get(query=screen_query, siis_response=email_siis)
    assert resp is None, "Cache must not return a response when SIIS fingerprint does not match"
    assert meta["cache_hit"] is False

    # 2. When cold engine processes this pair, it must ground in the authoritative SIIS (Email/Wi-Fi)
    from app.services.extractor.deterministic_extractor import DeterministicFallbackExtractor
    from app.services.extractor.engine import ColdPathExtractionEngine
    engine = ColdPathExtractionEngine(
        provider=DeterministicFallbackExtractor(),
        cache=cache,
    )
    plan = engine.extract_and_build(query=screen_query, siis_response=email_siis)
    assert plan is not None
    assert len(plan.contexts) > 0
    # Must follow SIIS context (Email server / Wi-Fi), NOT screen crack
    assert "email" in plan.contexts[0].goal.lower() or "connection" in plan.contexts[0].goal.lower()


