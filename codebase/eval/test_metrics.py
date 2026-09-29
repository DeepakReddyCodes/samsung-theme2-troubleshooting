import pytest
from eval.metrics import (
    check_grounding,
    check_polarity_correctness,
    calculate_latency_metrics,
    check_deeplink_resolution
)

def test_grounding_valid_step():
    siis_text = "To fix the issue, open Settings and then navigate to Display to reset the configuration."
    resp = {
        "contexts": [{
            "actions": [{
                "actionName": "Reset Display Settings",
                "stepGroups": [{"steps": ["Navigate to Display and reset"]}]
            }]
        }]
    }
    result = check_grounding(resp, siis_text)
    assert result["is_grounded"] is True
    assert len(result["unsupported_facts"]) == 0

def test_grounding_unsupported_step():
    siis_text = "To fix the issue, turn the device off and on."
    resp = {
        "contexts": [{
            "actions": [{
                "actionName": "Factory Reset Device",
                "stepGroups": [{"steps": ["Navigate to Settings and Factory Reset"]}]
            }]
        }]
    }
    result = check_grounding(resp, siis_text)
    assert result["is_grounded"] is False
    assert "Factory" in result["unsupported_facts"][0] or "Reset" in result["unsupported_facts"][0]

def test_grounding_empty_response():
    resp = {"contexts": []}
    result = check_grounding(resp, "Some text")
    # Empty response should explicitly not be marked as successfully "grounded" to avoid false inflation
    assert result["is_grounded"] is False
    assert result["is_empty"] is True
    assert "not evaluated for actionable grounding" in result["note"]

def test_polarity_correctness():
    # True positives with valid target
    assert check_polarity_correctness({"contexts": [{"actions": [{"actionName": "Enable Wi-Fi"}]}]}, "enable", "wi-fi") is True
    assert check_polarity_correctness({"contexts": [{"actions": [{"actionName": "Turn on Wi-Fi"}]}]}, "enable", "wi-fi") is True
    assert check_polarity_correctness({"contexts": [{"actions": [{"actionName": "Disable Wi-Fi"}]}]}, "disable", "wi-fi") is True

    # Contradictory polarities
    assert check_polarity_correctness({"contexts": [{"actions": [{"actionName": "Enable and disable Wi-Fi"}]}]}, "enable", "wi-fi") is False

    # Explicit negations
    assert check_polarity_correctness({"contexts": [{"actions": [{"actionName": "Do not turn on Wi-Fi"}]}]}, "negated_enable", "wi-fi") is True
    assert check_polarity_correctness({"contexts": [{"actions": [{"actionName": "Do not turn on Wi-Fi"}]}]}, "enable", "wi-fi") is False

    # Missing target
    assert check_polarity_correctness({"contexts": [{"actions": [{"actionName": "Enable Bluetooth"}]}]}, "enable", "wi-fi") is False
    assert check_polarity_correctness({"contexts": [{"actions": [{"actionName": "Turn on Bluetooth"}]}]}, "enable", "bluetooth") is True

def test_calculate_latency_metrics():
    latencies = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]
    metrics = calculate_latency_metrics(latencies)
    assert metrics["p50"] == 55.0  # (50+60)/2 depending on exact percentile calc
    assert 90.0 <= metrics["p95"] <= 100.0
    assert 90.0 <= metrics["p99"] <= 100.0
    assert metrics["sample_count"] == 10

def test_deeplink_resolution():
    valid_catalog = {"bixby://valid/uri"}
    valid_validation = {"bixby://valid/validation"}

    resp = {
        "contexts": [{
            "actions": [{
                "stepGroups": [{
                    "actionableDeeplink": {"deeplink": "bixby://valid/uri", "description": "Valid URI"},
                    "validationDeeplink": {"deeplink": "bixby://valid/validation", "description": "Validation URI"}
                }]
            }]
        }]
    }

    result = check_deeplink_resolution(resp, valid_catalog, valid_validation)
    assert result["catalog_matches"] == 1
    assert result["validation_matches"] == 1
    assert result["invalid_attempts"] == 0

def test_dummy_positive_requires_target_desc():
    valid_catalog = set()
    valid_validation = set()

    resp_valid = {
        "contexts": [{
            "actions": [{
                "stepGroups": [{
                    "actionableDeeplink": {
                        "deeplink": "bixby://dummy_positive",
                        "description": "It will open Display Settings" # 5 words => >= 3 words
                    }
                }]
            }]
        }]
    }
    res_valid = check_deeplink_resolution(resp_valid, valid_catalog, valid_validation)
    assert res_valid["dummy_positive"] == 1
    assert res_valid["invalid_attempts"] == 0

    resp_invalid = {
        "contexts": [{
            "actions": [{
                "stepGroups": [{
                    "actionableDeeplink": {
                        "deeplink": "bixby://dummy_positive",
                        "description": "Display" # Too short => Invalid Fallback Attempt
                    }
                }]
            }]
        }]
    }
    res_invalid = check_deeplink_resolution(resp_invalid, valid_catalog, valid_validation)
    assert res_invalid["dummy_positive"] == 0
    assert res_invalid["invalid_attempts"] == 1
