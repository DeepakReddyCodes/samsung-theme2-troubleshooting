import re
import json
from typing import Dict, Any, List

def check_action_validity(response_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Measures action structure, categories, ordering, and descriptions.
    """
    valid_categories = {"auto", "manual", "critical"}
    category_order = {"auto": 0, "manual": 1, "critical": 2}

    contexts = response_data.get("contexts", [])
    if not contexts:
        return {"valid_structure": False, "valid_categories": False, "valid_ordering": False, "valid_descriptions": False}

    goal_obj = contexts[0]
    actions = goal_obj.get("actions", [])

    if not actions:
        # Empty actions can be valid for adversarial/no-evidence cases, but typically false for action validity
        return {"valid_structure": False, "valid_categories": False, "valid_ordering": False, "valid_descriptions": False}

    valid_structure = True
    valid_categories_flag = True
    valid_descriptions = True

    order_indices = []

    for act in actions:
        category = act.get("category")
        if category not in valid_categories:
            valid_categories_flag = False
        else:
            order_indices.append(category_order[category])

        desc = act.get("description", "").strip()
        words = desc.split()
        if not (5 <= len(words) <= 7 and desc.startswith("It will")):
            valid_descriptions = False

        if not act.get("stepGroups"):
            valid_structure = False
        else:
            for sg in act.get("stepGroups", []):
                if not sg.get("steps"):
                    valid_structure = False

    valid_ordering = (order_indices == sorted(order_indices))

    return {
        "valid_structure": valid_structure,
        "valid_categories": valid_categories_flag,
        "valid_ordering": valid_ordering,
        "valid_descriptions": valid_descriptions
    }


def check_deeplink_resolution(response_data: Dict[str, Any], valid_catalog_uris: set, valid_validation_uris: set) -> Dict[str, Any]:
    """
    Measures exact catalog URI resolution, validation URIs, dummy-positive validation, and invalid URIs.
    Explicitly tracks inability to verify SIIS provenance from the final JSON structure alone.
    """
    contexts = response_data.get("contexts", [])
    if not contexts:
        return {"catalog_matches": 0, "validation_matches": 0, "verified_dummy_positives": 0, "unable_to_verify_provenance": 0, "invalid_attempts": 0}

    catalog_matches = 0
    validation_matches = 0
    verified_dummy_positives = 0
    unable_to_verify_provenance = 0
    invalid_attempts = 0

    for act in contexts[0].get("actions", []):
        for sg in act.get("stepGroups", []):
            dl_obj = sg.get("actionableDeeplink")
            val_obj = sg.get("validationDeeplink")

            # Actionable DeepLink
            if dl_obj:
                uri = dl_obj.get("deeplink", "")
                if uri in valid_catalog_uris:
                    catalog_matches += 1
                elif uri.startswith("bixby://dummy_positive"):
                    desc = dl_obj.get("description", "").strip().lower()

                    # 1. Invalid Attempts
                    if not desc or desc in ["settings", "device settings", "open settings"]:
                        # Missing or generic descriptions cannot act as a concrete dummy fallback
                        invalid_attempts += 1
                    # 2. Heuristic concrete-target plausibility check (Not Proof)
                    else:
                        # W06 evaluator cannot prove SIIS provenance strictly from the JSON payload
                        # unless provenance metadata is present.
                        provenance_meta = dl_obj.get("siis_provenance")

                        if provenance_meta:
                            # If metadata is present proving derivation, we can verify it
                            verified_dummy_positives += 1
                        else:
                            # The target looks concrete heuristically, but we cannot establish end-to-end provenance.
                            unable_to_verify_provenance += 1
                else:
                    # Non-catalog URIs or generic invalid formats fall here
                    invalid_attempts += 1

            # Validation DeepLink
            if val_obj:
                uri = val_obj.get("deeplink", "")
                if uri in valid_catalog_uris or uri in valid_validation_uris:
                    validation_matches += 1
                else:
                    invalid_attempts += 1

    return {
        "catalog_matches": catalog_matches,
        "validation_matches": validation_matches,
        "verified_dummy_positives": verified_dummy_positives,
        "unable_to_verify_provenance": unable_to_verify_provenance,
        "invalid_attempts": invalid_attempts
    }

def check_grounding(response_data: Dict[str, Any], siis_text: str) -> Dict[str, Any]:
    """
    Deterministic evaluation metric that compares generated troubleshooting steps against SIIS evidence.
    Returns actual pass/fail result based on lexical coverage approximation.
    Identifies explicitly unsupported action content.
    """
    contexts = response_data.get("contexts", [])

    # An empty response is NOT evidence of successful grounding. It is an evaluation-not-applicable safe state.
    if not contexts or not contexts[0].get("actions"):
        return {
            "is_grounded": False,
            "is_empty": True,
            "unsupported_facts": [],
            "note": "Empty response - not evaluated for actionable grounding"
        }

    siis_lower = siis_text.lower()

    # Generic stop words to ignore in strict grounding coverage
    stopwords = {"the", "a", "an", "and", "or", "to", "in", "on", "of", "for", "with", "is", "it", "will", "go", "navigate", "open", "check", "how", "do", "you", "my", "steps", "perform", "this", "troubleshooting", "settings", "device"}

    unsupported_facts = []

    for act in contexts[0].get("actions", []):
        act_name = act.get("actionName", "")
        # Inspect action name
        name_words = [w.strip(".,!?\"'") for w in act_name.lower().split() if w.strip(".,!?\"'") not in stopwords and len(w) > 2]
        name_matched = sum(1 for w in name_words if w in siis_lower)
        # If less than 50% of significant words in action name are found, mark as ungrounded
        if name_words and (name_matched / len(name_words) < 0.5):
            unsupported_facts.append(f"ActionName: {act_name}")

        for sg in act.get("stepGroups", []):
            for step in sg.get("steps", []):
                step_words = [w.strip(".,!?\"'") for w in step.lower().split() if w.strip(".,!?\"'") not in stopwords and len(w) > 2]
                if not step_words:
                    continue
                match_count = sum(1 for w in step_words if w in siis_lower)
                # If less than 50% of significant words are found, consider the step ungrounded
                if match_count / len(step_words) < 0.5:
                    unsupported_facts.append(f"Step: {step}")

    is_grounded = len(unsupported_facts) == 0
    return {
        "is_grounded": is_grounded,
        "is_empty": False,
        "unsupported_facts": unsupported_facts,
        "note": "Lexical grounding approximation (does not establish full semantic entailment)"
    }

def check_polarity_correctness(response_data: Dict[str, Any], expected_polarity: str, target_entity: str) -> bool:
    """
    Verifies the intended action polarity (enable vs disable) AND the specified target entity rigorously.
    Tests for explicit negations, contradictory output, and wrong targets.
    Enforces exact operation semantics for benchmarking.
    """
    contexts = response_data.get("contexts", [])
    if not contexts:
        return False

    actions_text = json.dumps(contexts[0].get("actions", [])).lower()

    target_lower = target_entity.lower()
    # Normalize variants
    if target_lower == "wi-fi":
        target_lower = "wifi"

    actions_normalized = actions_text.replace("wi-fi", "wifi")

    # Must contain the target to pass
    if target_lower not in actions_normalized:
        return False

    enable_terms = {"enable", "turn on"}
    disable_terms = {"disable", "turn off"}
    negated_enable_terms = {"do not enable", "don't enable", "do not turn on", "don't turn on", "keep off"}
    negated_disable_terms = {"do not disable", "don't disable", "do not turn off", "don't turn off", "keep on"}

    has_enable = any(t in actions_normalized for t in enable_terms) and not any(t in actions_normalized for t in negated_enable_terms)
    has_disable = any(t in actions_normalized for t in disable_terms) and not any(t in actions_normalized for t in negated_disable_terms)

    has_negated_enable = any(t in actions_normalized for t in negated_enable_terms)
    has_negated_disable = any(t in actions_normalized for t in negated_disable_terms)

    # Fail on contradictory output containing both explicit enable and disable without clear context
    if has_enable and has_disable:
        return False

    # Evaluate exact operation semantics
    if expected_polarity == "enable":
        return has_enable and not has_negated_disable # Don't automatically conflate "do not disable" as "enable"
    elif expected_polarity == "disable":
        return has_disable and not has_negated_enable
    elif expected_polarity == "negated_enable":
        return has_negated_enable
    elif expected_polarity == "negated_disable":
        return has_negated_disable

    return False

def calculate_latency_metrics(latencies: List[float]) -> Dict[str, float]:
    """Calculates p50, p95, p99 latencies using proper percentile calculation."""
    if not latencies:
        return {"p50": 0.0, "p95": 0.0, "p99": 0.0, "avg": 0.0, "sample_count": 0}

    latencies.sort()
    n = len(latencies)

    def get_percentile(p):
        k = (n - 1) * p
        f = int(k)
        c = f + 1 if f + 1 < n else f
        if f == c:
            return latencies[int(k)]
        d0 = latencies[f] * (c - k)
        d1 = latencies[c] * (k - f)
        return d0 + d1

    return {
        "p50": get_percentile(0.50),
        "p95": get_percentile(0.95),
        "p99": get_percentile(0.99),
        "avg": sum(latencies) / n,
        "sample_count": n
    }
