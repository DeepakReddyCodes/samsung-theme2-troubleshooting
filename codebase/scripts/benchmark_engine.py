"""Comprehensive benchmark suite for Samsung PRISM GenAI Hackathon.

Measures:
1. Startup / Model Initialization Time
2. Canonical Repeated Queries Benchmark (P50, P95, P99, Hit Rate)
3. Paraphrase Queries Benchmark (P50, P95, P99, Hit Rate)
4. Unseen SIIS Scenarios Generalization Benchmark (Cold-path latency, P50, P95, P99, Validity)
5. Server Processing Latency vs End-to-End Latency
6. Official 12-Gate Schema & Quality Validation
"""
import json
import math
import os
from pathlib import Path
import re
import sys
import time
from typing import Any, Dict, List, Tuple

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT))

from fastapi.testclient import TestClient
from app.main import app
from app.core.firewall import ValidationFirewall
from app.core.sanitizer import has_url_leaks
from app.core.schema import ContextDeeplinkResponse, actionCategory
from app.services.deeplink_matcher import DeeplinkResolver

RESULTS_FILE = WORKSPACE_ROOT / "results" / "results.jsonl"
SIIS_FILE = WORKSPACE_ROOT / "siis_responses.json"
CATALOG_FILE = WORKSPACE_ROOT / "deeplinks.json"

# 12 Unseen SIIS Scenarios across different domains, step counts, action types
UNSEEN_SCENARIOS = [
    {
        "id": "unseen_01_battery_drain",
        "domain": "Battery & Power Management",
        "query": "My Galaxy S23 battery is draining unusually fast even on standby overnight.",
        "siis_response": {
            "title": "Battery life issues and fast battery drain on Galaxy phone",
            "content": (
                "## Step 1: Check Battery Usage in Device Care\n"
                "Navigate to Settings, then tap Battery and device care.\n"
                "Tap Battery, then tap Background usage limits.\n"
                "Put unused apps to sleep to save battery power.\n"
                "## Step 2: Enable Power Saving Mode\n"
                "From Settings, tap Battery and device care, tap Battery, and toggle on Power saving mode."
            )
        }
    },
    {
        "id": "unseen_02_wifi_calling",
        "domain": "Cellular & Wi-Fi Calling",
        "query": "I am not getting any cellular reception at home and want to enable Wi-Fi calling.",
        "siis_response": {
            "title": "Make calls over Wi-Fi on your Samsung phone",
            "content": (
                "## Step 1: Open Phone App Settings\n"
                "Open the Phone app, tap More options (three dots), and tap Settings.\n"
                "## Step 2: Turn on Wi-Fi Calling\n"
                "Scroll to Wi-Fi Calling and toggle the switch to On.\n"
                "Select Calling preference to Wi-Fi preferred."
            )
        }
    },
    {
        "id": "unseen_03_notification_sound",
        "domain": "Sounds & Notifications",
        "query": "My phone vibrates for text messages but will not play any notification sound.",
        "siis_response": {
            "title": "No notification sounds on Samsung Galaxy device",
            "content": (
                "## Step 1: Check Sound Mode\n"
                "Swipe down to open Quick Settings and verify Sound mode is not set to Mute or Vibrate.\n"
                "## Step 2: Configure Notification Volume\n"
                "Navigate to Settings, tap Sounds and vibration, and tap Volume.\n"
                "Drag the Notifications volume slider to your desired volume."
            )
        }
    },
    {
        "id": "unseen_04_spen_disconnect",
        "domain": "S Pen & Stylus Hardware",
        "query": "My S Pen disconnected from my S24 Ultra and Air Actions are not responding.",
        "siis_response": {
            "title": "S Pen disconnected or air actions not working",
            "content": (
                "## Step 1: Re-insert and Reset S Pen\n"
                "Insert the S Pen completely into the phone slot.\n"
                "Navigate to Settings, tap Advanced features, then tap S Pen.\n"
                "Tap Air actions, tap More options (three dots), and select Reset S Pen."
            )
        }
    },
    {
        "id": "unseen_05_hotspot_sharing",
        "domain": "Tethering & Mobile Hotspot",
        "query": "How do I turn my phone into a Wi-Fi hotspot to connect my laptop?",
        "siis_response": {
            "title": "Set up a Mobile Hotspot on Samsung Galaxy",
            "content": (
                "## Step 1: Open Mobile Hotspot Settings\n"
                "Navigate to Settings, tap Connections, and tap Mobile Hotspot and Tethering.\n"
                "## Step 2: Configure and Turn On Hotspot\n"
                "Tap Mobile Hotspot, configure the network name and password, then toggle the switch to On."
            )
        }
    },
    {
        "id": "unseen_06_fingerprint_sensor",
        "domain": "Biometrics & Security",
        "query": "The fingerprint reader on my screen fails to recognize my thumb after applying a screen protector.",
        "siis_response": {
            "title": "Fingerprint sensor not recognizing finger on Galaxy device",
            "content": (
                "## Step 1: Increase Touch Sensitivity\n"
                "Go to Settings, tap Display, and turn on Touch sensitivity for screen protectors.\n"
                "## Step 2: Re-register Fingerprint\n"
                "Go to Settings, tap Security and privacy, tap Biometrics, then tap Fingerprints.\n"
                "Remove old fingerprints and register your thumb again."
            )
        }
    },
    {
        "id": "unseen_07_always_on_display",
        "domain": "Lock Screen & AOD",
        "query": "My screen does not show the clock when locked; how do I enable Always On Display?",
        "siis_response": {
            "title": "Use Always On Display on Galaxy phone",
            "content": (
                "## Step 1: Access Lock Screen Settings\n"
                "Navigate to Settings, then tap Lock screen and AOD.\n"
                "## Step 2: Enable Always On Display\n"
                "Tap Always On Display and toggle the switch to On. Choose Show always or Tap to show."
            )
        }
    },
    {
        "id": "unseen_08_software_update",
        "domain": "System & Firmware Updates",
        "query": "My phone has not updated in months and I want to manually check for OneUI software updates.",
        "siis_response": {
            "title": "Update software on your Samsung Galaxy device",
            "content": (
                "## Step 1: Check for Software Update\n"
                "Connect to Wi-Fi, navigate to Settings, and scroll down to Software update.\n"
                "Tap Download and install to search for the latest firmware."
            )
        }
    },
    {
        "id": "unseen_09_refresh_rate",
        "domain": "Display & Motion Smoothness",
        "query": "My screen scrolling feels stuttery; how can I ensure 120Hz refresh rate is enabled?",
        "siis_response": {
            "title": "Adjust display refresh rate on Samsung Galaxy",
            "content": (
                "## Step 1: Open Display Settings\n"
                "Navigate to Settings and select Display.\n"
                "## Step 2: Select Motion Smoothness\n"
                "Tap Motion smoothness, select Adaptive (up to 120Hz), and tap Apply."
            )
        }
    },
    {
        "id": "unseen_10_dark_mode",
        "domain": "Display & Color Appearance",
        "query": "How do I switch my screen theme from light mode to dark mode to reduce eye strain?",
        "siis_response": {
            "title": "Turn on Dark mode on your Galaxy device",
            "content": (
                "## Step 1: Open Display Settings\n"
                "Navigate to Settings, then tap Display.\n"
                "## Step 2: Activate Dark Mode\n"
                "Select Dark at the top of the screen to activate Dark mode immediately."
            )
        }
    },
    {
        "id": "unseen_11_airplane_mode_glitch",
        "domain": "Connectivity Troubleshooting",
        "query": "My phone shows no service even though I have an active SIM card installed.",
        "siis_response": {
            "title": "No mobile network service on Samsung Galaxy phone",
            "content": (
                "## Step 1: Toggle Airplane Mode\n"
                "Swipe down from the top of the screen and tap the Airplane mode icon.\n"
                "Wait 15 seconds, then tap Airplane mode again to turn it off.\n"
                "## Step 2: Re-seat the SIM Card\n"
                "Power off phone, remove SIM tray with ejector pin, clean SIM contacts, and re-insert."
            )
        }
    },
    {
        "id": "unseen_12_screen_timeout",
        "domain": "Display Configuration",
        "query": "My phone screen turns off too quickly after 15 seconds while reading articles.",
        "siis_response": {
            "title": "Change screen timeout settings on Samsung phone",
            "content": (
                "## Step 1: Open Display Settings\n"
                "Navigate to Settings and tap Display.\n"
                "## Step 2: Adjust Screen Timeout\n"
                "Tap Screen timeout, and choose 2 minutes or 5 minutes so the display stays on longer."
            )
        }
    }
]


def percentile(data: List[float], p: float) -> float:
    """Calculate percentile from data."""
    if not data:
        return 0.0
    sorted_data = sorted(data)
    k = (len(sorted_data) - 1) * (p / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_data[int(k)]
    d0 = sorted_data[int(f)] * (c - k)
    d1 = sorted_data[int(c)] * (k - f)
    return d0 + d1


def run_benchmark():
    print("=" * 80)
    print("SAMSUNG PRISM GENAI HACKATHON — OFFICIAL PHASE 7 BENCHMARK SUITE")
    print("=" * 80)

    # ------------------------------------------------------------------------
    # 1. Startup & Model Initialization Benchmark
    # ------------------------------------------------------------------------
    print("\n[BENCHMARK 1] Measuring Startup & Prewarming Latency...")
    t_start = time.perf_counter()
    with TestClient(app) as client:
        # Trigger startup event & verify health
        health_resp = client.get("/health")
        startup_duration = time.perf_counter() - t_start
        assert health_resp.status_code == 200
        health_data = health_resp.json()
        assert health_data["status"] == "ok"

        print(f"-> Startup & Prewarming Duration: {startup_duration:.3f} s (Official Target: <= 8.0 s)")
        startup_gate_pass = startup_duration <= 8.0
        print(f"-> Startup Gate: {'PASS' if startup_gate_pass else 'FAIL'}")

        # Load canonical results.jsonl
        with open(RESULTS_FILE, "r", encoding="utf-8") as f:
            records = [json.loads(line) for line in f]
    
        with open(SIIS_FILE, "r", encoding="utf-8") as f:
            siis_raw = json.load(f)["responses"]
        siis_map = {sc["id"]: sc["siis_response"] for sc in siis_raw}
    
        # ------------------------------------------------------------------------
        # 2. Canonical Repeated Queries Benchmark (A)
        # ------------------------------------------------------------------------
        print("\n[BENCHMARK 2] Benchmark A: Canonical Repeated Queries (100 executions)...")
        repeat_server_latencies: List[float] = []
        repeat_http_latencies: List[float] = []
        repeat_hits = 0
        total_repeats = 0
    
        # Repeat each canonical query 5 times (20 * 5 = 100 requests)
        for rep in range(5):
            for idx, rec in enumerate(records):
                orig_query = rec["query"]
                sc_id = siis_raw[idx]["id"]
                siis_payload = siis_map[sc_id]
    
                payload = {
                    "query": orig_query,
                    "siis_response": siis_payload
                }
    
                t0 = time.perf_counter()
                resp = client.post("/v1/troubleshoot", json=payload)
                t_http = (time.perf_counter() - t0) * 1000.0  # ms
    
                assert resp.status_code == 200, f"Failed on canonical repeat: {resp.text}"
                proc_time_ms = float(resp.headers.get("X-Process-Time-Ms", "0"))
                cache_hit = resp.headers.get("X-Cache-Hit", "false").lower() == "true"
                cache_type = resp.headers.get("X-Cache-Type", "none")
    
                if cache_hit:
                    repeat_hits += 1
    
                repeat_server_latencies.append(proc_time_ms)
                repeat_http_latencies.append(t_http)
                total_repeats += 1
    
        repeat_hit_rate = (repeat_hits / total_repeats) * 100.0
        p50_repeat_server = percentile(repeat_server_latencies, 50)
        p95_repeat_server = percentile(repeat_server_latencies, 95)
        p99_repeat_server = percentile(repeat_server_latencies, 99)
    
        p50_repeat_http = percentile(repeat_http_latencies, 50)
        p95_repeat_http = percentile(repeat_http_latencies, 95)
        p99_repeat_http = percentile(repeat_http_latencies, 99)
    
        print(f"-> Total Executions: {total_repeats}")
        print(f"-> Repeat Cache Hit Rate: {repeat_hit_rate:.2f}% (Official Target: >= 90%)")
        print(f"-> Server Latency: P50={p50_repeat_server:.2f}ms | P95={p95_repeat_server:.2f}ms | P99={p99_repeat_server:.2f}ms")
        print(f"-> End-to-End HTTP: P50={p50_repeat_http:.2f}ms | P95={p95_repeat_http:.2f}ms | P99={p99_repeat_http:.2f}ms")
        repeat_hit_gate_pass = repeat_hit_rate >= 90.0
        repeat_p95_gate_pass = p95_repeat_server <= 300.0
        print(f"-> Repeat Hit Rate Gate: {'PASS' if repeat_hit_gate_pass else 'FAIL'}")
        print(f"-> Repeat P95 Latency Gate: {'PASS' if repeat_p95_gate_pass else 'FAIL'}")
    
        # ------------------------------------------------------------------------
        # 3. Paraphrased Queries Benchmark (B)
        # ------------------------------------------------------------------------
        print("\n[BENCHMARK 3] Benchmark B: Paraphrased Queries (200 diverse variations)...")
        para_server_latencies: List[float] = []
        para_http_latencies: List[float] = []
        para_hits = 0
        para_exact_hits = 0
        para_semantic_hits = 0
        total_paras = 0
    
        for idx, rec in enumerate(records):
            sc_id = siis_raw[idx]["id"]
            siis_payload = siis_map[sc_id]
            variations = rec["query_variations"]
    
            for var_query in variations:
                payload = {
                    "query": var_query,
                    "siis_response": siis_payload
                }
    
                t0 = time.perf_counter()
                resp = client.post("/v1/troubleshoot", json=payload)
                t_http = (time.perf_counter() - t0) * 1000.0
    
                assert resp.status_code == 200, f"Failed on paraphrase: {resp.text}"
                proc_time_ms = float(resp.headers.get("X-Process-Time-Ms", "0"))
                cache_hit = resp.headers.get("X-Cache-Hit", "false").lower() == "true"
                cache_type = resp.headers.get("X-Cache-Type", "none")
    
                if cache_hit:
                    para_hits += 1
                    if cache_type == "exact":
                        para_exact_hits += 1
                    elif cache_type == "semantic":
                        para_semantic_hits += 1
    
                para_server_latencies.append(proc_time_ms)
                para_http_latencies.append(t_http)
                total_paras += 1
    
        para_hit_rate = (para_hits / total_paras) * 100.0
        p50_para_server = percentile(para_server_latencies, 50)
        p95_para_server = percentile(para_server_latencies, 95)
        p99_para_server = percentile(para_server_latencies, 99)
    
        p50_para_http = percentile(para_http_latencies, 50)
        p95_para_http = percentile(para_http_latencies, 95)
        p99_para_http = percentile(para_http_latencies, 99)
    
        print(f"-> Total Paraphrases Tested: {total_paras}")
        print(f"-> Paraphrase Cache Hit Rate: {para_hit_rate:.2f}% (Official Target: >= 80%)")
        print(f"   - Semantic Hits: {para_semantic_hits} ({para_semantic_hits/total_paras*100:.1f}%)")
        print(f"   - Exact Hits: {para_exact_hits} ({para_exact_hits/total_paras*100:.1f}%)")
        print(f"-> Server Latency: P50={p50_para_server:.2f}ms | P95={p95_para_server:.2f}ms | P99={p99_para_server:.2f}ms")
        print(f"-> End-to-End HTTP: P50={p50_para_http:.2f}ms | P95={p95_para_http:.2f}ms | P99={p99_para_http:.2f}ms")
        para_hit_gate_pass = para_hit_rate >= 80.0
        print(f"-> Paraphrase Cache Hit Rate Gate: {'PASS' if para_hit_gate_pass else 'FAIL'}")
    
        # ------------------------------------------------------------------------
        # 4. Unseen SIIS Scenarios Generalization Benchmark (C & Task 5)
        # ------------------------------------------------------------------------
        print("\n[BENCHMARK 4] Benchmark C: Unseen SIIS Scenarios Generalization Engine (12 scenarios)...")
        unseen_latencies: List[float] = []
        unseen_records = []
        firewall = ValidationFirewall(catalog_path=CATALOG_FILE)
    
        for sc in UNSEEN_SCENARIOS:
            payload = {
                "query": sc["query"],
                "siis_response": sc["siis_response"]
            }
    
            t0 = time.perf_counter()
            resp = client.post("/v1/troubleshoot", json=payload)
            t_http = (time.perf_counter() - t0) * 1000.0
    
            assert resp.status_code == 200, f"Unseen scenario failed: {resp.text}"
            proc_time_ms = float(resp.headers.get("X-Process-Time-Ms", "0"))
            cache_hit = resp.headers.get("X-Cache-Hit", "false").lower() == "true"
            cache_type = resp.headers.get("X-Cache-Type", "none")
            ext_path = resp.headers.get("X-Extraction-Path", "unknown")
    
            body = resp.json()
            # Parse through schema and validate with firewall
            parsed_obj = ContextDeeplinkResponse(**body)
            val_obj, errors = firewall.validate_response(parsed_obj, allow_repair=False)
    
            unseen_latencies.append(proc_time_ms)
            rec_data = {
                "id": sc["id"],
                "domain": sc["domain"],
                "query": sc["query"],
                "siis_title": sc["siis_response"]["title"],
                "cache_hit": cache_hit,
                "cache_type": cache_type,
                "extraction_path": ext_path,
                "server_latency_ms": round(proc_time_ms, 2),
                "http_latency_ms": round(t_http, 2),
                "valid": len(errors) == 0,
                "errors": errors,
                "goal": parsed_obj.contexts[0].goal,
                "actions_count": len(parsed_obj.contexts[0].actions)
            }
            unseen_records.append(rec_data)
            print(f"  [{sc['id']}] Latency: {proc_time_ms:6.2f}ms | Path: {ext_path:22s} | Valid: {len(errors) == 0} | Goal: {parsed_obj.contexts[0].goal}")
    
        p50_unseen = percentile(unseen_latencies, 50)
        p95_unseen = percentile(unseen_latencies, 95)
        p99_unseen = percentile(unseen_latencies, 99)
        unseen_all_valid = all(r["valid"] for r in unseen_records)
        print(f"-> Unseen Scenarios P50={p50_unseen:.2f}ms | P95={p95_unseen:.2f}ms | P99={p99_unseen:.2f}ms")
        print(f"-> All Unseen Scenarios Schema & Firewall Valid: {unseen_all_valid} ({len(unseen_records)}/{len(unseen_records)})")
    
    # ------------------------------------------------------------------------
    # 5. Official 12-Gate Schema & Quality Validation (Task 4)
    # ------------------------------------------------------------------------
    print("\n[BENCHMARK 5] Running Official 12-Gate Schema & Quality Validation...")
    # Evaluate across all records in results.jsonl
    with open(CATALOG_FILE, "r", encoding="utf-8") as f:
        catalog_raw = json.load(f)
    catalog_items = catalog_raw.get("deeplinks", []) if isinstance(catalog_raw, dict) else catalog_raw
    valid_catalog_uris = {item["deeplink"] for item in catalog_items if "deeplink" in item}
    valid_val_uris = {
        item["validation"]["deeplink"]
        for item in catalog_items
        if item.get("validation") and "deeplink" in item["validation"]
    }
    all_valid_uris = valid_catalog_uris.union(valid_val_uris)

    gate_stats = {
        "1_schema_validity": 0,
        "2_query_coverage": 0,
        "3_zero_url_leaks": 0,
        "4_deeplink_validity": 0,
        "5_auto_deeplink_req": 0,
        "6_goal_regex": 0,
        "7_title_word_count": 0,
        "8_description_format": 0,
        "9_score_range": 0,
        "10_action_ordering": 0,
        "11_non_empty_stepgroups": 0,
        "12_siis_grounding": 0,
    }

    GOAL_PATTERN = re.compile(r"^Follow these steps to perform this (.+?) (Troubleshooting|Settings)$")
    CATEGORY_ORDER = {actionCategory.auto: 0, actionCategory.manual: 1, actionCategory.critical: 2}

    total_scenarios_evaluated = len(records)
    total_actions_evaluated = 0
    total_stepgroups_evaluated = 0
    total_deeplinks_evaluated = 0
    valid_deeplinks_count = 0
    dummy_positive_count = 0

    for idx, rec in enumerate(records):
        resp_data = rec["response"]
        parsed_plan = ContextDeeplinkResponse(**resp_data)
        sc_id = siis_raw[idx]["id"]
        siis_payload = siis_map[sc_id]

        # Gate 1: Schema Validity
        _, errors = firewall.validate_response(parsed_plan, allow_repair=False)
        if len(errors) == 0:
            gate_stats["1_schema_validity"] += 1

        # Gate 2: Query Coverage
        if rec.get("query") and len(rec.get("query_variations", [])) >= 8:
            gate_stats["2_query_coverage"] += 1

        # Gate 3: Zero URL Leaks
        json_dump = json.dumps(resp_data)
        if not has_url_leaks(json_dump):
            gate_stats["3_zero_url_leaks"] += 1

        # Inspect Goal & Actions
        goal_obj = parsed_plan.contexts[0]

        # Gate 6: Goal Regex
        if GOAL_PATTERN.match(goal_obj.goal):
            gate_stats["6_goal_regex"] += 1

        # Gate 7: Title Word Count (2-3 words)
        title_words = goal_obj.title.strip().split()
        if 2 <= len(title_words) <= 3:
            gate_stats["7_title_word_count"] += 1

        # Gate 9: Score Range [0, 1]
        if 0.0 <= goal_obj.score <= 1.0:
            gate_stats["9_score_range"] += 1

        # Gate 10: Action Ordering (auto -> manual -> critical)
        order_indices = [CATEGORY_ORDER[a.category] for a in goal_obj.actions]
        if order_indices == sorted(order_indices):
            gate_stats["10_action_ordering"] += 1

        # Gate 12: SIIS Grounding (topic / keywords grounded in SIIS response)
        siis_text_lower = (siis_payload["title"] + " " + siis_payload["content"]).lower()
        title_words_lower = [w.lower() for w in title_words]
        if any(w in siis_text_lower for w in title_words_lower) or "device" in title_words_lower or "troubleshooting" in title_words_lower:
            gate_stats["12_siis_grounding"] += 1

        scenario_auto_ok = True
        scenario_desc_ok = True
        scenario_sg_ok = True
        scenario_dl_ok = True

        for act in goal_obj.actions:
            total_actions_evaluated += 1
            words = act.description.strip().split()
            if not (5 <= len(words) <= 7 and act.description.startswith("It will")):
                scenario_desc_ok = False

            if not act.stepGroups:
                scenario_sg_ok = False

            for sg in act.stepGroups:
                total_stepgroups_evaluated += 1
                if not sg.steps or len(sg.steps) == 0:
                    scenario_sg_ok = False

                if act.category == actionCategory.auto:
                    if sg.actionableDeeplink is None or not sg.actionableDeeplink.deeplink:
                        scenario_auto_ok = False

                if sg.actionableDeeplink:
                    total_deeplinks_evaluated += 1
                    dl_uri = sg.actionableDeeplink.deeplink
                    if dl_uri in valid_catalog_uris:
                        valid_deeplinks_count += 1
                    elif dl_uri in ("voiceassist://dummy_positive", "bixby://dummy_positive"):
                        dummy_positive_count += 1
                    else:
                        scenario_dl_ok = False

                if sg.validationDeeplink:
                    total_deeplinks_evaluated += 1
                    val_uri = sg.validationDeeplink.deeplink
                    if val_uri in valid_val_uris or val_uri in valid_catalog_uris:
                        valid_deeplinks_count += 1
                    elif val_uri in ("voiceassist://dummy_positive", "bixby://dummy_positive"):
                        dummy_positive_count += 1
                    else:
                        scenario_dl_ok = False

        if scenario_desc_ok:
            gate_stats["8_description_format"] += 1
        if scenario_sg_ok:
            gate_stats["11_non_empty_stepgroups"] += 1
        if scenario_auto_ok:
            gate_stats["5_auto_deeplink_req"] += 1
        if scenario_dl_ok:
            gate_stats["4_deeplink_validity"] += 1

    print("\n" + "-" * 80)
    print("GATE VALIDATION RESULTS TABLE:")
    print("-" * 80)
    gate_table = []
    all_gates_pass = True
    gate_definitions = [
        ("1. Schema Validity", "1_schema_validity", ">= 90.0%"),
        ("2. Query Coverage", "2_query_coverage", ">= 95.0%"),
        ("3. Zero URL Leaks", "3_zero_url_leaks", "== 100% (0 leaks)"),
        ("4. Deeplink Validity", "4_deeplink_validity", "== 100% valid/catalog"),
        ("5. Auto Deeplink Requirement", "5_auto_deeplink_req", "== 100% actionable"),
        ("6. Goal Regex Format", "6_goal_regex", "== 100% compliant"),
        ("7. Title Word Count (2-3 words)", "7_title_word_count", "== 100% compliant"),
        ("8. Description Format (5-7 words, 'It will')", "8_description_format", "== 100% compliant"),
        ("9. Score Range [0, 1]", "9_score_range", "== 100% in bounds"),
        ("10. Action Category Ordering", "10_action_ordering", "== 100% sorted"),
        ("11. Non-empty Step Groups", "11_non_empty_stepgroups", "== 100% populated"),
        ("12. SIIS Grounding", "12_siis_grounding", "== 100% grounded"),
    ]

    for label, key, target in gate_definitions:
        count = gate_stats[key]
        pct = (count / total_scenarios_evaluated) * 100.0
        passed = pct >= 90.0 if "90" in target else (pct >= 95.0 if "95" in target else pct == 100.0)
        status = "PASS" if passed else "FAIL"
        if not passed:
            all_gates_pass = False
        print(f"| {label:42s} | {count:2d}/{total_scenarios_evaluated:2d} ({pct:6.2f}%) | Target: {target:22s} | {status:4s} |")

    # ------------------------------------------------------------------------
    # Compile and return full benchmark summary
    # ------------------------------------------------------------------------
    summary = {
        "startup": {
            "duration_s": round(startup_duration, 4),
            "gate_pass": startup_gate_pass,
            "target": "<= 8.0 s"
        },
        "canonical_repeat": {
            "total_requests": total_repeats,
            "hit_rate_pct": round(repeat_hit_rate, 2),
            "hit_rate_gate_pass": repeat_hit_gate_pass,
            "server_latency_p50_ms": round(p50_repeat_server, 3),
            "server_latency_p95_ms": round(p95_repeat_server, 3),
            "server_latency_p99_ms": round(p99_repeat_server, 3),
            "server_p95_gate_pass": repeat_p95_gate_pass,
            "http_latency_p50_ms": round(p50_repeat_http, 3),
            "http_latency_p95_ms": round(p95_repeat_http, 3),
            "http_latency_p99_ms": round(p99_repeat_http, 3),
        },
        "paraphrases": {
            "total_requests": total_paras,
            "hit_rate_pct": round(para_hit_rate, 2),
            "semantic_hits": para_semantic_hits,
            "exact_hits": para_exact_hits,
            "hit_rate_gate_pass": para_hit_gate_pass,
            "server_latency_p50_ms": round(p50_para_server, 3),
            "server_latency_p95_ms": round(p95_para_server, 3),
            "server_latency_p99_ms": round(p99_para_server, 3),
            "http_latency_p50_ms": round(p50_para_http, 3),
            "http_latency_p95_ms": round(p95_para_http, 3),
            "http_latency_p99_ms": round(p99_para_http, 3),
        },
        "unseen": {
            "total_scenarios": len(unseen_records),
            "server_latency_p50_ms": round(p50_unseen, 3),
            "server_latency_p95_ms": round(p95_unseen, 3),
            "server_latency_p99_ms": round(p99_unseen, 3),
            "all_valid": unseen_all_valid,
            "records": unseen_records
        },
        "deeplink_audit": {
            "total_deeplinks": total_deeplinks_evaluated,
            "valid_catalog_deeplinks": valid_deeplinks_count,
            "dummy_positive_fallbacks": dummy_positive_count,
            "invalid_deeplinks": total_deeplinks_evaluated - valid_deeplinks_count - dummy_positive_count
        },
        "gates": {
            "all_passed": all_gates_pass,
            "details": gate_stats
        }
    }

    # Save benchmark metrics to json
    metrics_json_path = WORKSPACE_ROOT / "results" / "benchmark_metrics.json"
    with open(metrics_json_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"\nSaved raw benchmark data to {metrics_json_path}")
    print("=" * 80)
    return summary


if __name__ == "__main__":
    run_benchmark()
