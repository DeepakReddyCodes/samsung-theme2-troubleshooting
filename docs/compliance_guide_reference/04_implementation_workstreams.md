# Implementation Workstreams

This is the work decomposition to use when we draft the exact implementation blueprint.

## Phase 0 — Contract lock

- Freeze authoritative schema.
- Freeze input/output examples.
- Freeze SIIS grounding rule.
- Freeze deeplink fallback semantics.
- Separate Samsung requirements from our enhancements.

## Phase 1 — Current-code audit/fixes

Audit:

- `app/main.py`
- `app/api/schemas.py`
- `app/core/schema.py`
- `app/core/firewall.py`
- `app/core/sanitizer.py`
- `app/core/rewrite_controller.py`
- `app/services/extractor/engine.py`
- `app/services/extractor/gemini_extractor.py`
- `app/services/extractor/deterministic_extractor.py`
- `app/services/extractor/grounding_checker.py`
- `app/services/deeplink_matcher.py`
- `app/services/fallback_resolver.py`
- `app/services/retriever/*`
- `app/cache/*`
- tests and benchmark scripts.

## Phase 2 — Query enrichment

Implement a clearly isolated normalization stage. It must preserve polarity and important entities:

- model/device;
- component;
- symptom;
- trigger;
- desired operation;
- enable/disable polarity;
- app/context;
- constraints.

## Phase 3 — Grounded extraction

Require every generated action/step to be traceable to SIIS evidence.

Add evidence spans or internal provenance metadata even if the final Samsung response does not expose that metadata.

## Phase 4 — Deeplink retrieval

Use catalog metadata:

- description;
- message;
- qna_description;
- originalType;
- validation metadata.

Candidate pipeline:

`normalized screen intent → lexical retrieval → semantic retrieval → reranking → confidence gate`.

## Phase 5 — Conservative fallback

Implement deterministic extraction from SIIS for:

- numbered instructions;
- bullet steps;
- Settings navigation phrases;
- enable/disable operations;
- app-specific troubleshooting actions.

## Phase 6 — Cache

Cache only validated final responses.

Recommended fingerprint:

`hash(normalized_intent + SIIS_content_hash + engine_version + catalog_version)`.

Semantic cache must reject cross-SIIS false positives and opposite intent.

## Phase 7 — Benchmark

Build four sets:

1. Canonical 20.
2. Paraphrases.
3. Unseen SIIS.
4. Adversarial cases.

## Phase 8 — Full gate

Run:

- schema tests;
- grounding tests;
- deeplink tests;
- URL leak tests;
- cache tests;
- latency tests;
- unseen-scenario tests;
- Docker/reproducibility tests;
- frontend integration tests.

## Phase 9 — Demo/submission

Freeze the judged commit, verify documentation, tag the release, and run the final clean-environment test.
