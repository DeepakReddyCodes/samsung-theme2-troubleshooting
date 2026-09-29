"""Executable tests for SIIS-aware cache isolation."""
import pytest
from app.cache.semantic_cache import FastPathSemanticCache
from app.core.schema import ContextDeeplinkResponse


def test_different_siis_content_no_collision():
    """Ensure different SIIS content for same queries doesn't collide in the cache."""
    cache = FastPathSemanticCache()
    query = "How do I fix my screen?"

    from app.core.schema import Goal, Action, StepGroup, actionCategory
    # Store with SIIS A. Note that cache rejects empty contexts, so we provide a valid dummy goal.
    resp_a = ContextDeeplinkResponse(contexts=[Goal(goal="Follow these steps to perform this Valid Troubleshooting.", title="Valid Title", actions=[Action(actionName="A", description="It will do a thing", stepGroups=[StepGroup(steps=["S"])], category=actionCategory.manual)], score=1.0)])
    cache.put(query, resp_a, siis_response="SIIS A")

    # Retrieve with SIIS B - should miss
    resp_b, meta_b = cache.get(query, siis_response="SIIS B")
    assert resp_b is None
    assert meta_b["cache_hit"] is False

    # Retrieve with SIIS A - should hit
    resp_a_ret, meta_a = cache.get(query, siis_response="SIIS A")
    assert resp_a_ret is not None
    assert meta_a["cache_hit"] is True


def test_polarity_differences_no_collision():
    """Ensure 'enable' vs 'disable' does not hit the same cache entry."""
    cache = FastPathSemanticCache()

    from app.core.schema import Goal, Action, StepGroup, actionCategory
    resp = ContextDeeplinkResponse(contexts=[Goal(goal="Follow these steps to perform this Valid Troubleshooting.", title="Valid Title", actions=[Action(actionName="A", description="It will do a thing", stepGroups=[StepGroup(steps=["S"])], category=actionCategory.manual)], score=1.0)])
    cache.put("how do i enable wifi", resp, scenario_id="wifi_on")

    # Opposing intent
    resp_miss, meta = cache.get("how do i disable wifi")
    # Our intent conflict check should prevent this from hitting
    assert resp_miss is None
    assert meta["cache_hit"] is False


def test_engine_catalog_version_changes_invalidate_cache():
    """Ensure version changes prevent stale entry reuse."""
    # Test automatic version isolation, not manual invalidation.
    cache_v1 = FastPathSemanticCache(engine_version="1.0")

    from app.core.schema import Goal, Action, StepGroup, actionCategory
    resp = ContextDeeplinkResponse(contexts=[Goal(goal="Follow these steps to perform this Valid Troubleshooting.", title="Valid Title", actions=[Action(actionName="A", description="It will do a thing", stepGroups=[StepGroup(steps=["S"])], category=actionCategory.manual)], score=1.0)])
    # Assume default config uses same cache dir or memory, but version isolates
    cache_v1.put("test query", resp, siis_response="context")

    # We should get a hit on v1
    hit, meta = cache_v1.get("test query", siis_response="context")
    assert hit is not None
    assert meta["cache_hit"] is True

    # Same query, but different cache instance with updated version
    cache_v2 = FastPathSemanticCache(engine_version="2.0")
    resp_miss, meta = cache_v2.get("test query", siis_response="context")
    # Will miss because engine version is different
    assert resp_miss is None
    assert meta["cache_hit"] is False
