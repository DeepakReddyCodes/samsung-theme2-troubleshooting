# Theme 2 — Authoritative Requirements

## 1. Problem

Theme 2 asks for a Smart Guided Troubleshooting Engine that converts vague customer device complaints into structured troubleshooting actions and maps those actions to Galaxy Settings deeplinks.

Samsung's published Theme 2 description requires:

- Query enrichment: normalize a raw complaint into a technical query.
- A two-stage LLM engine that returns clean, ordered troubleshooting steps as JSON.
- Mapping each step to the exact in-app Settings deeplink so the fix can be one tap away.
- A fast-path cache serving pre-validated answers in under 300 ms.
- A REST API returning structured JSON.
- Reusable mapping suitable for 10k+ scenarios.
- Deeplinks that logically resolve to the action steps.
- Output JSON containing all actions, steps, and associated deeplinks.
- Reporting of step accuracy, latency, and cost per query.

## 2. API input

`POST /v1/troubleshoot`

Expected input conceptually:

```json
{
  "query": "user natural-language troubleshooting complaint",
  "siis_response": {
    "title": "SIIS article title",
    "content": "pre-cleaned SIIS knowledge text"
  }
}
```

`query_variations` may also appear in offline/evaluation material.

### Critical grounding rule

`siis_response` is the knowledge source. The engine may normalize, extract, restructure, and paraphrase it, but it must not invent unsupported troubleshooting facts.

## 3. API output

The output is a `ContextDeeplinkResponse` containing:

```text
ContextDeeplinkResponse
└── contexts: List[Goal]
    └── Goal
        ├── goal
        ├── title
        ├── score
        └── actions: List[Action]
            └── Action
                ├── actionName
                ├── description
                ├── category
                └── stepGroups
                    └── StepGroup
```

The exact Pydantic structure is supplied in `02_theme02_input_kit/student_kit/schema.py` and the current implementation's `schema.py`/`app/api/schemas.py`.

## 4. Formatting constraints

The supplied FAQ/schema require, among other constraints:

- Goal text follows the specified `Follow these steps to perform this <Name> Troubleshooting/Configuration.` form.
- Goal title is 2–3 words.
- Goal score is in `[0.0, 1.0]`.
- Action description is 5–7 words and starts with `It will`.
- Action category is one of `auto`, `manual`, `critical`.
- Output is structured JSON, not prose.

## 5. Action ordering

The implementation should enforce the supplied ordering semantics:

`auto → manual → critical`

Do not reorder merely for aesthetic reasons after validation.

## 6. Deeplinks

The supplied `deeplinks.json` is the authoritative catalog of valid Samsung Galaxy OneUI deeplinks for the provided evaluation material.

Matching must use human-readable catalog metadata such as descriptions/messages/types rather than attempting to infer meaning from a masked or opaque URI.

When a catalog entry matches, copy the exact catalog URI verbatim.

## 7. `dummy_positive`

If a concrete SIIS-derived Settings action has no matching catalog entry, the documented Samsung fallback is:

`bixby://dummy_positive`

The fallback must still identify the concrete Settings screen/action in its associated description/message. It is not permission to invent an arbitrary troubleshooting action.

## 8. Cache

The fast path must return pre-validated responses. The cache should be intent-aware rather than raw-string-only, while protecting against cross-SIIS contamination and opposite-intent collisions.

A robust cache key should conceptually include:

- normalized intent/query representation;
- SIIS content fingerprint;
- engine version;
- catalog version.

## 9. Generalization

The engine must not be hardcoded to the 20 canonical scenarios. The supplied FAQ describes new SIIS payloads/unseen cases as part of the intended problem behavior.

The correct generalization model is:

`new complaint + new SIIS → valid non-empty grounded response`

not:

`unknown complaint → empty response`

and not:

`unknown complaint → invented generic troubleshooting advice`.

## 10. Published hackathon evaluation

The launch material publishes:

- Working prototype & functionality — 30%
- Technical depth & feasibility — 25%
- Innovation & originality — 20%
- Relevance to theme — 15%
- Presentation & documentation — 10%

For submission, the published requirements also call for a working prototype repository, reproducible README, Docker/required files, demo video, and presentation material. The final judged commit must use the required release tag.
