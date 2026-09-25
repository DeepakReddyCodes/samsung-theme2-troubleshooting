# Samsung Theme 2 — Frozen Contracts v1.0

**Status: FROZEN FOR IMPLEMENTATION**

The complete frozen contract is in:

`docs/CONTRACT_FREEZE_v1.0.md`

Agents MUST read that document before modifying the implementation.

## Frozen external request

```json
{
  "query": "string",
  "siis_response": {
    "title": "string",
    "content": "string"
  }
}
```

Endpoint:

```http
POST /v1/troubleshoot
```

## Frozen response

The response MUST conform to the supplied `ContextDeeplinkResponse` model. Do not invent a parallel schema.

## Frozen grounding invariant

```text
No SIIS evidence => no new troubleshooting fact.
```

## Frozen action constraints

- description begins with `It will`
- description is 5–7 words
- category ∈ `{auto, manual, critical}`
- category ordering: `auto → manual → critical`
- goal title: 2–3 words
- goal score: `[0, 1]`

## Frozen deeplink constraints

- catalog match → exact URI copied verbatim
- catalog miss for concrete SIIS-grounded Settings target → `bixby://dummy_positive` with concrete target wording
- never synthesize an opaque catalog URI
- no arbitrary HTTP/HTTPS URLs in final troubleshooting output

## Frozen cache constraints

Cache identity must include:

```text
normalized intent
+ SIIS fingerprint
+ engine version
+ catalog version
```

Semantic similarity alone is insufficient.

## Frozen fallback

```text
LLM extraction
→ deterministic SIIS extraction
→ conservative SIIS-only construction
```

Never invent a troubleshooting step to avoid an empty result.

## Frozen non-requirement

Do NOT claim that Samsung requires exactly one Settings screen per Action unless a higher-authority Samsung source is later verified to say so.
