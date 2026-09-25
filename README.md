# Samsung Theme 2 — Implementation Workspace

This workspace is the engineering starting point for the Samsung PRISM GenAI Hackathon Y2026 Theme 2 — Smart Guided Troubleshooting Engine.

## Source of truth
1. `docs/IMPLEMENTATION.md` — master implementation blueprint.
2. `contracts/contracts.md` — frozen internal and external contracts.
3. `docs/REQUIREMENTS_TRACEABILITY.md` — requirement-to-code/test mapping.
4. `agents/AGENT_RULES.md` — rules for all coding agents/LLMs.
5. `tasks/` — independently assignable workstreams.
6. `codebase/` — supplied SmartGuide implementation baseline, cleaned of generated dependency folders.

## Important
The existing `codebase/` is a baseline, not a claim that the implementation is already fully compliant. Agents must treat the blueprint and contracts as the target state and the existing code as material to audit and modify.

Do not silently weaken SIIS grounding to make tests pass. Do not invent troubleshooting facts or deeplink URIs.

## Contract status

The implementation contract is frozen as **v1.0** in `docs/CONTRACT_FREEZE_v1.0.md`.

No agent should make a semantic architecture or external-schema change without first opening a contract-change request and identifying which higher-authority Samsung requirement necessitates the change.
