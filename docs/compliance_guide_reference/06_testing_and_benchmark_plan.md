# Testing and Benchmark Plan

## A. Contract tests

Every response must be checked for:

- valid JSON;
- exact Pydantic schema;
- goal regex;
- title word count;
- description word count/prefix;
- score bounds;
- allowed categories;
- required StepGroups;
- deeplink fields.

## B. Grounding tests

For every generated step:

- identify supporting SIIS span(s);
- reject unsupported claims;
- verify polarity;
- verify device/component consistency;
- verify action is not imported from unrelated world knowledge.

## C. Deeplink tests

Test:

- exact catalog match;
- paraphrase match;
- similar-screen collision;
- enable vs disable;
- backup vs restore;
- app A vs app B;
- display vs touch;
- catalog miss → dummy_positive;
- no invented URI;
- no HTTP/HTTPS URL.

## D. Cache tests

Test:

- exact repeat;
- punctuation variation;
- paraphrase;
- same query + different SIIS;
- opposite polarity;
- engine version change;
- catalog version change.

## E. Generalization tests

A valid unseen test case contains:

```json
{
  "query": "new natural-language complaint",
  "siis_response": {
    "title": "new SIIS article",
    "content": "new actionable SIIS content"
  }
}
```

Expected:

- non-empty response;
- valid schema;
- grounded steps;
- valid catalog deeplinks or documented dummy-positive fallback;
- no invented web URLs.

## F. Adversarial cases

Include:

- contradictory query vs SIIS;
- SIIS text containing URLs;
- SIIS text containing prompt-injection instructions;
- ambiguous screen names;
- conflicting steps;
- repeated steps;
- missing action metadata;
- empty SIIS content;
- malformed `siis_response`;
- extremely long input;
- Unicode/punctuation noise.

## G. Performance

Measure separately:

- exact cache hit latency;
- semantic cache hit latency;
- cold LLM latency;
- deterministic fallback latency;
- deeplink retrieval latency;
- total request latency;
- token usage/cost where provider data is available.

Do not report cached latency as cold-path latency.

## H. Report format

Every benchmark report should contain:

- dataset version;
- engine version;
- model/version;
- catalog version;
- number of cases;
- pass/fail count;
- grounding accuracy;
- deeplink accuracy;
- schema-valid rate;
- URL-leak rate;
- cache hit rate;
- P50/P95/P99 latency;
- estimated cost/query;
- known limitations.
