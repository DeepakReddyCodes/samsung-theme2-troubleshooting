import pytest
import sys
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT))

from scripts.cost_calculator import calculate_cost

def test_cost_calculator_zero_cache_hit_rate():
    res = calculate_cost(1000, 300, 100000, 0.15, 0.60, 0.0)
    # uncached = (1000/1M)*0.15 + (300/1M)*0.60 = 0.00015 + 0.00018 = 0.00033
    assert abs(res["uncached_cost_per_query"] - 0.00033) < 1e-6
    assert abs(res["cached_effective_cost_per_query"] - 0.00033) < 1e-6
    assert abs(res["uncached_monthly_cost"] - 33.0) < 1e-6
    assert abs(res["monthly_cost_with_cache"] - 33.0) < 1e-6
    assert abs(res["monthly_savings_with_cache"] - 0.0) < 1e-6

def test_cost_calculator_100_percent_cache_hit_rate():
    res = calculate_cost(1000, 300, 100000, 0.15, 0.60, 1.0)
    assert abs(res["cached_effective_cost_per_query"] - 0.0) < 1e-6
    assert abs(res["monthly_cost_with_cache"] - 0.0) < 1e-6
    assert abs(res["monthly_savings_with_cache"] - 33.0) < 1e-6

def test_cost_calculator_partial_cache_hit_rate():
    res = calculate_cost(1000, 300, 100000, 0.15, 0.60, 0.5)
    assert abs(res["cached_effective_cost_per_query"] - (0.00033 * 0.5)) < 1e-6
    assert abs(res["monthly_cost_with_cache"] - 16.5) < 1e-6
    assert abs(res["monthly_savings_with_cache"] - 16.5) < 1e-6

def test_cost_calculator_zero_requests():
    res = calculate_cost(1000, 300, 0, 0.15, 0.60, 0.5)
    assert res["uncached_monthly_cost"] == 0.0
    assert res["monthly_cost_with_cache"] == 0.0
    assert res["monthly_savings_with_cache"] == 0.0

def test_cost_calculator_zero_tokens():
    res = calculate_cost(0, 0, 100000, 0.15, 0.60, 0.5)
    assert res["uncached_cost_per_query"] == 0.0
    assert res["cached_effective_cost_per_query"] == 0.0
    assert res["monthly_cost_with_cache"] == 0.0

def test_cost_calculator_invalid_negative_tokens():
    with pytest.raises(ValueError, match="Input tokens per request must be >= 0"):
        calculate_cost(-10, 300, 100000, 0.15, 0.60, 0.5)
    with pytest.raises(ValueError, match="Output tokens per request must be >= 0"):
        calculate_cost(1000, -5, 100000, 0.15, 0.60, 0.5)

def test_cost_calculator_invalid_negative_requests():
    with pytest.raises(ValueError, match="Requests per month must be >= 0"):
        calculate_cost(1000, 300, -100, 0.15, 0.60, 0.5)

def test_cost_calculator_invalid_negative_prices():
    with pytest.raises(ValueError, match="Price per 1M input tokens must be >= 0"):
        calculate_cost(1000, 300, 100000, -0.1, 0.60, 0.5)
    with pytest.raises(ValueError, match="Price per 1M output tokens must be >= 0"):
        calculate_cost(1000, 300, 100000, 0.15, -0.2, 0.5)

def test_cost_calculator_cache_hit_rate_below_zero():
    with pytest.raises(ValueError, match="Cache hit rate must be between 0.0 and 1.0 inclusive"):
        calculate_cost(1000, 300, 100000, 0.15, 0.60, -0.1)

def test_cost_calculator_cache_hit_rate_above_one():
    with pytest.raises(ValueError, match="Cache hit rate must be between 0.0 and 1.0 inclusive"):
        calculate_cost(1000, 300, 100000, 0.15, 0.60, 1.1)
