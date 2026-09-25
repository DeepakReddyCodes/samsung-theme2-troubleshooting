# Samsung Theme 2 Compliant Guide

**Project:** Smart Guided Troubleshooting Engine  
**Hackathon:** Samsung PRISM GenAI Hackathon Y2026 — Theme 02  
**Purpose:** Single working reference package for auditing, redesigning, implementing, testing, and submitting a Theme 2 solution.

## What this package is

This package consolidates the supplied Samsung Theme 2 materials, the supplied `Samsung-SmartGuide` implementation, the Theme 2 input kit extracted from the all-theme participant kit, and a corrected compliance/review guide.

It is deliberately organized so that an implementation agent can distinguish:

1. **Authoritative Samsung material** — requirements and evaluation facts.
2. **Theme 2 evaluation assets** — SIIS responses, deeplink catalog, schema, sample output, canonical queries.
3. **Current implementation** — the code we are auditing and improving, not an unquestionable source of truth.
4. **Compliance guide** — our consolidated interpretation and implementation requirements.
5. **Original source archives** — immutable supplied archives for traceability.

## Important correction carried into this guide

Earlier analysis incorrectly treated `siis_response` as optional and proposed a `contexts=[] / no_match` style fallback. That interpretation is superseded.

For Theme 2, the authoritative FAQ describes `POST /v1/troubleshoot` as receiving `query` and a raw/pre-cleaned `siis_response` object. Actions and steps must be derived from SIIS. Unseen scenarios are expected to supply new SIIS content and receive valid, non-empty responses.

When a concrete SIIS-derived Settings target has no matching catalog deeplink, the FAQ permits the documented `bixby://dummy_positive` fallback, with a concrete Settings-screen description/message.

## Important participant-kit distinction

The root all-theme participant kit is a **Theme 5: Interruptible Real-time Agents** kit. Its voice/interruption/tool protocol is not a Theme 2 requirement.

The Theme 2-relevant item inside that kit is:

`participant-kit/Theme02_Input_Kit.zip`

That archive is included in `02_theme02_input_kit/` and extracted there as well.

## Recommended use

Do not start implementation directly from the current SmartGuide README. First read:

- `01_authoritative_sources/`
- `02_theme02_input_kit/`
- `04_compliance_guide/01_authoritative_requirements.md`
- `04_compliance_guide/02_requirements_matrix.md`
- `04_compliance_guide/03_corrected_architecture.md`
- `04_compliance_guide/04_implementation_workstreams.md`
- `04_compliance_guide/05_task_delegation.md`
- `04_compliance_guide/06_testing_and_benchmark_plan.md`
- `04_compliance_guide/07_known_corrections.md`
- `04_compliance_guide/08_submission_gate.md`

The exact implementation blueprint will be drafted after this package is accepted as the shared project baseline.
