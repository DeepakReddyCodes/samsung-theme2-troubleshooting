# Samsung Theme 2 — Exact Implementation Blueprint

## 1. Objective

Implement a production-oriented `POST /v1/troubleshoot` Smart Guided Troubleshooting Engine that converts a user complaint plus a raw/pre-cleaned SIIS response into a valid `ContextDeeplinkResponse`.

The system must remain grounded in the supplied SIIS content. The deeplink catalog is used for navigation only; it is not a source of troubleshooting facts.

## 2. Non-negotiable invariants

- `siis_response` is required input.
- SIIS is the source of truth for troubleshooting facts.
- No troubleshooting fact may be introduced solely by the LLM.
- No fabricated deeplink URI may be emitted.
- Catalog URIs must be copied verbatim when a catalog match exists.
- `bixby://dummy_positive` may be used only when a concrete SIIS-grounded Settings target has no catalog match; its accompanying text must identify that concrete screen in 5–7 words.
- Web URLs must not leak into the final response.
- Every returned response passes the validation firewall.
- Cache entries must be isolated by SIIS content and implementation/catalog versions.
- A cache hit is not trusted blindly; it is revalidated before return.
- Deterministic fallback must never manufacture a step just to produce a non-empty response.

## 3. Target architecture

```text
HTTP Request
  -> Request validation
  -> Query Enrichment
  -> SIIS fingerprint/context alignment
  -> Cache lookup
       | hit -> firewall -> response
       | miss
  -> Stage 2 structured extraction
  -> Grounding verification
       | pass -> grounded plan
       | fail -> deterministic SIIS extraction
  -> Settings intent extraction
  -> Lexical + semantic catalog retrieval
  -> reranking / confidence gate
       | catalog match -> exact catalog URI
       | no match -> dummy_positive + concrete grounded screen label
  -> Action ordering
  -> Response schema validation
  -> Firewall
  -> Cache write
  -> Response
```

## 4. Repository map

### API
- `codebase/app/main.py`: HTTP lifecycle, endpoint, telemetry headers, error handling.
- `codebase/app/api/schemas.py`: external request/response DTO validation.

### Core
- `codebase/app/core/schema.py`: canonical response model.
- `codebase/app/core/firewall.py`: final validation and safe repair.
- `codebase/app/core/sanitizer.py`: text/URL sanitization.
- `codebase/app/core/rewrite_controller.py`: format-only rewriting.

### Extraction
- `codebase/app/services/extractor/engine.py`: orchestrator.
- `gemini_extractor.py`: LLM structured extraction.
- `deterministic_extractor.py`: conservative SIIS-only fallback.
- `grounding_checker.py`: evidence verification.
- `base.py`: extractor interfaces.

### Deeplinks
- `deeplink_matcher.py`: end-to-end deeplink resolution.
- `retriever/lexical_matcher.py`: metadata lexical retrieval.
- `retriever/semantic_matcher.py`: semantic retrieval.
- `fallback_resolver.py`: catalog miss handling.

### Cache
- `semantic_cache.py`: exact/semantic cache.
- `prewarm.py`: startup cache preparation.

## 5. Required changes by file

| File | Change level | Required outcome |
|---|---|---|
| `app/api/schemas.py` | Major | Freeze external request/response contract; reject malformed required SIIS. |
| `app/core/schema.py` | Major | Ensure exact response shape and enum/format constraints. |
| `app/core/firewall.py` | Major | Enforce grounding, URI, URL, category/order, and structural invariants. |
| `app/core/sanitizer.py` | Major | Prevent URL/web leakage and unsafe text transformations. |
| `app/core/rewrite_controller.py` | Major | Formatting only; no semantic invention. |
| `app/services/extractor/engine.py` | Major | Explicit LLM -> grounding -> deterministic fallback pipeline. |
| `gemini_extractor.py` | Major | Structured output + SIIS-only prompt + evidence spans. |
| `deterministic_extractor.py` | Major | Extract only actionable instructions explicitly present in SIIS. |
| `grounding_checker.py` | Major | Claim-level evidence checking against SIIS. |
| `deeplink_matcher.py` | Major | Retrieve from human-readable catalog metadata; confidence gate. |
| `lexical_matcher.py` | Review | Normalize Android/Samsung terminology and retrieve candidates. |
| `semantic_matcher.py` | Review | Semantic candidates; never manufacture URI meaning. |
| `fallback_resolver.py` | Major | Implement conservative `dummy_positive` policy. |
| `semantic_cache.py` | Major | SIIS-aware, versioned, polarity-safe cache keys. |
| `prewarm.py` | Review | Prewarm only validated entries; never hide generalization failures. |
| `app/main.py` | Review | Keep endpoint thin; delegate business logic. |
| tests/* | Major | Add contract, grounding, generalization, adversarial, cache, and performance tests. |
| scripts/* | Major | Separate canonical, paraphrase, unseen-SIIS, adversarial, and latency benchmarks. |

## 6. Internal modules to introduce

Create these modules unless an existing module is extended cleanly:

```text
codebase/app/domain/
  models.py
  enums.py
  errors.py

codebase/app/pipeline/
  orchestrator.py
  enrichment.py
  grounding.py
  action_builder.py
  ordering.py

codebase/app/catalog/
  index.py
  normalizer.py
  resolver.py

codebase/app/observability/
  telemetry.py

codebase/tests/compliance/
  test_contracts.py
  test_grounding.py
  test_generalization.py
  test_adversarial.py
  test_cache_isolation.py
  test_deeplink_policy.py
```

Do not add these files if the agent can preserve an equivalent clean architecture without duplication; contracts must remain identical.

## 7. Internal data flow

### 7.1 Query enrichment

Input: raw user query.

Output:
- normalized query
- technical query
- intent candidates
- entity candidates
- polarity/action direction

Enrichment may clarify terminology but may not add a troubleshooting fact absent from SIIS.

### 7.2 SIIS fingerprint

Compute a stable hash from normalized SIIS title + content. Keep the original SIIS payload available for evidence verification.

### 7.3 Extraction

The LLM receives:
- user query
- enriched query
- SIIS title
- SIIS content
- strict output schema

The model must return evidence references for each substantive action.

### 7.4 Grounding

For every action:
1. Identify the factual claims.
2. Locate supporting SIIS evidence.
3. Reject unsupported claims.
4. Reject polarity reversal.
5. Reject unsupported setting names.

### 7.5 Deterministic fallback

Parse SIIS instruction-like sentences, ordered lists, settings paths, and imperative statements. Return only claims that can be directly supported.

If no actionable instruction exists, return the contractually valid conservative response allowed by the authoritative schema/requirements; do not invent a troubleshooting procedure.

### 7.6 Settings intent

Extract only concrete settings targets supported by the grounded plan/SIIS. Normalize synonyms for retrieval only.

### 7.7 Deeplink retrieval

Use human-readable metadata such as description/message/qna_description/originalType and related catalog fields.

Do not infer URI meaning by parsing opaque identifiers.

Pipeline:

```text
intent
 -> normalized metadata query
 -> lexical candidates
 -> semantic candidates
 -> deduplicate
 -> rerank
 -> confidence threshold
 -> exact URI or dummy_positive
```

### 7.8 Ordering

Actions are emitted in the required category order:

```text
auto -> manual -> critical
```

Preserve SIIS sequence inside a category where possible.

## 8. Cache design

Cache key:

```text
SHA256(
  normalized_intent
  + SIIS_content_hash
  + extractor_version
  + catalog_version
)
```

Recommended cache record:

```python
CacheEntry(
    key,
    response,
    siis_hash,
    engine_version,
    catalog_version,
    created_at,
    validation_version,
)
```

Semantic cache acceptance requires both semantic similarity and SIIS compatibility. Never reuse a response across incompatible SIIS contexts.

## 9. Firewall

The firewall must reject or repair only non-semantic formatting defects. It must reject semantic violations such as:

- unsupported action claim
- unsupported setting target
- invented URI
- HTTP/HTTPS URL
- malformed deeplink
- invalid category
- wrong action order
- empty required structure
- cache contamination

A repair function may alter formatting, title wording, and action-description wording only when the underlying meaning remains unchanged and evidence remains intact.

## 10. LLM strategy

Use structured output where available. Keep the LLM responsible for semantic structuring, not authority.

Prompt requirements:
- SIIS is authoritative.
- Quote or reference evidence for each action.
- Never infer missing troubleshooting facts.
- Never create a URI.
- Distinguish settings navigation from procedural instructions.
- Preserve polarity.
- Return `NO_GROUNDED_ACTION` when evidence is insufficient.

## 11. API behavior

`POST /v1/troubleshoot` is the only required business endpoint.

The endpoint must:
1. Validate request.
2. Compute context fingerprint.
3. Check cache.
4. Run cold pipeline on miss.
5. Validate final response.
6. Return deterministic JSON.

Telemetry headers may be retained but must not alter the response contract.

## 12. Error handling

- malformed JSON -> HTTP 400
- schema-invalid request -> HTTP 422
- not-ready -> HTTP 503
- unexpected internal failure -> HTTP 500 without stack traces/secrets

## 13. Test matrix

### Contract
- required fields
- type validation
- response schema
- regex/title/description constraints
- enum values

### Grounding
- every action traceable to SIIS
- polarity preservation
- unsupported claim rejection
- prompt injection in SIIS

### Deeplink
- exact catalog URI preservation
- metadata matching
- no invented URI
- dummy_positive policy
- no HTTP/HTTPS leakage

### Generalization
- unseen SIIS article
- unseen complaint + unseen SIIS
- new settings target
- no prewarm dependency

### Cache
- same query + same SIIS -> hit
- same query + different SIIS -> miss
- opposite intent -> miss
- changed engine version -> miss
- changed catalog version -> miss

### Adversarial
- enable/disable
- backup/restore
- display/touch
- Wi-Fi/mobile data
- application identity substitution
- contradictory query/SIIS
- malicious instructions embedded in SIIS

### Performance
Record p50/p95 latency, cache hit rate, LLM calls/query, cost/query, and throughput.

## 14. Acceptance criteria

A workstream is complete only if:
- implementation matches `contracts/contracts.md`;
- targeted tests pass;
- full regression suite passes;
- no new unsupported claims are introduced;
- no secret/generated dependency artifacts are committed;
- benchmark results are recorded;
- known limitations are documented.

## 15. Implementation sequence

1. Freeze contracts.
2. Audit current schemas.
3. Build domain models/interfaces.
4. Implement query enrichment.
5. Refactor extraction around evidence.
6. Implement deterministic SIIS fallback.
7. Harden grounding checker.
8. Refactor deeplink retrieval/ranking.
9. Implement dummy-positive policy.
10. Redesign cache isolation.
11. Harden firewall.
12. Add compliance tests.
13. Add unseen-SIIS benchmark.
14. Add adversarial benchmark.
15. Optimize latency/cost.
16. Integrate frontend/demo.
17. Run final submission gate.

Do not optimize latency before correctness and grounding are stable.
