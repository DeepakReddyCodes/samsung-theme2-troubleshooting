# Corrected Theme 2 Architecture

```text
                         USER COMPLAINT
                               │
                               ▼
                    ┌─────────────────────┐
                    │ Stage 1             │
                    │ Query Enrichment    │
                    └──────────┬──────────┘
                               │
                               ▼
                       Technical Query
                               │
                               ▼
                    ┌─────────────────────┐
                    │ SIIS Context        │
                    │ Alignment /         │
                    │ Fingerprinting      │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │ Stage 2             │
                    │ Troubleshooting     │
                    │ Structuring LLM     │
                    └──────────┬──────────┘
                               │
                               ▼
                    Evidence / Grounding
                        Verification
                               │
                  ┌────────────┴────────────┐
                  │                         │
                PASS                      FAIL
                  │                         │
                  │                Deterministic SIIS
                  │                    extraction
                  │                         │
                  │                         ▼
                  │                    grounding
                  │                         │
                  └────────────┬────────────┘
                               ▼
                       Structured Actions
                               │
                               ▼
                     Settings Intent Extraction
                               │
                               ▼
                  ┌──────────────────────────┐
                  │ Deeplink Retrieval       │
                  │                          │
                  │ lexical + semantic       │
                  │ metadata matching        │
                  └────────────┬─────────────┘
                               │
                               ▼
                            Rerank
                               │
                     ┌─────────┴─────────┐
                     │                   │
                 catalog match       no catalog match
                     │                   │
                     ▼                   ▼
               exact URI copy      dummy_positive
                                   + grounded screen
                     └─────────┬─────────┘
                               ▼
                      Action Ordering
                               │
                               ▼
                    Validation Firewall
                               │
                               ▼
                       Semantic Cache
                               │
                               ▼
                       REST JSON Output
```

## Non-negotiable design principle

The LLM is a reasoning/structuring component, not an independent troubleshooting knowledge base.

The permitted transformation is:

`SIIS facts → normalized/structured representation → validated output`

not:

`SIIS + model world knowledge → arbitrary troubleshooting advice`.

## Fallback architecture

The cold path should have three levels:

1. Gemini structured extraction.
2. Deterministic SIIS parser.
3. Conservative minimal SIIS restructuring.

A failed LLM call must not force an empty response when the SIIS payload contains actionable content. Conversely, the fallback must never fabricate a step merely to make the response non-empty.
