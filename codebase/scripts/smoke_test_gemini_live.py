"""Live Gemini Two-Stage Production Smoke Test.

Executes real cloud LLM queries against Google GenAI API:
1. Canonical complaint
2. Paraphrased complaint
3. Unseen SIIS-backed complaint

Measures and records:
- model
- success/failure
- latency (ms)
- whether structured output parsed
- whether grounding passed
- number of actions
- deeplink resolution result

Security: Reads GEMINI_API_KEY strictly from environment / .env. Never prints or logs the key.
"""
import json
import os
from pathlib import Path
import time
from dotenv import load_dotenv

# Load environment
WORKSPACE_DIR = Path(__file__).resolve().parent.parent
import sys
sys.path.insert(0, str(WORKSPACE_DIR))
load_dotenv()
load_dotenv(WORKSPACE_DIR / ".env")
load_dotenv(WORKSPACE_DIR.parent / ".env")

from app.core.schema import ContextDeeplinkResponse
from app.services.extractor.engine import ColdPathExtractionEngine
from app.services.extractor.gemini_extractor import GeminiExtractor
from app.services.query_enrichment import QueryEnricher
from app.services.query_enrichment.gemini_enricher import GeminiQueryEnricher


def run_live_gemini_smoke():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("[ERROR] GEMINI_API_KEY not found in environment or .env file.")
        return False

    model_name = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
    print("=" * 80)
    print("SAMSUNG PRISM THEME 2 — LIVE GEMINI TWO-STAGE INTEGRATION SMOKE TEST")
    print(f"Model Configured: {model_name}")
    print(f"API Key Present: YES (len={len(api_key)}, masked=***)")
    print("=" * 80)

    # Initialize live two-stage engine
    stage1 = GeminiQueryEnricher(api_key=api_key, model_name=model_name)
    stage2 = GeminiExtractor(api_key=api_key, model_name=model_name)
    enricher_facade = QueryEnricher(gemini_enricher=stage1)
    engine = ColdPathExtractionEngine(provider=stage2, enricher=enricher_facade)

    # Load canonical SIIS
    with open(WORKSPACE_DIR / "siis_responses.json", "r", encoding="utf-8") as f:
        siis_data = json.load(f)["responses"]

    test_cases = [
        {
            "name": "1. Canonical Complaint",
            "query": "1. My Samsung A115G tablet screen flashes and then goes completely blank whenever I connect to my office email exchange server via Wi-Fi.",
            "siis": siis_data[0]["siis_response"],
        },
        {
            "name": "2. Paraphrased Complaint",
            "query": "Samsung tablet display flashes repeatedly and shuts off black while connecting to Wi-Fi email server",
            "siis": siis_data[0]["siis_response"],
        },
        {
            "name": "3. Unseen SIIS-backed Complaint",
            "query": "My Galaxy device screen timeout is too short and turns dark after 10 seconds of inactivity",
            "siis": {
                "title": "Screen Timeout Settings on Galaxy Devices",
                "content": (
                    "## How to Adjust Screen Timeout\n"
                    "If your device display turns dark too fast, adjust the screen timeout setting.\n"
                    "1. Navigate to and open Settings.\n"
                    "2. Tap on Display.\n"
                    "3. Select Screen timeout.\n"
                    "4. Choose your desired duration such as 2 minutes to keep the screen active."
                ),
            },
        },
    ]

    records = []

    for tc in test_cases:
        print(f"\n--- Running: {tc['name']} ---")
        t0 = time.perf_counter()
        success = False
        parsed_ok = False
        grounding_ok = False
        num_actions = 0
        resolved_deeplinks = []

        try:
            plan = engine.extract_and_build(
                query=tc["query"],
                siis_response=tc["siis"],
            )
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            parsed_ok = True

            if isinstance(plan, ContextDeeplinkResponse) and plan.contexts:
                goal = plan.contexts[0]
                num_actions = len(goal.actions)
                # Check grounding audit: at least one step was grounded and retained in the final action
                grounding_ok = len(engine.last_grounding_audit) > 0 and any(
                    a.is_grounded for a in engine.last_grounding_audit
                ) and num_actions > 0
                for act in goal.actions:
                    for sg in act.stepGroups:
                        dl = sg.actionableDeeplink.deeplink if sg.actionableDeeplink else None
                        resolved_deeplinks.append(dl)

                success = num_actions > 0 and (engine.last_stage1_provider == "gemini" or engine.last_stage2_provider == "gemini")

            record = {
                "test_case": tc["name"],
                "model": model_name,
                "success": success,
                "latency_ms": round(elapsed_ms, 2),
                "structured_output_parsed": parsed_ok,
                "grounding_passed": grounding_ok,
                "num_actions": num_actions,
                "stage1_provider": engine.last_stage1_provider,
                "stage2_provider": engine.last_stage2_provider,
                "resolved_deeplinks": resolved_deeplinks,
            }
            records.append(record)

            print(f"Status: {'SUCCESS' if success else 'PARTIAL'}")
            print(f"Latency: {elapsed_ms:.2f} ms")
            print(f"Stage 1 Provider: {engine.last_stage1_provider}")
            print(f"Stage 2 Provider: {engine.last_stage2_provider}")
            print(f"Structured Output Parsed: {parsed_ok}")
            print(f"Grounding Passed: {grounding_ok}")
            print(f"Number of Actions: {num_actions}")
            print(f"Deeplinks: {resolved_deeplinks}")

        except Exception as e:
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            record = {
                "test_case": tc["name"],
                "model": model_name,
                "success": False,
                "latency_ms": round(elapsed_ms, 2),
                "structured_output_parsed": False,
                "grounding_passed": False,
                "num_actions": 0,
                "error": str(e),
            }
            records.append(record)
            print(f"FAILED with error: {e}")

    print("\n" + "=" * 80)
    print("LIVE SMOKE TEST SUMMARY")
    print("=" * 80)
    print(json.dumps(records, indent=2))
    return all(r["success"] for r in records)


if __name__ == "__main__":
    run_live_gemini_smoke()
