# Workstream 01 — Query Enrichment

Owner: Agent B

Build deterministic/LLM-assisted query normalization without adding unsupported troubleshooting facts.

Inputs: raw query + SIIS context.
Outputs: normalized query, technical terms, intent candidates, polarity/entities.

Acceptance: paraphrases normalize consistently; polarity and app identity are preserved.



Implement explicit Stage 1 query enrichment.

Input:
raw user complaint

Output:
structured technical representation

Stage 1 must not invent troubleshooting actions.

Read:
- MASTER_CHECKPOINT_v2.md
- contracts.md
- existing extractor implementation

Do not implement W02, W03, NBE, or cache changes.
