import json
import time
import httpx
from pathlib import Path
from datasets import (
    load_canonical_dataset,
    load_paraphrased_dataset,
    load_unseen_siis_dataset,
    load_adversarial_dataset,
    load_polarity_dataset
)
from metrics import (
    check_action_validity,
    check_deeplink_resolution,
    check_grounding,
    check_polarity_correctness,
    calculate_latency_metrics
)

BASE_URL = "http://127.0.0.1:8000"
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent

def load_catalog_uris():
    catalog_path = WORKSPACE_ROOT / "deeplinks.json"
    if not catalog_path.exists():
        return set(), set()
    with open(catalog_path, "r", encoding="utf-8") as f:
        catalog_raw = json.load(f)
    catalog_items = catalog_raw.get("deeplinks", []) if isinstance(catalog_raw, dict) else catalog_raw
    valid_uris = {item["deeplink"] for item in catalog_items if "deeplink" in item}

    valid_val_uris = {
        item["validation"]["deeplink"]
        for item in catalog_items
        if item.get("validation") and "deeplink" in item["validation"]
    }
    return valid_uris, valid_val_uris

def send_request(client, query, siis_response):
    t0 = time.perf_counter()
    try:
        resp = client.post("/v1/troubleshoot", json={"query": query, "siis_response": siis_response})
        t_roundtrip = (time.perf_counter() - t0) * 1000.0
        return resp.status_code, resp.json(), resp.headers, t_roundtrip
    except Exception as e:
        return 500, {}, {}, 0.0

def run_evaluation():
    print("=" * 80)
    print("STARTING W06 EVALUATION AND BENCHMARKING HARNESS")
    print("=" * 80)

    client = httpx.Client(base_url=BASE_URL, timeout=30.0)

    # Check if server is up
    try:
        client.get("/health")
    except Exception:
        print("ERROR: API Server is not running. Start the server on port 8000 before running eval.")
        return

    valid_catalog_uris, valid_validation_uris = load_catalog_uris()

    results = {
        "canonical": {"latencies": [], "cache_hits": 0, "total": 0, "valid_actions": 0, "dl_catalog": 0, "dl_verified_dummy": 0, "dl_unable_verify": 0, "dl_invalid": 0, "eval_errors": 0},
        "paraphrased": {"latencies": [], "cache_hits": 0, "total": 0, "valid_actions": 0, "eval_errors": 0},
        "unseen": {
            "latencies": [], "total": 0, "grounded": 0, "valid_actions": 0,
            "correctly_empty": 0, "incorrectly_empty": 0, "eval_errors": 0
        },
        "adversarial": {
            "total": 0, "safely_rejected": 0, "safely_ignored": 0,
            "unsafe_propagation": 0, "eval_errors": 0
        },
        "polarity": {"total": 0, "correct": 0, "eval_errors": 0}
    }

    # 1. Canonical Dataset
    canonical_data = load_canonical_dataset()
    for item in canonical_data[:20]: # Limit for eval speed if necessary
        status, data, headers, latency = send_request(client, item["original_query"], item["siis_response"])
        results["canonical"]["total"] += 1

        if status == 500 or status == 0 or (status != 200 and status != 422):
            results["canonical"]["eval_errors"] += 1
            continue

        results["canonical"]["latencies"].append(latency)
        if headers.get("x-cache-hit") == "true":
            results["canonical"]["cache_hits"] += 1

        if status == 200:
            val = check_action_validity(data)
            if val["valid_structure"] and val["valid_descriptions"]:
                results["canonical"]["valid_actions"] += 1

            dl_res = check_deeplink_resolution(data, valid_catalog_uris, valid_validation_uris)
            results["canonical"]["dl_catalog"] += dl_res["catalog_matches"]
            results["canonical"].setdefault("dl_validation", 0)
            results["canonical"]["dl_validation"] += dl_res["validation_matches"]
            results["canonical"]["dl_verified_dummy"] += dl_res["verified_dummy_positives"]
            results["canonical"]["dl_unable_verify"] += dl_res["unable_to_verify_provenance"]
            results["canonical"]["dl_invalid"] += dl_res["invalid_attempts"]

    # 2. Paraphrased Dataset
    paraphrased_data = load_paraphrased_dataset()
    for item in paraphrased_data:
        status, data, headers, latency = send_request(client, item["query"], item["siis_response"])
        results["paraphrased"]["total"] += 1

        if status == 500 or status == 0 or (status != 200 and status != 422):
            results["paraphrased"]["eval_errors"] += 1
            continue

        results["paraphrased"]["latencies"].append(latency)
        if headers.get("x-cache-hit") == "true" and headers.get("x-cache-type") == "semantic":
            results["paraphrased"]["cache_hits"] += 1

        if status == 200:
            val = check_action_validity(data)
            if val["valid_structure"]:
                results["paraphrased"]["valid_actions"] += 1

    # 3. Unseen SIIS Dataset
    unseen_data = load_unseen_siis_dataset()
    for item in unseen_data:
        status, data, headers, latency = send_request(client, item["query"], item["siis_response"])
        results["unseen"]["total"] += 1

        if status == 500 or status == 0 or (status != 200 and status != 422):
             results["unseen"]["eval_errors"] += 1
             continue

        results["unseen"]["latencies"].append(latency)

        if status == 200:
            contexts = data.get("contexts", [])
            has_actions = contexts and contexts[0].get("actions")
            is_reject_case = "reject" in item["id"]

            # Record Empty Response Semantics
            if not has_actions:
                if is_reject_case:
                    results["unseen"]["correctly_empty"] += 1
                else:
                    results["unseen"]["incorrectly_empty"] += 1
            else:
                grounding_res = check_grounding(data, item["siis_response"]["content"])
                if grounding_res["is_grounded"]:
                    results["unseen"]["grounded"] += 1

                val = check_action_validity(data)
                if val["valid_structure"]:
                    results["unseen"]["valid_actions"] += 1

    # 4. Adversarial Dataset
    adv_data = load_adversarial_dataset()
    for item in adv_data:
        status, data, headers, latency = send_request(client, item["query"], item["siis_response"])
        results["adversarial"]["total"] += 1

        if status == 500 or status == 0 or (status != 200 and status != 422):
             results["adversarial"]["eval_errors"] += 1
             continue

        if status == 422:
             results["adversarial"]["safely_rejected"] += 1
        elif status == 200:
            contexts = data.get("contexts", [])
            has_actions = contexts and contexts[0].get("actions")
            if not has_actions:
                 # Empty responses to adversarial inputs are considered safe rejections
                 results["adversarial"]["safely_rejected"] += 1
            else:
                 # Check if injected forbidden concepts propagated to output
                 text = json.dumps(data).lower()
                 forbidden_concepts = item.get("forbidden_concepts", [])
                 unsafe = any(concept.lower() in text for concept in forbidden_concepts)

                 if unsafe:
                     results["adversarial"]["unsafe_propagation"] += 1
                 else:
                     # Action output generated, but malicious payload ignored
                     results["adversarial"]["safely_ignored"] += 1

    # 5. Polarity Dataset
    pol_data = load_polarity_dataset()
    for item in pol_data:
        status, data, headers, latency = send_request(client, item["query"], item["siis_response"])
        results["polarity"]["total"] += 1

        if status == 500 or status == 0 or (status != 200 and status != 422):
            results["polarity"]["eval_errors"] += 1
            continue

        if status == 200:
            expected = "enable"
            if "negated_enable" in item["id"]:
                expected = "negated_enable"
            elif "negated_disable" in item["id"]:
                expected = "negated_disable"
            elif "disable" in item["id"]:
                expected = "disable"

            target_entity = item.get("target", "")

            if check_polarity_correctness(data, expected, target_entity):
                results["polarity"]["correct"] += 1

    # Calculate final latency metrics
    lat_canon = calculate_latency_metrics(results["canonical"]["latencies"])
    lat_para = calculate_latency_metrics(results["paraphrased"]["latencies"])
    lat_unseen = calculate_latency_metrics(results["unseen"]["latencies"])

    report = {
        "metadata": {
            "total_evaluated": sum(r.get("total", 0) for r in results.values()),
            "total_eval_errors": sum(r.get("eval_errors", 0) for r in results.values()),
            "timestamp": time.time()
        },
        "dataset_sizes": {
            "canonical": results["canonical"]["total"],
            "paraphrased": results["paraphrased"]["total"],
            "unseen": results["unseen"]["total"],
            "adversarial": results["adversarial"]["total"],
            "polarity": results["polarity"]["total"]
        },
        "grounding": {
            "measured_unseen_grounded_actions": results["unseen"]["grounded"],
            "unseen_actionable_total": results["unseen"]["total"] - results["unseen"]["correctly_empty"]
        },
        "empty_response_semantics": {
            "correctly_empty": results["unseen"]["correctly_empty"],
            "incorrectly_empty": results["unseen"]["incorrectly_empty"]
        },
        "action_validity": {
            "canonical_valid_actions": results["canonical"]["valid_actions"],
            "paraphrase_valid_actions": results["paraphrased"]["valid_actions"]
        },
        "deeplink_resolution": {
            "catalog_matches": results["canonical"]["dl_catalog"],
            "validation_matches": results["canonical"]["dl_validation"] if "dl_validation" in results["canonical"] else 0,
            "verified_dummy_positives": results["canonical"]["dl_verified_dummy"],
            "unable_to_verify_provenance": results["canonical"]["dl_unable_verify"],
            "invalid_attempts": results["canonical"]["dl_invalid"]
        },
        "adversarial_safety": {
            "safely_rejected_422_or_empty": results["adversarial"]["safely_rejected"],
            "safely_ignored_malicious_content": results["adversarial"]["safely_ignored"],
            "unsafe_propagation": results["adversarial"]["unsafe_propagation"]
        },
        "polarity": {
            "semantic_correctness_count": results["polarity"]["correct"],
            "total_polarity_cases": results["polarity"]["total"]
        },
        "latency_ms": {
            "canonical": {"p50": lat_canon["p50"], "p95": lat_canon["p95"], "p99": lat_canon["p99"]},
            "paraphrase": {"p50": lat_para["p50"], "p95": lat_para["p95"], "p99": lat_para["p99"]},
            "unseen": {"p50": lat_unseen["p50"], "p95": lat_unseen["p95"], "p99": lat_unseen["p99"]}
        },
        "cache": {
            "canonical_hit_rate": (results["canonical"]["cache_hits"] / max(results["canonical"]["total"], 1)) * 100,
            "semantic_hit_rate": (results["paraphrased"]["cache_hits"] / max(results["paraphrased"]["total"], 1)) * 100
        }
    }

    report_path = WORKSPACE_ROOT / "eval" / "evaluation_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"Evaluation Complete. Report saved to {report_path}")

if __name__ == "__main__":
    run_evaluation()
