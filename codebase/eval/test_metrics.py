import pytest
from eval.metrics import (
    check_grounding,
    check_polarity_correctness,
    calculate_latency_metrics,
    check_deeplink_resolution
)

def test_grounding_empty_response():
    resp = {"contexts": []}
    result = check_grounding(resp, "Some text")
    # Empty response should explicitly not be marked as successfully "grounded" to avoid false inflation
    assert result["status"] == "NOT_EVALUATED"
    assert result["is_empty"] is True
    assert "not evaluated for actionable grounding" in result["note"]

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
    assert result["status"] == "PASS"
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
    assert result["status"] == "FAIL"
    assert "Factory" in result["unsupported_facts"][0] or "Reset" in result["unsupported_facts"][0]

def test_polarity_correctness():
    # True positives with valid target
    assert check_polarity_correctness({"contexts": [{"actions": [{"actionName": "Enable Wi-Fi"}]}]}, "enable", "wi-fi") is True
    assert check_polarity_correctness({"contexts": [{"actions": [{"actionName": "Turn on Wi-Fi"}]}]}, "enable", "wi-fi") is True
    assert check_polarity_correctness({"contexts": [{"actions": [{"actionName": "Disable Wi-Fi"}]}]}, "disable", "wi-fi") is True

    # Normalized Targets (wifi vs wi-fi)
    assert check_polarity_correctness({"contexts": [{"actions": [{"actionName": "Enable wifi"}]}]}, "enable", "wi-fi") is True

    # Contradictory polarities
    assert check_polarity_correctness({"contexts": [{"actions": [{"actionName": "Enable and disable Wi-Fi"}]}]}, "enable", "wi-fi") is False

    # Explicit negations & Exact Operation Semantics
    # "Do not disable" should not automatically be accepted as "Enable" to enforce exact benchmark rules
    assert check_polarity_correctness({"contexts": [{"actions": [{"actionName": "Do not turn on Wi-Fi"}]}]}, "negated_enable", "wi-fi") is True
    assert check_polarity_correctness({"contexts": [{"actions": [{"actionName": "Do not turn on Wi-Fi"}]}]}, "enable", "wi-fi") is False
    assert check_polarity_correctness({"contexts": [{"actions": [{"actionName": "Do not disable Wi-Fi"}]}]}, "enable", "wi-fi") is False
    assert check_polarity_correctness({"contexts": [{"actions": [{"actionName": "Do not disable Wi-Fi"}]}]}, "negated_disable", "wi-fi") is True

    # Missing target / Wrong Target
    assert check_polarity_correctness({"contexts": [{"actions": [{"actionName": "Enable Bluetooth"}]}]}, "enable", "wi-fi") is False
    assert check_polarity_correctness({"contexts": [{"actions": [{"actionName": "Turn on Bluetooth"}]}]}, "enable", "bluetooth") is True

def test_calculate_latency_metrics():
    latencies = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]
    metrics = calculate_latency_metrics(latencies)
    assert metrics["p50"] == 55.0  # (50+60)/2 depending on exact percentile calc
    assert 90.0 <= metrics["p95"] <= 100.0
    assert 90.0 <= metrics["p99"] <= 100.0
    assert metrics["sample_count"] == 10

def test_deeplink_resolution_exact_matches():
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
    assert result["verified_dummy_positives"] == 0
    assert result["unable_to_verify_provenance"] == 0
    assert result["invalid_attempts"] == 0

def test_deeplink_resolution_dummy_positives():
    valid_catalog = set()
    valid_validation = set()

    # Concrete-looking description, NO provenance metadata => Unable to verify
    resp_concrete = {
        "contexts": [{
            "actions": [{
                "stepGroups": [{
                    "actionableDeeplink": {
                        "deeplink": "bixby://dummy_positive",
                        "description": "It will open Display Settings"
                    }
                }]
            }]
        }]
    }
    res_concrete = check_deeplink_resolution(resp_concrete, valid_catalog, valid_validation)
    assert res_concrete["verified_dummy_positives"] == 0
    assert res_concrete["unable_to_verify_provenance"] == 1
    assert res_concrete["invalid_attempts"] == 0

    # Concrete-looking description WITH provenance metadata, but verifiable => Verified
    resp_provenance = {
        "contexts": [{
            "actions": [{
                "stepGroups": [{
                    "actionableDeeplink": {
                        "deeplink": "bixby://dummy_positive",
                        "description": "It will open Display Settings",
                        "siis_provenance": {"source_match": "Display Settings"}
                    }
                }]
            }]
        }]
    }
    siis_text = "To fix this, adjust your Display Settings."
    res_provenance = check_deeplink_resolution(resp_provenance, valid_catalog, valid_validation, siis_text)
    assert res_provenance["verified_dummy_positives"] == 1
    assert res_provenance["unable_to_verify_provenance"] == 0
    assert res_provenance["invalid_attempts"] == 0

    # Concrete-looking description WITH provenance metadata, but unverifiable (self-asserted) => Unable to verify
    resp_provenance_fake = {
        "contexts": [{
            "actions": [{
                "stepGroups": [{
                    "actionableDeeplink": {
                        "deeplink": "bixby://dummy_positive",
                        "description": "It will open Developer Options",
                        "siis_provenance": {"source_match": "Developer Options"}
                    }
                }]
            }]
        }]
    }
    res_provenance_fake = check_deeplink_resolution(resp_provenance_fake, valid_catalog, valid_validation, siis_text)
    assert res_provenance_fake["verified_dummy_positives"] == 0
    assert res_provenance_fake["unable_to_verify_provenance"] == 1
    assert res_provenance_fake["invalid_attempts"] == 0

    # Generic description => Invalid
    resp_generic = {
        "contexts": [{
            "actions": [{
                "stepGroups": [{
                    "actionableDeeplink": {
                        "deeplink": "bixby://dummy_positive",
                        "description": "Settings"
                    }
                }]
            }]
        }]
    }
    res_generic = check_deeplink_resolution(resp_generic, valid_catalog, valid_validation)
    assert res_generic["verified_dummy_positives"] == 0
    assert res_generic["unable_to_verify_provenance"] == 0
    assert res_generic["invalid_attempts"] == 1

    # Missing description entirely => Malformed / Invalid
    resp_missing = {
        "contexts": [{
            "actions": [{
                "stepGroups": [{
                    "actionableDeeplink": {
                        "deeplink": "bixby://dummy_positive",
                        "description": ""
                    }
                }]
            }]
        }]
    }
    res_missing = check_deeplink_resolution(resp_missing, valid_catalog, valid_validation)
    assert res_missing["verified_dummy_positives"] == 0
    assert res_missing["unable_to_verify_provenance"] == 0
    assert res_missing["invalid_attempts"] == 1

def test_deeplink_resolution_invalid_uris():
    valid_catalog = {"bixby://catalog/uri"}
    valid_validation = set()

    # Malformed URI (Web URL)
    resp_web = {
        "contexts": [{
            "actions": [{
                "stepGroups": [{
                    "actionableDeeplink": {"deeplink": "https://google.com", "description": "Web"}
                }]
            }]
        }]
    }
    res_web = check_deeplink_resolution(resp_web, valid_catalog, valid_validation)
    assert res_web["invalid_attempts"] == 1

    # Non-catalog URI (Invented bixby URI)
    resp_invented = {
        "contexts": [{
            "actions": [{
                "stepGroups": [{
                    "actionableDeeplink": {"deeplink": "bixby://invented/fake", "description": "Fake"}
                }]
            }]
        }]
    }
    res_invented = check_deeplink_resolution(resp_invented, valid_catalog, valid_validation)
    assert res_invented["invalid_attempts"] == 1

    # Valid catalog URI with unrelated description - The evaluator accepts the exact catalog match,
    # but actual SIIS provenance would still be deferred to strict retrieval layers.
    resp_unrelated = {
        "contexts": [{
            "actions": [{
                "stepGroups": [{
                    "actionableDeeplink": {"deeplink": "bixby://catalog/uri", "description": "Some random gibberish"}
                }]
            }]
        }]
    }
    res_unrelated = check_deeplink_resolution(resp_unrelated, valid_catalog, valid_validation)
    assert res_unrelated["catalog_matches"] == 1
    assert res_unrelated["invalid_attempts"] == 0
