# Workstream 00 — Contract Freeze + Baseline Contract Audit

**Owner:** Human + Reviewer
**Status:** Contract frozen; baseline audit complete; executable compliance tests still required.

## Goal
Freeze the external and internal contracts before parallel implementation and establish a measured PASS/PARTIAL/FAIL/MISSING baseline against the supplied SmartGuide implementation.

## Read first

1. `docs/CONTRACT_FREEZE_v1.0.md`
2. `contracts/contracts.md`
3. `docs/CONTRACT_TO_CODE_AUDIT_v1.0.md`
4. `docs/REQUIREMENTS_TRACEABILITY.md`

## Deliverables

- Validate the frozen contract against authoritative Theme 2 materials.
- Keep Samsung requirements separate from engineering choices.
- Replace placeholder compliance tests with executable tests.
- Build fixtures for canonical, paraphrase, unseen-SIIS, and adversarial cases.
- Produce a machine-readable compliance result.
- Do not modify production behavior unless a testability hook is explicitly justified and reviewed.

## Baseline findings already established

The supplied baseline currently has:

```text
89 passed, 3 failed
```

The visible failures are:

- semantic paraphrase cache hit;
- cache benchmark hit-rate assertion;
- frontend compiled `dist` integration test.

The deeper contract risks are documented in `docs/CONTRACT_TO_CODE_AUDIT_v1.0.md`, especially:

- invented generic troubleshooting fallback;
- missing explicit query enrichment stage;
- incomplete two-stage LLM architecture;
- deeplink handling only for `auto` actions;
- `dummy_positive` generic screen fallback;
- lexical-only grounding limitations;
- placeholder compliance suites;
- truncated SIIS fingerprint.

## Acceptance

Workstream 00 is complete only when:

1. every frozen requirement has at least one executable test;
2. canonical, paraphrase, unseen-SIIS, adversarial, deeplink, cache, and API fixtures exist;
3. every current baseline failure is classified;
4. no requirement is marked PASS merely because a code path exists;
5. downstream agents can implement against the frozen internal interfaces without reinterpretation;
6. the test suite can distinguish Samsung requirements from optional engineering enhancements.

## Important restriction

Do **not** weaken the grounding invariant to make the baseline pass.

```text
No SIIS evidence => no new troubleshooting fact.
```
