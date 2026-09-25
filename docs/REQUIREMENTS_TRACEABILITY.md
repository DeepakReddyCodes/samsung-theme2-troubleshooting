# Requirements Traceability — Baseline Audit

| Requirement | Implementation area | Test area | Baseline status |
|---|---|---|---|
| POST /v1/troubleshoot | `app/main.py` | `tests/compliance/test_contracts.py` | PASS — needs executable compliance test |
| Required SIIS input | `app/api/schemas.py` | contract tests | PASS |
| SIIS as source of truth | extractor + grounding | `test_grounding.py` | PARTIAL / HIGH RISK |
| Structured response | `app/core/schema.py` | contract tests | PASS |
| Goal formatting | rewrite/schema | contract tests | PASS/PARTIAL |
| Action formatting | rewrite/schema | contract tests | PASS/PARTIAL |
| Category ordering | pipeline/order | contract tests | PASS |
| Catalog URI verbatim | catalog resolver | deeplink tests | PASS |
| Metadata-based matching | retrievers | deeplink tests | PASS/PARTIAL |
| dummy_positive fallback | fallback resolver | deeplink policy tests | PARTIAL / HIGH RISK |
| No URL leakage | sanitizer/firewall | adversarial tests | PASS / TEST GAP |
| Query enrichment | new component required | contract/generalization tests | MISSING |
| Explicit two-stage LLM flow | extractor architecture | contract tests | PARTIAL |
| No invented troubleshooting facts | engine fallback | grounding tests | FAIL |
| All applicable action deeplink mapping | engine/resolver | deeplink policy tests | FAIL / HIGH RISK |
| Unseen SIIS | pipeline | generalization tests | TEST GAP |
| SIIS-aware cache | semantic cache | cache isolation tests | PASS/PARTIAL |
| Full SIIS fingerprint | semantic cache | collision tests | FAIL/P1 |
| Intent collision protection | semantic cache | cache isolation tests | PARTIAL |
| Performance measurement | scripts | benchmark suite | TEST GAP |
| Fast-path under 300 ms | cache | performance tests | TEST GAP |
| 10k+ scenario reusability | architecture | scale/generalization tests | PARTIAL |
| Adversarial security | firewall/pipeline | adversarial tests | MISSING |
| Reproducible frontend | frontend build | integration tests | FAIL in baseline |
| Submission artifacts | root/docs/release | submission gate | PARTIAL |
