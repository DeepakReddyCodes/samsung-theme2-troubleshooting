# Samsung PRISM Y2026 — Theme 2 Contract Freeze v1.0

**Status:** FROZEN FOR IMPLEMENTATION
**Scope:** Smart Guided Troubleshooting Engine (Theme 02)
**Contract owner:** Project team
**Baseline:** Supplied Samsung Theme 2 materials + supplied Theme02 Input Kit + current SmartGuide implementation

> This document freezes what the implementation must do. It deliberately separates Samsung requirements from implementation choices and from assumptions. Agents must not silently promote an implementation choice into a Samsung requirement.

## 1. Authority hierarchy

Use this order when sources conflict:

1. Samsung-published Theme 2 problem statement / submission instructions.
2. Samsung Theme 2 FAQ / clarification material supplied to the team.
3. Supplied Theme02 Input Kit (`schema.py`, `sample_output.json`, `deeplinks.json`, `siis_responses.json`, `input.txt`).
4. Existing supplied SmartGuide implementation.
5. Our engineering decisions.

If a lower-level source conflicts with a higher-level source, the higher-level source wins and the discrepancy must be recorded.

## 2. Samsung Theme 2 requirements — MUST

The implementation MUST provide the following:

- A REST API for the troubleshooting engine.
- `POST /v1/troubleshoot` as the business endpoint.
- Request processing based on the user's natural-language complaint plus the supplied raw/pre-cleaned SIIS response.
- Query enrichment: normalize the complaint into a technical query.
- A two-stage LLM-oriented troubleshooting flow that produces clean, ordered troubleshooting steps as JSON.
- Mapping of troubleshooting/settings actions to relevant Galaxy Settings deeplinks.
- A fast-path cache for pre-validated answers with a target of under 300 ms for the fast path.
- Reusable mapping suitable for the stated 10k+ scenario production target.
- Deeplinks that logically correspond to the action they accompany.
- Output JSON containing the actions, steps, and associated deeplink information required by the supplied response contract.
- Reporting/evaluation of step accuracy, latency, and cost per query.

Samsung's published Theme 2 description explicitly emphasizes query enrichment, two-stage LLM structuring, exact in-app Settings deeplinks, sub-300-ms fast-path caching, reusable 10k+ scenario mapping, logical deeplink resolution, and structured JSON output. fileciteturn10file0

## 3. API request contract

### Endpoint

```http
POST /v1/troubleshoot
Content-Type: application/json
```

### Required request body

```json
{
  "query": "string",
  "siis_response": {
    "title": "string",
    "content": "string"
  }
}
```

Rules:

- `query` is required and must be a non-empty string after trimming.
- `siis_response` is required.
- `siis_response.title` is required and non-empty.
- `siis_response.content` is required and non-empty.
- Additional request fields may be rejected or ignored according to the frozen external schema, but they must never change the meaning of the required fields.

### Critical correction

`siis_response` is NOT optional for the Theme 2 implementation. The SIIS payload is the supplied knowledge context for the troubleshooting request.

## 4. SIIS authority / grounding contract

SIIS is the **source of truth for troubleshooting facts**.

The engine MAY:

- normalize wording;
- enrich the complaint linguistically;
- extract instructions from SIIS;
- restructure SIIS instructions into the required JSON form;
- paraphrase SIIS-supported instructions;
- identify settings targets explicitly supported by the grounded troubleshooting content;
- map a grounded settings target to the supplied deeplink catalog.

The engine MUST NOT:

- invent a troubleshooting step from general model knowledge when SIIS does not support it;
- add a diagnosis merely because it is plausible;
- reverse action polarity (`enable` → `disable`, `backup` → `restore`, etc.);
- substitute a different app, feature, device, or setting;
- use the deeplink catalog as evidence for a troubleshooting fact;
- treat an LLM's unsupported assertion as evidence.

### Core invariant

```text
No SIIS evidence
    => no new troubleshooting fact
```

A model may decide how to express a supported instruction. It may not decide what unsupported instruction should exist.

## 5. API response contract

The response MUST conform to the supplied `ContextDeeplinkResponse` schema. The canonical supplied structure is:

```text
ContextDeeplinkResponse
└── contexts: List[Goal]
    └── Goal
        ├── goal: string
        ├── title: string
        ├── actions: List[Action]
        └── score: float
            └── Action
                ├── actionName: string
                ├── description: string
                ├── stepGroups: List[StepGroup]
                └── category: auto | manual | critical
                    └── StepGroup
                        ├── steps: List[string]
                        ├── validationDeeplink: optional
                        └── actionableDeeplink: optional
```

Do not create a parallel response schema.

### Non-empty behavior

For an actionable SIIS response, the implementation MUST attempt to produce a valid, non-empty grounded troubleshooting context. It MUST NOT depend on the 20 canonical prewarmed examples to appear functional.

If SIIS contains no actionable troubleshooting instruction, the implementation may return the schema-valid no-action representation permitted by the authoritative contract. It must not fabricate a step solely to avoid an empty result.

## 6. Goal contract

The goal string MUST follow the supplied pattern:

```text
Follow these steps to perform this <Name> Troubleshooting.
```

or the contractually permitted Configuration variant where appropriate.

Goal title:

- 2–3 words.
- Human-readable.
- Must describe the grounded troubleshooting/configuration objective.

Goal score:

- numeric;
- inclusive range `[0.0, 1.0]`;
- must represent system confidence, not an invented external probability.

The implementation must not add unsupported diagnostic certainty merely to increase the score.

## 7. Action contract

Each Action contains:

- `actionName`;
- `description`;
- `stepGroups`;
- `category`.

### Description

The description MUST:

- begin with `It will`;
- contain 5–7 words;
- describe the grounded action purpose;
- avoid introducing a new factual claim.

Example shape:

```text
It will check your Wi-Fi connection status
```

The example is a formatting example, not an instruction to check Wi-Fi unless SIIS supports it.

### Category

Allowed values only:

```text
auto
manual
critical
```

### Ordering

Actions MUST be emitted in this category order:

```text
auto → manual → critical
```

Within the same category, preserve grounded SIIS order where practical.

## 8. StepGroup contract

A StepGroup contains:

- one or more `steps`;
- optional `validationDeeplink`;
- optional `actionableDeeplink`.

Rules:

- Steps must be grounded in SIIS-derived troubleshooting content.
- A StepGroup's deeplink must logically correspond to the setting/action it accompanies.
- Do not claim that Samsung formally requires exactly one screen per Action; the authoritative material currently available to the team does not establish that rule.
- Multiple coherent steps may be grouped when they belong to the same grounded setting/action flow.

## 9. Deeplink contract

### 9.1 Catalog authority

The supplied `deeplinks.json` is the authoritative navigation catalog for the supplied evaluation material.

### 9.2 Matching

Matching SHOULD use human-readable catalog metadata, including available fields such as:

- `description`;
- `message`;
- `qna_description` when present;
- `originalType`;
- other human-readable metadata supplied by the catalog.

Do NOT infer semantic meaning by parsing masked/opaque URI identifiers.

### 9.3 Catalog hit

When a catalog entry is selected:

```text
returned URI == catalog URI exactly
```

Do not mutate, synthesize, shorten, decode, or reconstruct the URI.

### 9.4 Catalog miss

When a **concrete SIIS-grounded Settings target** exists but no catalog entry matches it, the permitted fallback is:

```text
bixby://dummy_positive
```

The accompanying description/message MUST name the concrete grounded Settings screen/action and be 5–7 words where the applicable Samsung fallback wording requires that length.

Example shape only:

```text
Open display refresh rate settings
```

The fallback does NOT authorize invention of the underlying troubleshooting action.

### 9.5 URL safety

Final troubleshooting responses MUST NOT leak arbitrary `http://` or `https://` web URLs as troubleshooting/navigation targets.

## 10. Query enrichment contract

Query enrichment is a normalization layer, not a knowledge-generation layer.

It may produce:

```text
raw complaint
→ normalized complaint
→ technical terminology
→ candidate intent
→ entities / device / app / feature
→ polarity / action direction
```

It MUST preserve:

- negation;
- enable/disable direction;
- device identity;
- application identity;
- feature identity;
- relevant constraints in the complaint.

It must not inject a troubleshooting step.

## 11. Two-stage LLM contract

The architecture must preserve the Theme 2 concept of a two-stage LLM engine.

Recommended division:

### Stage 1 — Enrichment / interpretation

Convert the raw complaint into a technical representation while preserving polarity and entities.

### Stage 2 — Grounded structuring

Given the enriched complaint and SIIS context, produce structured troubleshooting actions with evidence references.

The LLM is a structuring component. SIIS remains the authority.

## 12. Grounding verification contract

Every substantive Action and StepGroup must be traceable to SIIS evidence.

The grounding checker must detect at minimum:

- unsupported action claims;
- unsupported setting targets;
- polarity reversal;
- app/device substitution;
- unsupported diagnosis;
- instruction expansion beyond SIIS evidence.

If LLM output fails grounding, it MUST NOT proceed directly to the client.

Fallback sequence:

```text
LLM structured extraction
        ↓ fail grounding
Deterministic SIIS extraction
        ↓ fail
Conservative SIIS-only construction
```

Never use a generic model-generated troubleshooting step as the fallback.

## 13. Cache contract

The fast path must serve **pre-validated** responses.

Cache identity MUST include, at minimum:

```text
normalized intent/query representation
+ SIIS content fingerprint
+ engine version
+ catalog version
```

Recommended:

```text
SHA256(
    normalized_intent
    + siis_content_hash
    + engine_version
    + catalog_version
)
```

A semantic cache match is invalid when SIIS compatibility fails.

Cache MUST NOT cause:

- cross-SIIS contamination;
- enable/disable collisions;
- backup/restore collisions;
- app/feature identity collisions;
- reuse across incompatible catalog versions.

## 14. Performance contract

Samsung's Theme 2 target is a fast-path cache serving pre-validated answers in under 300 ms. fileciteturn10file0

We therefore measure separately:

- cache-hit p50;
- cache-hit p95;
- cold-path p50/p95;
- LLM calls/query;
- cost/query;
- throughput;
- cache hit rate.

Do not represent cold-path latency as satisfying the fast-path target.

## 15. Reusability contract

The mapping and pipeline must be reusable beyond the supplied 20 canonical scenarios. The published target is 10k+ scenarios. fileciteturn10file0

The implementation MUST NOT:

- hardcode one response per canonical query;
- select answers solely by exact query text;
- rely on prewarm fixtures for unseen cases;
- infer that benchmark coverage equals generalization.

## 16. Error contract

The external API should use:

- `400` for malformed JSON/request parsing failures;
- `422` for schema validation failures;
- `503` when the engine is not ready;
- `500` for unexpected internal failures.

Client responses MUST NOT expose:

- stack traces;
- API keys;
- model credentials;
- internal prompts;
- filesystem paths that expose secrets;
- raw exception internals.

## 17. Security / adversarial contract

The system must treat SIIS content as **data**, not as executable instructions to the LLM.

Test and defend against:

- prompt injection embedded in SIIS;
- URL injection;
- fake deeplinks;
- instruction polarity flips;
- contradictory query/SIIS combinations;
- unsupported settings targets;
- cross-scenario cache contamination.

## 18. Evaluation contract

The implementation must report at least:

### Accuracy

- step/action correctness against grounded references;
- deeplink correctness;
- grounding pass rate;
- unsupported-claim rate.

### Performance

- p50/p95 latency;
- fast-path under-300-ms rate;
- cache hit rate;
- throughput.

### Cost

- LLM calls/query;
- estimated token usage;
- cost/query where measurable.

### Test partitions

Keep these partitions separate:

1. Canonical 20 scenarios.
2. Query paraphrases.
3. Unseen SIIS + unseen complaint scenarios.
4. Adversarial/security cases.
5. Cache/performance tests.

Canonical benchmark success MUST NOT be reported as generalization evidence.

## 19. Hackathon submission contract

The final repository must satisfy Samsung's published submission requirements, including:

- working prototype code in a public/shared GitHub repository;
- reproducible README/setup instructions;
- Docker and other required files;
- required demo video, maximum 5 minutes;
- required presentation file;
- final release tag `PRISM_GENAI_HACKATHON_Y2026` on the judged final commit;
- all materials referenced by the submission must be present in the tagged commit.

Samsung's published submission guidance also says teams not following the submission guidelines may be directly disqualified. fileciteturn10file6

## 20. Explicit non-requirements / do-not-claim list

The following are NOT frozen as Samsung requirements:

- exactly one Settings screen per Action;
- a specific LLM vendor/model;
- a specific embedding model;
- a specific vector database;
- a specific web framework implementation;
- a specific cache technology;
- a requirement to use Theme 5's audio/video/interruption protocol;
- a requirement to reproduce the 20 canonical answers verbatim;
- permission to invent troubleshooting steps when SIIS is insufficient.

These may be engineering choices, but agents must label them as such.

## 21. Definition of contract compliance

A build is contract-compliant only when:

```text
API contract passes
AND
response schema passes
AND
SIIS grounding passes
AND
deeplink policy passes
AND
cache isolation passes
AND
unseen-SIIS tests pass
AND
adversarial tests pass
AND
fast-path performance is measured
AND
submission artifacts are reproducible
```

Passing the canonical 20 alone is NOT sufficient for contract freeze acceptance.
