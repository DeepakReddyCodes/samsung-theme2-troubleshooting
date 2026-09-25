# Task Delegation Plan — Human + LLMs + Agents

## Human-owned decisions

The team should decide:

- final architecture;
- acceptable latency/cost trade-offs;
- model/provider choice;
- demo narrative;
- claims made in PPT/video;
- final merge/release/tag.

## LLM/agent-owned implementation tasks

### Agent A — Contract/schema auditor

Deliver:

- schema diff;
- invariant list;
- failing fields;
- tests for every invariant.

### Agent B — Query enrichment

Deliver:

- normalization module;
- polarity/entity preservation tests;
- benchmark on canonical and paraphrase queries.

### Agent C — SIIS extraction

Deliver:

- structured extraction prompt;
- deterministic fallback;
- grounding verifier;
- evidence mapping tests.

### Agent D — Deeplink retrieval

Deliver:

- catalog indexing;
- lexical matcher;
- semantic matcher;
- reranker;
- dummy-positive fallback;
- precision/recall evaluation.

### Agent E — Cache

Deliver:

- exact cache;
- semantic cache;
- SIIS fingerprinting;
- polarity guard;
- version invalidation;
- latency benchmark.

### Agent F — Security/validation

Deliver:

- URL leak detection;
- malformed JSON rejection;
- schema firewall;
- prompt-injection resistance against SIIS content;
- deeplink integrity checks.

### Agent G — Evaluation

Deliver:

- canonical benchmark;
- 8–10 paraphrases per canonical query;
- unseen-SIIS benchmark;
- adversarial benchmark;
- metrics report.

### Agent H — Frontend/demo

Deliver:

- clear query input;
- SIIS context display where useful;
- generated actions;
- deeplink action buttons;
- cache/latency telemetry;
- failure-state display.

## Human + ChatGPT review loop

For each agent output:

1. Agent implements.
2. Agent writes tests.
3. Human runs/inspects.
4. ChatGPT reviews diff and claims.
5. Failing tests are returned to the responsible agent.
6. Human approves merge.
7. Regression suite runs.

No agent should be allowed to redefine Samsung requirements from its own assumptions.
