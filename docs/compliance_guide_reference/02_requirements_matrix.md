# Theme 2 Compliance Matrix

Legend:

- **MUST** — directly required by Samsung material or necessary to satisfy the stated contract.
- **SHOULD** — strong engineering requirement derived from the contract.
- **OUR ENHANCEMENT** — useful improvement, not itself a Samsung mandate.
- **DO NOT CLAIM AS SAMSUNG RULE** — design choice that must not be presented as an explicit Samsung requirement.

| Area | Requirement | Status/Direction |
|---|---|---|
| REST API | `POST /v1/troubleshoot` | MUST |
| Input | `query` | MUST |
| Input | `siis_response` object | MUST |
| Grounding | SIIS is source of troubleshooting facts | MUST |
| Query enrichment | Normalize vague complaint | MUST |
| LLM architecture | Two-stage conceptual flow | MUST |
| Output | `ContextDeeplinkResponse` | MUST |
| Goal | Required pattern | MUST |
| Goal title | 2–3 words | MUST |
| Goal score | 0–1 | MUST |
| Action description | 5–7 words, starts `It will` | MUST |
| Categories | auto/manual/critical | MUST |
| Ordering | auto → manual → critical | SHOULD/MUST where schema/evaluator enforces it |
| Step grouping | Structured troubleshooting steps | MUST |
| Deeplink | Associated with actions/steps | MUST |
| Catalog URI | Copy verbatim when matched | MUST |
| URI discovery | Match human-readable metadata | SHOULD |
| Dummy fallback | `bixby://dummy_positive` when documented no-match condition occurs | MUST/allowed fallback |
| Dummy fallback grounding | Concrete SIIS-derived Settings target | MUST |
| Web URLs | No leakage into output | SHOULD / current firewall requirement |
| Cache | Pre-validated fast path | MUST |
| Cache latency | Under 300 ms target for fast path | MUST target |
| Cache key | Exact-only | DO NOT CLAIM AS SUFFICIENT |
| Semantic cache | Paraphrase support | SHOULD |
| SIIS fingerprint | Cross-article protection | SHOULD |
| Opposite-intent guard | Enable/disable, backup/restore etc. | SHOULD |
| 10k+ scenarios | Reusable mapping architecture | MUST |
| Canonical data | 20 SIIS responses | Evaluation asset |
| Deeplink catalog | 578 entries in supplied kit | Evaluation asset |
| Query variations | 8–10 per query in offline material | Evaluation asset |
| Unseen SIIS | New SIIS should yield valid non-empty response | MUST for intended behavior |
| Deterministic fallback | Conservative SIIS extraction | OUR ENHANCEMENT |
| BM25 + semantic reranking | Hybrid retrieval | OUR ENHANCEMENT |
| Adversarial benchmark | Opposite intents, collisions, leakage | OUR ENHANCEMENT |
| One Action = exactly one screen | Formal Samsung rule | DO NOT CLAIM AS SAMSUNG RULE |
| Theme 5 voice protocol | Required for Theme 2 | NO |
