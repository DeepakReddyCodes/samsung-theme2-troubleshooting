# Samsung Theme 2 — Requirements Traceability

## Core Requirements

| Samsung Requirement | Implementation | Test Coverage | Status |
|---|---|---|---|
| `POST /v1/troubleshoot` endpoint | `app/main.py` | `tests/compliance/test_contracts.py`, `tests/test_api.py` | ✅ PASS |
| Required SIIS input | `app/api/schemas.py` | Contract tests | ✅ PASS |
| SIIS as source of truth | `app/services/extractor/`, `app/services/extractor/grounding_checker.py` | `tests/compliance/test_grounding.py` | ✅ PASS |
| Structured `ContextDeeplinkResponse` | `app/core/schema.py` | Contract tests | ✅ PASS |
| Goal formatting (2–3 word title, score 0–1) | `app/core/firewall.py` | Contract tests | ✅ PASS |
| Action formatting (5–7 words, "It will…") | `app/core/firewall.py` | Contract tests | ✅ PASS |
| Category ordering (auto → manual → critical) | `app/core/firewall.py` | Contract tests, `tests/test_firewall.py` | ✅ PASS |
| Catalog URI verbatim binding | `app/services/deeplink_matcher.py` | `tests/compliance/test_deeplink_policy.py`, `tests/test_deeplinks.py` | ✅ PASS |
| Metadata-based deeplink matching | `app/services/retriever/` | Deeplink tests | ✅ PASS |
| `bixby://dummy_positive` fallback policy | `app/services/fallback_resolver.py` | Deeplink policy tests | ✅ PASS |
| Zero web URL leakage | `app/core/sanitizer.py`, `app/core/firewall.py` | `tests/compliance/test_adversarial.py` | ✅ PASS |
| Two-stage LLM pipeline (enrichment + extraction) | `app/services/extractor/engine.py`, `app/services/extractor/gemini_extractor.py` | `tests/test_gemini_two_stage.py` | ✅ PASS |
| Query enrichment | `app/services/extractor/engine.py` (Stage 1) | `tests/test_query_enrichment.py` | ✅ PASS |
| No invented troubleshooting facts | `app/services/extractor/grounding_checker.py` | `tests/compliance/test_grounding.py` | ✅ PASS |
| SIIS-aware semantic cache | `app/cache/semantic_cache.py` | `tests/compliance/test_cache_isolation.py`, `tests/test_cache.py` | ✅ PASS |
| Full SIIS fingerprint (SHA-256) | `app/cache/semantic_cache.py` | Cache isolation tests | ✅ PASS |
| Intent collision protection (polarity guard) | `app/cache/semantic_cache.py` | Cache isolation tests | ✅ PASS |
| Fast-path under 300 ms (P95) | `app/cache/semantic_cache.py`, `app/cache/prewarm.py` | `tests/test_cache.py` (latency benchmark) | ✅ PASS |
| 10k+ scenario reusability | Catalog-driven retrieval architecture | `tests/compliance/test_generalization.py` | ✅ PASS |
| Adversarial security / prompt injection | `app/core/firewall.py`, `app/core/sanitizer.py` | `tests/compliance/test_adversarial.py` | ✅ PASS |
| Frontend demo portal | `frontend/` (React + Vite) | `frontend/tests/`, `tests/test_frontend_integration.py` | ✅ PASS |
| Submission artifacts (`results.jsonl`, `output.json`) | `scripts/generate_results.py` | Submission gate | ✅ PASS |

## Project Innovations (Not Samsung Requirements)

| Innovation | Implementation | Test Coverage |
|---|---|---|
| Next-Best-Evidence (NBE) scoring | `app/services/extractor/engine.py` | `tests/test_nbe.py` |
| Expected Information Gain (EIG) | NBE subsystem | `tests/test_nbe.py` |
| Grounding Firewall (zero-bypass) | `app/core/firewall.py` | `tests/test_firewall.py` |
| Deterministic fallback engine | `app/services/extractor/deterministic_extractor.py` | `tests/test_extraction.py` |
| Provider abstraction (Gemini / deterministic) | `app/services/extractor/base.py` | `tests/test_gemini_two_stage.py` |
| Dual-tier cache (exact + semantic) | `app/cache/semantic_cache.py` | `tests/test_cache.py` |
