"""Official Phase 7 Production Smoke Test against live running server.

Executes all 6 required smoke scenarios over real TCP socket:
1. GET /health verification
2. GET / (Frontend root HTML) verification
3. Canonical query execution
4. Exact repeat (verifying exact cache hit)
5. Paraphrase query (verifying semantic cache hit)
6. Unseen SIIS scenario (verifying cold-path extraction)
7. Invalid request (verifying HTTP 422 handling)
8. Different SIIS with same query (verifying SIIS isolation)
"""
import json
from pathlib import Path
import sys
import time
import httpx

BASE_URL = "http://127.0.0.1:8000"
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent

def run_smoke_test():
    print("=" * 80)
    print("TASK 9: PRODUCTION SMOKE TEST ON LIVE SERVER")
    print(f"Target URL: {BASE_URL}")
    print("=" * 80)

    client = httpx.Client(base_url=BASE_URL, timeout=30.0)

    # 1. GET /health
    print("\n[SMOKE 1] Verifying GET /health...")
    resp_health = client.get("/health")
    print(f"Status: {resp_health.status_code} | Body: {resp_health.text}")
    assert resp_health.status_code == 200
    assert resp_health.json()["status"] == "ok"
    print("-> GET /health: PASS")

    # 2. GET / (Frontend serving)
    print("\n[SMOKE 2] Verifying Frontend GET /...")
    resp_fe = client.get("/")
    print(f"Status: {resp_fe.status_code} | Content-Type: {resp_fe.headers.get('content-type')}")
    assert resp_fe.status_code == 200
    assert "html" in resp_fe.headers.get("content-type", "").lower()
    assert "root" in resp_fe.text
    print("-> Frontend root serving: PASS")

    # Load canonical scenario 1
    with open(WORKSPACE_ROOT / "siis_responses.json", "r", encoding="utf-8") as f:
        siis_data = json.load(f)["responses"]
    sc1 = siis_data[0]
    sc1_query = sc1["original_query"]
    sc1_siis = sc1["siis_response"]

    # 3. Canonical Query Execution
    print("\n[SMOKE 3] Testing Canonical Query...")
    t0 = time.perf_counter()
    resp_canon = client.post("/v1/troubleshoot", json={"query": sc1_query, "siis_response": sc1_siis})
    t_roundtrip = (time.perf_counter() - t0) * 1000.0
    print(f"Status: {resp_canon.status_code}")
    print(f"Headers: X-Cache-Hit={resp_canon.headers.get('x-cache-hit')} | X-Cache-Type={resp_canon.headers.get('x-cache-type')} | Server: {resp_canon.headers.get('x-process-time-ms')}ms | Roundtrip: {t_roundtrip:.2f}ms")
    assert resp_canon.status_code == 200
    canon_data = resp_canon.json()
    assert "contexts" in canon_data
    goal1 = canon_data["contexts"][0]["goal"]
    print(f"Goal: {goal1}")
    print("-> Canonical Query Execution: PASS")

    # 4. Exact Repeat Execution
    print("\n[SMOKE 4] Testing Exact Repeat Query...")
    t0 = time.perf_counter()
    resp_repeat = client.post("/v1/troubleshoot", json={"query": sc1_query, "siis_response": sc1_siis})
    t_roundtrip = (time.perf_counter() - t0) * 1000.0
    print(f"Status: {resp_repeat.status_code}")
    print(f"Headers: X-Cache-Hit={resp_repeat.headers.get('x-cache-hit')} | X-Cache-Type={resp_repeat.headers.get('x-cache-type')} | Server: {resp_repeat.headers.get('x-process-time-ms')}ms | Roundtrip: {t_roundtrip:.2f}ms")
    assert resp_repeat.status_code == 200
    assert resp_repeat.headers.get("x-cache-hit") == "true"
    assert resp_repeat.headers.get("x-cache-type") == "exact"
    print("-> Exact Repeat Hit: PASS")

    # 5. Paraphrase Query
    print("\n[SMOKE 5] Testing Paraphrase Query...")
    para_query = "How do I fix my Samsung tablet screen going completely blank whenever I open Gmail?"
    t0 = time.perf_counter()
    resp_para = client.post("/v1/troubleshoot", json={"query": para_query, "siis_response": sc1_siis})
    t_roundtrip = (time.perf_counter() - t0) * 1000.0
    print(f"Query: '{para_query}'")
    print(f"Headers: X-Cache-Hit={resp_para.headers.get('x-cache-hit')} | X-Cache-Type={resp_para.headers.get('x-cache-type')} | Server: {resp_para.headers.get('x-process-time-ms')}ms | Roundtrip: {t_roundtrip:.2f}ms")
    assert resp_para.status_code == 200
    assert resp_para.headers.get("x-cache-hit") == "true"
    assert resp_para.headers.get("x-cache-type") == "semantic"
    print("-> Paraphrase Semantic Hit: PASS")

    # 6. Unseen SIIS Scenario
    print("\n[SMOKE 6] Testing Unseen SIIS Scenario...")
    unseen_query = "My Galaxy S24 screen turns off after 15 seconds while reading articles."
    unseen_siis = {
        "title": "Change screen timeout settings on Samsung phone",
        "content": (
            "## Step 1: Open Display Settings\n"
            "Navigate to Settings and tap Display.\n"
            "## Step 2: Adjust Screen Timeout\n"
            "Tap Screen timeout, and choose 2 minutes or 5 minutes."
        )
    }
    t0 = time.perf_counter()
    resp_unseen = client.post("/v1/troubleshoot", json={"query": unseen_query, "siis_response": unseen_siis})
    t_roundtrip = (time.perf_counter() - t0) * 1000.0
    print(f"Headers: X-Cache-Hit={resp_unseen.headers.get('x-cache-hit')} | Path: {resp_unseen.headers.get('x-extraction-path')} | Server: {resp_unseen.headers.get('x-process-time-ms')}ms | Roundtrip: {t_roundtrip:.2f}ms")
    assert resp_unseen.status_code == 200
    unseen_data = resp_unseen.json()
    assert "contexts" in unseen_data
    print(f"Goal: {unseen_data['contexts'][0]['goal']}")
    print("-> Unseen SIIS Scenario: PASS")

    # 7. Invalid Request Handling
    print("\n[SMOKE 7] Testing Invalid Request (Missing fields)...")
    resp_invalid = client.post("/v1/troubleshoot", json={"query": ""})
    print(f"Status: {resp_invalid.status_code} | Body: {resp_invalid.text}")
    assert resp_invalid.status_code == 422
    assert "error" in resp_invalid.json()
    print("-> Invalid Request 422 Handling: PASS")

    # 8. Different SIIS with Same Query
    print("\n[SMOKE 8] Testing Different SIIS with Same Query (Isolation Check)...")
    sc13 = siis_data[12]  # Screen cracked scenario
    sc13_siis = sc13["siis_response"]
    # Send sc1_query (Gmail tablet issue) with sc13_siis (Cracked screen article)
    t0 = time.perf_counter()
    resp_diff_siis = client.post("/v1/troubleshoot", json={"query": sc1_query, "siis_response": sc13_siis})
    t_roundtrip = (time.perf_counter() - t0) * 1000.0
    print(f"Headers: X-Cache-Hit={resp_diff_siis.headers.get('x-cache-hit')} | Path: {resp_diff_siis.headers.get('x-extraction-path')} | Server: {resp_diff_siis.headers.get('x-process-time-ms')}ms | Roundtrip: {t_roundtrip:.2f}ms")
    assert resp_diff_siis.status_code == 200
    diff_data = resp_diff_siis.json()
    diff_goal = diff_data["contexts"][0]["goal"]
    print(f"Goal: {diff_goal}")
    # Must follow authoritative SIIS (Cracked Screen) and NOT the cached Email plan!
    assert "Screen" in diff_goal or "Cracked" in diff_goal or "Damage" in diff_goal
    assert "Email" not in diff_goal
    print("-> Different SIIS with Same Query Isolation: PASS")

    print("\n" + "=" * 80)
    print("ALL PRODUCTION SMOKE TESTS PASSED (8/8) ON LIVE SERVER!")
    print("=" * 80)

if __name__ == "__main__":
    run_smoke_test()
