# W07 — Performance, Latency and Cost Engineering Completion Report

## 1. Branch
`w07-performance-latency-cost-engineering`

## 2. Files Changed
- `codebase/scripts/cost_calculator.py` (New file)
- `codebase/scripts/benchmark_engine.py`
- `codebase/app/main.py`
- `W07_COMPLETION_REPORT.md` (New file)

## 3. Benchmark Commands
To run the parameterized cost calculator:
```bash
python codebase/scripts/cost_calculator.py --input-tokens 800 --output-tokens 200 --requests 1000000 --price-input 0.15 --price-output 0.60 --cache-hit-rate 0.90
```

To run the end-to-end benchmark engine with detailed component latencies:
```bash
cd codebase && python scripts/benchmark_engine.py
```

## 4. Measured Metrics
From local benchmark execution on a pre-warmed system:
- **Startup Latency**: ~14.755 s (Gate Failed - official target <= 8.0s)
- **Canonical Repeat (Warm Cache)**
    - Hit Rate: 100.00%
    - Server Latency (P50/P95/P99): 0.47ms / 1.01ms / 1.04ms
    - End-to-End HTTP (P50/P95/P99): 2.42ms / 3.22ms / 4.65ms
- **Paraphrased Queries**
    - Hit Rate: 92.50% (Semantic)
    - Server Latency (P50/P95/P99): 15.53ms / 41.83ms / 74.90ms
- **Unseen SIIS Scenarios (Cold Path)**
    - Server Latency (P50/P95/P99): 36.74ms / 39.35ms / 39.77ms
    - **Component P50 Latencies**:
        - Cache Lookup: 15.88ms
        - Extraction Engine: 20.44ms (Deterministic fallback in current test harness)
        - Response Serialization (Pydantic + Firewall): 0.29ms

## 5. Sample Benchmark Output
```
[BENCHMARK 4] Benchmark C: Unseen SIIS Scenarios Generalization Engine (12 scenarios)...
  [unseen_01_battery_drain] Latency:  38.47ms | Path: cold_path              | Valid: True | Goal: Follow these steps to perform this Battery Life Issues And Troubleshooting
...
-> Unseen Scenarios P50=36.74ms | P95=39.35ms | P99=39.77ms
   - Component P50s: Cache=15.88ms | Extraction=20.44ms | Serialization=0.29ms
-> All Unseen Scenarios Schema & Firewall Valid: True (12/12)
```

## 6. Methodology
- **Cost Calculator**: Built a pure Python parameterized calculator defining cost per 1M tokens vs average cache hit rate. We extrapolate single query API costs to monthly requests.
- **Latency Benchmarking**: Augmented `app/main.py` explicitly using lightweight `time.perf_counter()` wrappers. Telemetry data is communicated back to `benchmark_engine.py` via HTTP custom headers `X-Cache-Time-Ms`, `X-Extract-Time-Ms`, and `X-Serialize-Time-Ms`.
- Tests run sequentially in single-process mode utilizing the default `testclient`.

## 7. Limitations
- **Strict Architecture Boundaries ("Do NOT modify W01")**: The instruction strictly forbid modification of `app/services/extractor/engine.py` and `app/services/enrichment/`. This prevented us from deeply instrumenting the *internals* of the cold path (such as Query Enrichment, Grounding, LLM invocation wait times, Retrieval overhead, and Deeplink matching). These are all grouped under the single telemetry output `X-Extract-Time-Ms`.
- **LLM Mock Data**: Because the test suite uses `DeterministicFallbackExtractor` during cold path benchmarking (by default in offline test mode), the reported "Extraction" latency is exceptionally low (~20ms). Real production LLM invocation will likely shift this metric up dramatically (e.g. 500ms - 2s).

## 8. Optimization Opportunities Discovered
1. **Startup Initialization**: Model/Tokenizer loading for the `FastPathSemanticCache` causes the startup sequence to miss the <= 8.0s constraint (~14.7s measured). Lazy loading the SentenceTransformer or deferring cache pre-warm could fix this.
2. **Semantic Cache Paraphrase Latency**: The P99 latency for paraphrases hits ~74ms, which is mostly driven by SentenceTransformer embedding computation overhead.
3. **Pydantic Validation Firewall**: Adding Pydantic v2 `TypeAdapter` and avoiding full `.dict()` instantiations during the Serialization step could shave fractions of milliseconds, though serialization is currently extremely fast (~0.29ms).

## 9. Issues Left for Later Workstreams
- **W01 Integration**: Real API latency monitoring (for OpenAI/Gemini extraction) is needed once full LLMs are wired up.
- **W08 Frontend Demo**: Needs to gracefully handle Cold Path latency scenarios (displaying skeletons/loading spinners since un-cached LLM queries take significantly longer).
- **W09 Final Gate**: Needs to revisit the <= 8.0s startup gate failure using a deferred loading strategy.
