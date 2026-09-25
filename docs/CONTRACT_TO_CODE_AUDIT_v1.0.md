# Samsung PRISM Y2026 Theme 2 — Contract-to-Code Audit v1.0

**Date:** 2026-09-24
**Baseline:** `codebase/` supplied SmartGuide implementation in the implementation workspace
**Contract:** `docs/CONTRACT_FREEZE_v1.0.md`
**Audit status:** BASELINE AUDIT COMPLETE — IMPLEMENTATION NOT YET COMPLIANT

## Executive result

The supplied implementation has a substantial amount of useful infrastructure, but it is **not yet safe to call Samsung Theme 2 compliant**. The current code is a strong prototype baseline, not a finished implementation.

Observed baseline test result:

```text
89 passed, 3 failed
```

The three current failures are:

1. semantic cache paraphrase hit fails because `sentence_transformers` is unavailable in the environment and the cache falls back to exact-only mode;
2. the cache benchmark therefore misses the expected paraphrase hits and fails its hit-rate assertion;
3. the frontend integration test expects a compiled `frontend/dist`, but the baseline workspace does not contain that build output.

More importantly, several **contract-level risks are not covered by the current tests**. These are higher priority than the three visible failures.

---

# 1. Status legend

- **PASS** — current implementation materially satisfies the frozen contract and evidence exists in code/tests.
- **PARTIAL** — infrastructure exists, but important behavior is incomplete or conditional.
- **FAIL** — current behavior violates the frozen contract or creates a direct compliance risk.
- **MISSING** — required behavior has no meaningful implementation.
- **TEST GAP** — implementation may exist, but the required behavior is not adequately proven.

---

# 2. Contract-to-code matrix

| Contract area | Baseline status | Primary files | Finding |
|---|---|---|---|
| `POST /v1/troubleshoot` | PASS | `app/main.py` | Endpoint exists with request/response models. |
| Required `query` | PASS | `app/api/schemas.py` | Required and non-empty. |
| Required `siis_response` | PASS | `app/api/schemas.py` | Required object with title/content. |
| SIIS as source of truth | **PARTIAL / HIGH RISK** | `engine.py`, `grounding_checker.py`, `deterministic_extractor.py` | Grounding exists, but the engine contains an invented generic fallback path. |
| Query enrichment | **MISSING** | — | No dedicated enrichment stage or technical-query contract exists. |
| Two-stage LLM architecture | **PARTIAL** | `gemini_extractor.py`, `engine.py` | Current Gemini call performs extraction; no explicit enrichment stage is implemented. |
| Structured JSON response | PASS | `app/core/schema.py` | Pydantic response model exists. |
| Goal formatting | PASS/PARTIAL | `rewrite_controller.py`, `firewall.py` | Formatting gate exists; semantic confidence handling needs review. |
| Action 5–7 word description | PASS/PARTIAL | `rewrite_controller.py`, `firewall.py` | Formatting is enforced, but repair may change meaning and needs evidence-preservation tests. |
| Category enum | PASS | `schema.py`, `firewall.py` | `auto/manual/critical` enforced. |
| Action ordering | PASS | `engine.py`, `firewall.py` | Category sorting exists. |
| Step grounding | **PARTIAL / HIGH RISK** | `grounding_checker.py` | Token-overlap grounding is too weak to prove semantic support and can accept/reject incorrectly. |
| No invented troubleshooting step | **FAIL** | `engine.py` | Generic fallback creates unsupported instructions when extraction yields no grounded actions. |
| Deeplink catalog authority | PASS | `deeplink_matcher.py`, `firewall.py` | Catalog URIs are checked. |
| Verbatim catalog URI | PASS | retrievers/resolver | Selected URI is copied from catalog. |
| Metadata-based matching | PASS/PARTIAL | `lexical_matcher.py`, `semantic_matcher.py` | Metadata matching exists; semantic thresholds/reranking need adversarial validation. |
| Polarity handling | PARTIAL | lexical/cache | Some polarity logic exists; full action-polarity tests are missing. |
| `dummy_positive` | PARTIAL / HIGH RISK | `fallback_resolver.py`, `lexical_matcher.py` | Fallback exists, but screen extraction can fall back to generic invented names. |
| All actions/steps/deeplinks | **FAIL / HIGH RISK** | `engine.py` | Deeplink resolution is only performed for `auto` actions. Manual/critical actions can have no associated deeplink. |
| Cache SIIS isolation | PASS/PARTIAL | `semantic_cache.py` | Fingerprint is included and semantic candidates require exact fingerprint equality. Fingerprint currently hashes only the first 500 chars of content. |
| Cache versioning | PASS | `semantic_cache.py` | Engine/schema/catalog/SIIS file hashes are included in version token. |
| Cache intent collision protection | PARTIAL | `semantic_cache.py` | Basic conflicts exist, but the implementation is incomplete for general polarity/entity/app collisions. |
| Fast-path <300 ms | TEST GAP | `semantic_cache.py` | Exact lookup is fast; no clean published fast-path benchmark currently proves the requirement in a stable environment. |
| 10k+ scenario reuse | PARTIAL | architecture | Mapping is reusable in principle, but current implementation is not yet proven at scale. |
| Unseen SIIS | **TEST GAP / HIGH RISK** | compliance tests | Dedicated tests are placeholders; no evidence currently proves generalization. |
| Adversarial security | **MISSING** | compliance tests | Adversarial suite is still a placeholder. |
| API validation | PASS | `app/main.py`, `schemas.py` | 400/422 handling exists. |
| Secret/stack trace protection | PASS/PARTIAL | `main.py` | Generic errors are sanitized; CORS is overly permissive for production but not a Theme 2 core contract issue. |
| Evaluation metrics | PARTIAL | `scripts/`, `results/` | Benchmark infrastructure exists, but contract partitions are not yet fully implemented. |
| Reproducible frontend | FAIL in baseline test | `frontend/` | Compiled `dist` is absent from workspace, causing integration failure. |

---

# 3. Critical findings requiring implementation

## C1 — Invented generic fallback violates grounding invariant

**File:** `app/services/extractor/engine.py`

Current behavior after all extracted actions are rejected:

```python
fallback_steps = [
    "Navigate to and open device Settings.",
    f"Check {topic} configuration."
]
```

If those steps are not supported by SIIS, the code then falls back again to a line from the article and constructs an action named `Check <topic> Settings`.

This is not acceptable under the frozen invariant:

```text
No SIIS evidence => no new troubleshooting fact.
```

### Required change

Replace the generic fallback with a conservative SIIS-only constructor. If actionable instructions cannot be established, return the contractually permitted no-action representation rather than inventing a Settings navigation step.

**Priority: P0.**

---

## C2 — Query enrichment is not actually implemented

Samsung explicitly calls for:

```text
raw complaint → technical query
```

The current engine passes the raw query directly into the extractor. There is no dedicated `EnrichedQuery` or equivalent contract.

### Required change

Introduce an explicit enrichment component, for example:

```text
app/services/query_enrichment/
    models.py
    enricher.py
    deterministic.py
```

Minimum fields should preserve:

- original query;
- normalized technical query;
- device/entity;
- application/entity;
- feature;
- polarity/action direction;
- relevant constraints.

The enrichment stage must not generate troubleshooting actions.

**Priority: P0.**

---

## C3 — Two-stage LLM flow is not explicit

The current `GeminiExtractor` performs one structured extraction call. That is useful, but it does not cleanly implement:

```text
Stage 1: enrichment
Stage 2: grounded troubleshooting structuring
```

### Required change

Split the provider interface so Stage 2 receives an explicit enriched query and SIIS context. Keep provider/model choice implementation-specific.

**Priority: P0.**

---

## C4 — Deeplinks are resolved only for `auto` actions

In `engine.py`:

```python
if category == actionCategory.auto:
    resolution = self.resolver.resolve_from_step_group(...)
```

This means manual and critical actions can have steps but no associated deeplink.

Samsung's Theme 2 statement says the output should include actions, steps and associated deeplink information, and that the mapping should logically resolve to action steps. fileciteturn12file2

### Required change

Do not automatically force a Settings deeplink onto an action that has no grounded Settings target. Instead:

1. identify whether the grounded action contains a Settings target;
2. if yes, resolve it;
3. if catalog match exists, use exact URI;
4. if concrete target exists but catalog has no match, use permitted `dummy_positive`;
5. if no Settings target exists, preserve the action without a fabricated deeplink and explicitly test that this behavior matches the supplied output contract.

This requires a direct contract interpretation test against the authoritative Theme 2 kit before implementation is finalized.

**Priority: P0.**

---

## C5 — `dummy_positive` fallback can invent a screen name

`fallback_resolver.py` contains:

```python
return "Display"
```

as a final screen-name fallback.

That is dangerous because a catalog miss must not become an invented Settings target.

### Required change

`dummy_positive` must require a concrete SIIS-grounded Settings target. If no target can be extracted, return no deeplink rather than defaulting to `Display`.

**Priority: P0.**

---

## C6 — Grounding algorithm is lexical, not genuinely semantic

`GroundingChecker` currently considers a step grounded when roughly 50% of non-stopword tokens occur in SIIS, with a small phrase bonus.

This can produce false positives such as a generated instruction sharing common vocabulary with an article while introducing a new operation.

It can also reject legitimate paraphrases that use different vocabulary.

### Required change

Grounding should become a layered verifier:

```text
exact/phrase evidence
        ↓
entity + polarity consistency
        ↓
semantic entailment / constrained comparison
        ↓
decision
```

The verifier should record evidence and rejection reasons.

A lightweight deterministic layer can remain the first gate, but it must not be treated as proof of semantic entailment by itself.

**Priority: P0.**

---

## C7 — Compliance tests are placeholders

All six new compliance suites currently contain placeholder tests:

```text
contracts
cache isolation
adversarial
deeplink policy
generalization
grounding
```

Therefore the current `89 passed` result is **not** evidence of full contract compliance.

### Required change

Replace every placeholder with executable tests before declaring Workstream 00 complete.

**Priority: P0.**

---

## C8 — Cache fingerprint is truncated to 500 characters

`compute_siis_fingerprint()` hashes only:

```python
content[:500]
```

Two SIIS articles with the same first 500 characters but different actionable content could collide at the context identity level.

### Required change

Fingerprint the complete normalized SIIS title + content. Hashing the entire normalized payload is cheap compared with an LLM call and removes this avoidable collision risk.

**Priority: P1.**

---

## C9 — Semantic cache depends on optional package/model availability

The baseline test suite demonstrates that `sentence_transformers` is unavailable, causing semantic cache behavior to disappear.

This is not necessarily a Samsung violation because the model choice is open, but it means the current implementation cannot claim semantic paraphrase caching in every deployment.

### Required change

Choose and document one of two paths:

**Path A:** make the embedding dependency part of the reproducible deployment and include the model provisioning strategy;

**Path B:** implement a deterministic paraphrase retrieval strategy that does not silently downgrade a required capability.

For the hackathon prototype, Path A is likely simpler if the environment can reliably provision the model.

**Priority: P1.**

---

## C10 — Current frontend test assumes build artifact is present

The baseline `test_frontend_integration.py` expects:

```text
frontend/dist/index.html
```

but the supplied workspace does not contain the compiled distribution.

### Required change

Either:

- make the documented setup build the frontend before backend integration tests; or
- make the test explicitly skip when `dist` is intentionally absent and add a separate build test.

For final submission, reproducible setup should produce the required frontend artifact if the frontend is part of the demo.

**Priority: P1.**

---

# 4. Existing strengths worth preserving

The baseline already contains useful engineering foundations:

- FastAPI REST endpoint;
- Pydantic request/response models;
- catalog-backed URI validation;
- URI verbatim copying from catalog entries;
- lexical metadata retrieval;
- optional semantic reranking;
- action-category ordering;
- URL-leak detection;
- validation firewall;
- deterministic extraction fallback;
- SIIS-aware cache fingerprinting;
- cache version management;
- conflict checks for several opposing intents;
- benchmark scripts;
- Docker configuration;
- frontend integration structure.

These should be refactored and hardened rather than discarded.

---

# 5. Workstream order after audit

Do not parallelize everything yet. The recommended order is:

```text
W00 Contract tests + test harness
        ↓
W01 Query enrichment
        ↓
W02 Grounded extraction redesign
        ↓
W03 Deeplink resolution + dummy_positive hardening
        ↓
W04 Cache redesign / dependency reproducibility
        ↓
W05 Firewall + adversarial security
        ↓
W06 Unseen/generalization benchmark
        ↓
W07 Performance/cost benchmark
        ↓
W08 Frontend/demo integration
        ↓
W09 Final regression + submission gate
```

W01/W02/W03 have data-contract dependencies, so they should not be implemented independently before W00 freezes the internal interfaces.

---

# 6. Immediate next task — Workstream 00

The first agent task should **not modify production logic**.

It should:

1. replace placeholder compliance tests with executable contract tests;
2. build fixtures for canonical, paraphrase, unseen-SIIS and adversarial cases;
3. verify the current baseline against those tests;
4. produce a machine-readable compliance report;
5. leave production code unchanged except for testability hooks that are explicitly approved.

Acceptance condition:

```text
Every frozen requirement has at least one executable test
AND
all baseline failures are classified
AND
no requirement is marked PASS solely because a code path exists
```

Only after this passes should implementation agents begin changing the pipeline.

---

# 7. Baseline test result

Executed:

```bash
python -m pytest -q
```

Result:

```text
89 passed, 3 failed
```

Failures:

```text
FAIL test_paraphrase_semantic_hit
FAIL test_latency_benchmarking_and_statistics
FAIL test_frontend_index_serving
```

These failures are useful signals, but they are **not the complete compliance result** because the new compliance suite is still placeholder-only.

---

# 8. Audit conclusion

**Current state: Prototype baseline with substantial infrastructure; not yet Theme 2 contract-complete.**

The highest-risk issue is not the missing embedding package or frontend build. It is the possibility of returning a troubleshooting instruction or Settings target that is not actually supported by the supplied SIIS context.

The implementation should therefore be hardened around this invariant first:

```text
SIIS evidence
    ↓
Grounded action
    ↓
Grounded Settings target (if one exists)
    ↓
Catalog URI OR permitted dummy_positive
    ↓
Validated response
```

Nothing in the pipeline should be able to bypass that chain.
