\# AGENTS.md — Samsung PRISM GenAI Hackathon Y2026 Theme 2



\## Project



This repository implements Samsung PRISM GenAI Hackathon Y2026 — Theme 2:



\*\*Smart Guided Troubleshooting Engine\*\*



The system converts vague user device complaints into structured troubleshooting actions and resolves those actions to Samsung Settings deeplinks.



\---



\## AUTHORITATIVE REQUIREMENT HIERARCHY



When making implementation decisions, follow this order:



1\. Samsung-provided authoritative hackathon materials

2\. `docs/CONTRACT\_FREEZE\_v1.0.md`

3\. `contracts/contracts.md`

4\. The specific task/workstream specification

5\. This file and other engineering documentation



Do not override a higher-level requirement based on an agent's assumption.



If a requirement is ambiguous, identify the ambiguity rather than inventing a requirement.



\---



\## FIRST PRINCIPLE



The objective is not to make tests pass.



The objective is to make the implementation satisfy the authoritative

Samsung Theme 2 contract.



If existing production behavior conflicts with the contract, preserve

the test that exposes the conflict and fix the implementation.



Never modify a requirement merely because the current implementation

cannot satisfy it.

## Current Project Checkpoint

The current project state and architecture are defined in:

`docs/MASTER_CHECKPOINT_v2.md`

Before implementing any workstream, read:

1. `AGENTS.md`
2. `docs/MASTER_CHECKPOINT_v2.md`
3. `contracts/contracts.md`
4. the relevant task file under `tasks/`
5. relevant existing implementation and tests

The Master Checkpoint describes the current architecture and implementation direction.

Do not treat architectural proposals as Samsung requirements unless they are explicitly identified as Samsung requirements in the checkpoint or authoritative Samsung source materials.

\## SOURCE OF TRUTH FOR PROJECT FACTS



Do not treat:

\- existing code,

\- existing tests,

\- comments,

\- generated outputs,

\- agent assumptions



as authoritative when they conflict with the Samsung materials or

frozen project contracts.



Existing implementation behavior may be incorrect.



Existing tests may be incomplete or incorrect.



The contract takes precedence.



\## SCOPE



This repository is for \*\*Theme 2 only\*\*.



Do NOT import requirements from other Samsung PRISM hackathon themes.



In particular, do not introduce unrelated Theme 5 real-time voice/audio/video/interruptibility requirements.



\---



\## CORE GROUNDING RULE



SIIS is the source of truth for troubleshooting facts.



\### Fundamental invariant



NO SIIS EVIDENCE  

→ NO NEW TROUBLESHOOTING FACT  

→ NO GENERATED STEP



The system may restructure, normalize, order, classify, or explain information supported by SIIS.



It must not invent troubleshooting instructions merely to produce a non-empty response.



\---



\## TROUBLESHOOTING GENERATION



The intended pipeline is conceptually:



USER QUERY

→ Query Enrichment

→ SIIS Context Alignment / Fingerprint

→ Troubleshooting Structuring

→ Grounding Verification

→ Settings Intent Extraction

→ Deeplink Retrieval / Reranking

→ Action Ordering

→ Validation Firewall

→ Cache

→ REST JSON



Do not bypass grounding verification.



If an LLM fails to produce usable grounded output, use deterministic SIIS-derived extraction or another conservative fallback.



Never use generic invented troubleshooting steps as a fallback.



\---



\## QUERY ENRICHMENT



The raw user complaint must be converted into a useful technical query before troubleshooting structuring.



Query enrichment must preserve the user's actual intent.



Do not introduce unsupported device problems, causes, fixes, or settings.



\---



\## DEEPLINK RULES



Never invent Samsung deeplink URIs.



Catalog deeplinks must be copied exactly from the provided catalog.



Matching should use human-readable deeplink metadata such as descriptions, messages, Q\&A descriptions, and related metadata rather than assuming that URI strings themselves contain reliable semantic meaning.



`bixby://dummy\_positive` is a fallback for a concrete SIIS-derived Settings target when no catalog deeplink exists.



It does NOT authorize inventing a troubleshooting step or Settings target.



\---

## NBE / EIG

Next-Best-Evidence (NBE) and Expected Information Gain (EIG) are project innovations.

They are NOT to be represented as explicit Samsung Theme 2 requirements.

Do not claim NBE/EIG is implemented until the corresponding implementation and tests actually exist.

\## RESPONSE CONTRACT

## Theme Boundary

This repository implements Samsung PRISM Y2026 Theme 2 only.

Do not import requirements from Theme 5 or any other theme unless they are independently present in the Theme 2 requirements.

Respect the frozen external response contract.



Important constraints include:



\- Goal title: 2–3 words

\- Goal score: 0–1

\- Goal description follows the defined contract

\- Action description: 5–7 words and starts with `It will`

\- Action category:

&#x20; - `auto`

&#x20; - `manual`

&#x20; - `critical`

\- Action ordering:

&#x20; - `auto`

&#x20; - `manual`

&#x20; - `critical`

\- Catalog deeplink URIs must be exact.

\- Output must contain the required structured actions, steps, and deeplinks.

\- Do not leak ordinary web URLs into the response.



Do not change the external API contract without explicit approval.



\---



\## CACHE



Cache entries must not cross-contaminate different SIIS contexts.



The cache identity should account for relevant inputs including:



\- normalized intent

\- SIIS content/fingerprint

\- engine version

\- catalog version



Polarity changes such as enable/disable must not collide.



Do not use truncated SIIS content when a full-content fingerprint is required.



The fast-path target is under 300 ms for cache-served responses.



\---



\## TESTING



Tests are part of the implementation contract.



Do not:



\- weaken a test to make production code pass

\- delete a failing test without justification

\- replace a requirement with a weaker interpretation merely because it is difficult to implement

\- claim tests pass without actually running them



When tests fail, report the failure and investigate the underlying cause.



Existing baseline failures are evidence about the current implementation, not reasons to weaken the requirements.



\---



\## WORKSTREAM DISCIPLINE



Work only on the requested workstream.



Do not redesign unrelated architecture.



Do not silently modify unrelated modules.



Do not make broad refactors unless the requested workstream requires them.

For test-only workstreams, such as W00, do not modify production application behavior unless the task specification explicitly permits it.

If a test exposes an existing production defect, record the defect and failure rather than modifying production code outside the assigned workstream.



Before implementation:



1\. Read the relevant contract.

2\. Read the task specification.

3\. Inspect the existing implementation.

4\. State the implementation plan.



After implementation:



1\. Run relevant tests.

2\. Run affected existing tests.

3\. Report failures.

4\. Report all changed files.

5\. Report new dependencies.

6\. Report known limitations.

7\. Report possible regressions.



\---



\## GIT / BRANCHING



Do not force-push.



Do not rewrite shared history.



Do not commit secrets or credentials.



Do not commit:



\- `.env` files containing secrets

\- API keys

\- private credentials

\- private certificates

\- unnecessary generated artifacts

\- dependency caches



Prefer small, focused commits.



Do not merge your own work into `main` unless explicitly instructed.



\---
## Requirement Classification

Every requirement must be classified as one of:

- Samsung requirement
- Project contract requirement
- Engineering decision
- Proposed innovation
- Implementation detail

Do not promote an engineering decision or proposed innovation into a Samsung requirement.

## REQUIREMENT VERIFICATION

Before implementing a requirement, verify it against the referenced project documentation.

Do not promote an engineering preference, inferred behavior, existing implementation detail, or agent suggestion into a Samsung requirement.

If a behavior is an engineering decision rather than a Samsung requirement, treat it as such and document it separately.

Do not claim that Samsung requires a behavior unless the authoritative materials support that claim.


\## AGENT BEHAVIOR



Agents are implementation/research assistants, not project architects.



Do not redefine Samsung's requirements.



Do not silently reinterpret ambiguous requirements.



When a conflict is discovered:



1\. Identify the conflicting requirements.

2\. Cite the relevant project documentation.

3\. Stop the affected implementation if necessary.

4\. Report the ambiguity for human review.



Never fabricate evidence, test results, benchmark results, or compliance.



\---



\## DEFINITION OF DONE



A workstream is not complete merely because code was written.



A workstream is complete only when:



\- the requested behavior is implemented,

\- relevant tests exist,

\- relevant tests have been executed,

\- regressions have been checked,

\- the implementation respects the frozen contract,

\- no unsupported behavior has been introduced,

\- changed files and limitations are reported.



\---



\## HUMAN APPROVAL



The human project owner controls:



\- architecture changes,

\- external API changes,

\- Samsung requirement interpretation,

\- dependency additions with material impact,

\- merging into `main`,

\- final submission decisions.



When in doubt, stop and report rather than guessing.

