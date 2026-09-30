import pytest
import numpy as np
from app.cache.semantic_cache import FastPathSemanticCache, compute_siis_fingerprint
from app.core.schema import ContextDeeplinkResponse, Goal, Action, actionCategory, StepGroup, Deeplink

@pytest.fixture
def cache():
    return FastPathSemanticCache(enable_embeddings=True)

@pytest.fixture
def valid_response():
    return ContextDeeplinkResponse(
        contexts=[
            Goal(
                goal="Follow these steps to perform this Fix Wifi Troubleshooting",
                title="Fix wifi",
                score=1.0,
                actions=[Action(actionName="Turn on wifi", description="It will fix the wifi issue", category=actionCategory.auto, stepGroups=[StepGroup(steps=["test"], actionableDeeplink=Deeplink(deeplink="bixby://masked/act/fdd7f62e24", description="test"))])]
            )
        ]
    )

def test_full_siis_fingerprint():
    # Long SIIS string
    siis1 = "A" * 600 + "B"
    siis2 = "A" * 600 + "C"

    fp1 = compute_siis_fingerprint(siis1)
    fp2 = compute_siis_fingerprint(siis2)
    assert fp1 != fp2, "Fingerprint should hash the FULL SIIS content"

def test_siis_fingerprint_dict():
    # Long SIIS dict
    siis1 = {"title": "Title", "content": "A" * 600 + "B"}
    siis2 = {"title": "Title", "content": "A" * 600 + "C"}

    fp1 = compute_siis_fingerprint(siis1)
    fp2 = compute_siis_fingerprint(siis2)
    assert fp1 != fp2, "Fingerprint should hash the FULL SIIS content for dicts"

def test_cache_poisoning(cache):
    # Try inserting an invalid response directly to exact_store to bypass `put` validate
    pass # Wait we only care about `put` validate, which is tested in existing tests. We can check if invalid response can bypass validate via other means?


def test_cache_poisoning(cache):
    # Try inserting an invalid response
    from app.core.schema import ContextDeeplinkResponse, Goal, Action, actionCategory

    # An invalid response according to schema (e.g. empty actions)
    invalid_response = ContextDeeplinkResponse(
        contexts=[
            Goal(
                goal="Invalid Goal Syntax",  # Fails regex!
                title="Bad title having way too many words",  # 7 words!
                score=2.5,  # Out of range!
                actions=[],  # Empty actions!
            )
        ]
    )

    # Attempt to cache the invalid response
    stored = cache.put("Query for bad plan", invalid_response)

    # Should be rejected by validation firewall
    assert stored is False, "Invalid responses should not be cached"
    assert len(cache.exact_store) == 0, "Exact store should be empty"
    assert len(cache.entries_list) == 0, "Entries list should be empty"

def test_cache_return_validation(cache):
    # Verify that the ValidationFirewall is run on cache *return* (`get`).
    from app.core.schema import ContextDeeplinkResponse, Goal, Action, actionCategory, StepGroup, Deeplink
    from app.cache.semantic_cache import compute_siis_fingerprint

    valid = ContextDeeplinkResponse(
        contexts=[
            Goal(
                goal="Follow these steps to perform this Fix issue Troubleshooting",
                title="Fix issue",
                score=1.0,
                actions=[Action(actionName="Do something", description="It will fix the issue", category=actionCategory.auto, stepGroups=[StepGroup(steps=["step"], actionableDeeplink=Deeplink(deeplink="bixby://masked/act/fdd7f62e24", description="test"))])]
            )
        ]
    )

    # Put a valid response
    cache.put("my validate query", valid)

    # Mutate the exact store to make it invalid (simulating schema/catalog change over time)
    # The title should be 2-3 words. We will make it 8 words. Since allow_repair=False is now used on retrieval, this should fail.
    cache.exact_store[cache._compute_key("my validate query", compute_siis_fingerprint(None))].response.contexts[0].title = "This is a very long title that should fail validation"

    resp, meta = cache.get("my validate query")
    assert resp is None, "Should not return an invalid response that fails the firewall on cache return"
    assert meta["hit_type"] == "invalid_cached"

def test_cache_engine_version_miss(cache, valid_response):
    cache.put("query version", valid_response)

    # Manually modify the version token requirement
    cache.version_manager.engine_version = "2.0.0"
    cache.version_manager._version_token = cache.version_manager._generate_token()

    resp, meta = cache.get("query version")
    assert resp is None, "Engine version change should cause cache miss"
    assert meta["cache_hit"] is False

def test_cache_catalog_version_miss(cache, valid_response):
    cache.put("query catalog", valid_response)

    # Manually modify catalog hash
    cache.version_manager.catalog_hash = "newhash123"
    cache.version_manager._version_token = cache.version_manager._generate_token()

    resp, meta = cache.get("query catalog")
    assert resp is None, "Catalog version change should cause cache miss"
    assert meta["cache_hit"] is False

def test_malformed_empty_siis(cache, valid_response):
    # Testing that empty/malformed SIIS strings don't crash and yield CANONICAL_DEFAULT
    from app.cache.semantic_cache import compute_siis_fingerprint

    assert compute_siis_fingerprint(None) == "CANONICAL_DEFAULT"
    assert compute_siis_fingerprint("") == "CANONICAL_DEFAULT"
    assert compute_siis_fingerprint({}) == "CANONICAL_DEFAULT"

def test_prewarm_correctness(cache):
    from app.cache.prewarm import prewarm_canonical_scenarios
    stats = prewarm_canonical_scenarios(cache, siis_path="siis_responses.json")

    # Check that prewarming populated the cache using exactly identical rules
    assert len(cache.exact_store) > 0
    assert stats["scenarios_prewarmed"] > 0



def test_real_dependency_invalidation(valid_response, tmp_path):
    import json
    import time
    from app.cache.semantic_cache import FastPathSemanticCache

    cat_path = tmp_path / "catalog.json"
    cat_path.write_text('{"deeplinks": [{"deeplink": "bixby://masked/act/fdd7f62e24", "validation": {"deeplink": "bixby://val"}}]}')

    # Init cache
    c = FastPathSemanticCache(catalog_path=cat_path, enable_embeddings=False)

    c.put("test query", valid_response)
    resp, meta = c.get("test query")
    assert meta["cache_hit"] is True

    # Sleep briefly to ensure mtime changes if relying on that, though we rely on hash
    # Actually just modifying contents changes hash

    hash1 = c.version_manager.catalog_hash
    cat_path.write_text('{"deeplinks": []}')
    import time; time.sleep(0.1)

    # Let's verify compute_file_hash changed
    from app.cache.semantic_cache import compute_file_hash
    hash2 = compute_file_hash(cat_path)
    assert hash1 != hash2, f"File hash did not change! {hash1} vs {hash2}"

    resp2, meta2 = c.get("test query")
    assert meta2["cache_hit"] is False, f"Should miss because catalog hash changed. Catalog hash: {c.version_manager.catalog_hash}"

    assert len(c.exact_store) == 0, "Cache should have been invalidated"

    # Verify version state refreshed
    new_token = c.version_manager.version_token

    # Cache the item again under the NEW dependency version
    c.put("test query", valid_response)

    # Second lookup should HIT and NOT invalidate again because the hash is stable
    resp3, meta3 = c.get("test query")
    assert meta3["cache_hit"] is True, "Second lookup should hit and not repeatedly invalidate"
    assert c.version_manager.version_token == new_token, "Token should remain stable"


def test_semantic_invalidation_consistency(valid_response):
    from app.cache.semantic_cache import FastPathSemanticCache
    c = FastPathSemanticCache(enable_embeddings=True)
    c.put("semantic query", valid_response)

    assert len(c.entries_list) == 1
    assert c.vector_matrix is not None
    assert c.vector_matrix.shape[0] == 1

    c.invalidate("test")

    assert len(c.exact_store) == 0
    assert len(c.entries_list) == 0
    assert c.vector_matrix is None


def test_concurrent_stress(cache, valid_response):
    import threading
    import random

    stop_event = threading.Event()
    exceptions = []

    def writer():
        try:
            for i in range(100):
                if stop_event.is_set(): break
                cache.put(f"query_{i}", valid_response)
        except Exception as e:
            exceptions.append(e)

    def reader():
        try:
            for i in range(100):
                if stop_event.is_set(): break
                cache.get(f"query_{random.randint(0, 100)}")
        except Exception as e:
            exceptions.append(e)

    def invalidator():
        try:
            for i in range(10):
                if stop_event.is_set(): break
                cache.invalidate()
                import time; time.sleep(0.01)
        except Exception as e:
            exceptions.append(e)

    threads = []
    for _ in range(5): threads.append(threading.Thread(target=writer))
    for _ in range(5): threads.append(threading.Thread(target=reader))
    threads.append(threading.Thread(target=invalidator))

    for t in threads: t.start()
    for t in threads: t.join()

    assert not exceptions, f"Concurrent stress test raised exceptions: {exceptions}"

    # Check stats safely
    stats = cache.get_stats()
    assert stats["total_lookups"] >= 0
