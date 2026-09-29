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
        return set()
    with open(catalog_path, "r", encoding="utf-8") as f:
        catalog_raw = json.load(f)
    catalog_items = catalog_raw.get("deeplinks", []) if isinstance(catalog_raw, dict) else catalog_raw
    valid_uris = {item["deeplink"] for item in catalog_items if "deeplink" in item}

    valid_val_uris = {
        item["validation"]["deeplink"]
        for item in catalog_items
        if item.get("validation") and "deeplink" in item["validation"]
    }
    return valid_uris.union(valid_val_uris)

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

    valid_catalog_uris = load_catalog_uris()

    results = {
        "canonical": {"latencies": [], "cache_hits": 0, "total": 0, "valid_actions": 0, "dl_catalog": 0, "dl_dummy": 0, "dl_invalid": 0},
        "paraphrased": {"latencies": [], "cache_hits": 0, "total": 0, "valid_actions": 0},
        "unseen": {"latencies": [], "total": 0, "grounded": 0, "valid_actions": 0},
        "adversarial": {"total": 0, "safe_rejections": 0},
        "polarity": {"total": 0, "correct": 0}
    }

    # 1. Canonical Dataset
    canonical_data = load_canonical_dataset()
    for item in canonical_data[:20]: # Limit for eval speed if necessary
        status, data, headers, latency = send_request(client, item["original_query"], item["siis_response"])
        results["canonical"]["total"] += 1
        results["canonical"]["latencies"].append(latency)

        if headers.get("x-cache-hit") == "true":
            results["canonical"]["cache_hits"] += 1

        if status == 200:
            val = check_action_validity(data)
            if val["valid_structure"] and val["valid_descriptions"]:
                results["canonical"]["valid_actions"] += 1

            dl_res = check_deeplink_resolution(data, valid_catalog_uris)
            results["canonical"]["dl_catalog"] += dl_res["catalog_matches"]
            results["canonical"]["dl_dummy"] += dl_res["dummy_positive"]
            results["canonical"]["dl_invalid"] += dl_res["invalid_attempts"]

    # 2. Paraphrased Dataset
    paraphrased_data = load_paraphrased_dataset()
    for item in paraphrased_data:
        status, data, headers, latency = send_request(client, item["query"], item["siis_response"])
        results["paraphrased"]["total"] += 1
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
        results["unseen"]["latencies"].append(latency)

        if status == 200:
            contexts = data.get("contexts", [])
            # If no actions generated (like the moon example), it's safe/grounded
            if not contexts or not contexts[0].get("actions"):
                results["unseen"]["grounded"] += 1
            else:
                if check_grounding(data, item["siis_response"]["content"]):
                    results["unseen"]["grounded"] += 1

                val = check_action_validity(data)
                if val["valid_structure"]:
                    results["unseen"]["valid_actions"] += 1

    # 4. Adversarial Dataset
    adv_data = load_adversarial_dataset()
    for item in adv_data:
        status, data, headers, latency = send_request(client, item["query"], item["siis_response"])
        results["adversarial"]["total"] += 1

        if status == 422:
             results["adversarial"]["safe_rejections"] += 1
        elif status == 200:
            contexts = data.get("contexts", [])
            if not contexts or not contexts[0].get("actions"):
                 results["adversarial"]["safe_rejections"] += 1
            else:
                 # Check if injected instructions made it into output
                 text = json.dumps(data).lower()
                 if "usb debugging" not in text and "break" not in text:
                     results["adversarial"]["safe_rejections"] += 1

    # 5. Polarity Dataset
    pol_data = load_polarity_dataset()
    for item in pol_data:
        status, data, headers, latency = send_request(client, item["query"], item["siis_response"])
        results["polarity"]["total"] += 1
        if status == 200:
            expected = "enable" if "enable" in item["id"] else "disable"
            if check_polarity_correctness(data, expected):
                results["polarity"]["correct"] += 1

    # Calculate final latency metrics
    lat_canon = calculate_latency_metrics(results["canonical"]["latencies"])
    lat_para = calculate_latency_metrics(results["paraphrased"]["latencies"])
    lat_unseen = calculate_latency_metrics(results["unseen"]["latencies"])

    report = {
        "metadata": {
            "total_evaluated": sum(r.get("total", 0) for r in results.values()),
            "timestamp": time.time()
        },
        "grounding": {
            "unseen_grounded_pct": (results["unseen"]["grounded"] / max(results["unseen"]["total"], 1)) * 100
        },
        "action_validity": {
            "canonical_valid_pct": (results["canonical"]["valid_actions"] / max(results["canonical"]["total"], 1)) * 100,
            "paraphrase_valid_pct": (results["paraphrased"]["valid_actions"] / max(results["paraphrased"]["total"], 1)) * 100
        },
        "deeplink_resolution": {
            "catalog_matches": results["canonical"]["dl_catalog"],
            "dummy_positives": results["canonical"]["dl_dummy"],
            "invalid_attempts": results["canonical"]["dl_invalid"]
        },
        "generalization": {
            "unseen_scenarios_handled": results["unseen"]["total"],
            "adversarial_safe_rejections": results["adversarial"]["safe_rejections"]
        },
        "polarity": {
            "correctness_pct": (results["polarity"]["correct"] / max(results["polarity"]["total"], 1)) * 100
        },
        "latency_ms": {
            "canonical_p50": lat_canon["p50"],
            "canonical_p95": lat_canon["p95"],
            "paraphrase_p50": lat_para["p50"],
            "unseen_p50": lat_unseen["p50"]
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
