"""Comprehensive URL Leak and Deeplink Integrity Audit for Samsung PRISM Hackathon.

Tasks:
- Task 6: Zero URL Leak Audit across repository artifacts and API data.
- Task 7: Deeplink Integrity Audit ensuring verbatim catalog matching and preservation.
"""
import json
from pathlib import Path
import re
import sys
from typing import Any, Dict, List, Set

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT))

from app.core.sanitizer import has_url_leaks, find_url_leaks
from app.core.schema import ContextDeeplinkResponse

CATALOG_PATH = WORKSPACE_ROOT / "deeplinks.json"
RESULTS_FILE = WORKSPACE_ROOT / "results" / "results.jsonl"


def audit_url_leaks() -> Dict[str, Any]:
    print("=" * 70)
    print("TASK 6: URL LEAK AUDIT")
    print("=" * 70)

    files_to_scan = [
        RESULTS_FILE,
        WORKSPACE_ROOT / "sample_output.json",
        WORKSPACE_ROOT / "siis_responses.json",
        WORKSPACE_ROOT / "frontend" / "src" / "data" / "canonical_scenarios.ts",
    ]

    leak_report = {}
    total_leaks = 0

    for file_path in files_to_scan:
        if not file_path.exists():
            continue
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
        except UnicodeDecodeError:
            continue

        leaks = find_url_leaks(content)
        if leaks:
            leak_report[str(file_path.relative_to(WORKSPACE_ROOT))] = leaks
            total_leaks += len(leaks)

    # Also scan live API responses across canonical queries
    from fastapi.testclient import TestClient
    from app.main import app
    with open(WORKSPACE_ROOT / "siis_responses.json", "r", encoding="utf-8") as f:
        siis_scenarios = json.load(f)["responses"]

    api_responses_scanned = 0
    with TestClient(app) as client:
        for sc in siis_scenarios:
            api_responses_scanned += 1
            resp = client.post("/v1/troubleshoot", json={
                "query": sc["original_query"],
                "siis_response": sc["siis_response"]
            })
            assert resp.status_code == 200, f"Error {resp.status_code}: {resp.text}"
            resp_text = resp.text
            leaks = find_url_leaks(resp_text)
            if leaks:
                leak_report[f"api_response_{sc['id']}"] = leaks
                total_leaks += len(leaks)

    print(f"Scanned {len(files_to_scan)} data files and {api_responses_scanned} live API responses.")
    print(f"Total Prohibited Web URL Leaks Detected: {total_leaks}")
    if total_leaks > 0:
        for f, lks in leak_report.items():
            print(f"  [LEAK] {f}: {lks}")
    else:
        print("  -> ZERO URL LEAKS DETECTED! (Target: 0) — PASS")

    return {
        "files_scanned": len(files_to_scan),
        "total_leaks": total_leaks,
        "details": leak_report,
        "pass": total_leaks == 0
    }


def audit_deeplinks() -> Dict[str, Any]:
    print("\n" + "=" * 70)
    print("TASK 7: DEEPLINK INTEGRITY AUDIT")
    print("=" * 70)

    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        catalog_data = json.load(f)

    catalog_entries = catalog_data.get("deeplinks", []) if isinstance(catalog_data, dict) else catalog_data
    catalog_uris = {}
    validation_uris = {}
    for entry in catalog_entries:
        uri = entry.get("deeplink")
        if uri:
            catalog_uris[uri] = entry
        val = entry.get("validation")
        if val and "deeplink" in val:
            validation_uris[val["deeplink"]] = val

    print(f"Loaded {len(catalog_uris)} actionable URIs and {len(validation_uris)} validation URIs from {CATALOG_PATH.name}")

    with open(RESULTS_FILE, "r", encoding="utf-8") as f:
        records = [json.loads(line) for line in f]

    total_returned_deeplinks = 0
    valid_catalog_deeplinks = 0
    dummy_positive_count = 0
    invalid_deeplinks = []
    validation_objects_verified = 0

    for idx, rec in enumerate(records):
        query = rec["query"]
        plan = ContextDeeplinkResponse(**rec["response"])

        for context in plan.contexts:
            for action in context.actions:
                for sg in action.stepGroups:
                    # Check actionable deeplink
                    if sg.actionableDeeplink:
                        total_returned_deeplinks += 1
                        act_uri = sg.actionableDeeplink.deeplink
                        if act_uri in ("voiceassist://dummy_positive", "bixby://dummy_positive"):
                            dummy_positive_count += 1
                        elif act_uri in catalog_uris:
                            valid_catalog_deeplinks += 1
                            cat_entry = catalog_uris[act_uri]
                            # Check verbatim URI
                            assert act_uri == cat_entry["deeplink"]
                        else:
                            invalid_deeplinks.append({
                                "scenario_query": query[:40],
                                "type": "actionable",
                                "uri": act_uri
                            })

                    # Check validation deeplink
                    if sg.validationDeeplink:
                        total_returned_deeplinks += 1
                        val_uri = sg.validationDeeplink.deeplink
                        if val_uri in ("voiceassist://dummy_positive", "bixby://dummy_positive"):
                            dummy_positive_count += 1
                        elif val_uri in validation_uris or val_uri in catalog_uris:
                            valid_catalog_deeplinks += 1
                            validation_objects_verified += 1
                        else:
                            invalid_deeplinks.append({
                                "scenario_query": query[:40],
                                "type": "validation",
                                "uri": val_uri
                            })

    print(f"Total Returned Deeplinks in results.jsonl: {total_returned_deeplinks}")
    print(f"Valid Catalog Deeplinks (Exact Verbatim Match): {valid_catalog_deeplinks}")
    print(f"Dummy Positive Fallbacks: {dummy_positive_count}")
    print(f"Invalid / Fabricated Deeplinks: {len(invalid_deeplinks)}")
    print(f"Validation Objects Verified: {validation_objects_verified}")

    passed = len(invalid_deeplinks) == 0 and valid_catalog_deeplinks > 0
    print(f"Deeplink Integrity Gate: {'PASS' if passed else 'FAIL'}")

    return {
        "total_returned": total_returned_deeplinks,
        "valid_catalog": valid_catalog_deeplinks,
        "dummy_positive": dummy_positive_count,
        "invalid_count": len(invalid_deeplinks),
        "invalid_details": invalid_deeplinks,
        "pass": passed
    }


def main():
    leak_res = audit_url_leaks()
    dl_res = audit_deeplinks()
    assert leak_res["pass"]
    assert dl_res["pass"]
    print("\nAudits Completed Successfully with 100% PASS.")


if __name__ == "__main__":
    main()
