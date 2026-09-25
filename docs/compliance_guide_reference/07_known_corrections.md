# Known Corrections From Prior Review

## Correction 1 — `siis_response` is not optional for Theme 2

Previous interpretation: the API could treat SIIS as optional and fall back to `contexts=[]`.

Corrected interpretation: the Theme 2 FAQ defines the API around `query + siis_response`; SIIS is the source of truth for generated actions.

## Correction 2 — No generic empty-result fallback

Previous interpretation: an unknown/no-match case could return an empty context.

Corrected interpretation: new/unseen SIIS scenarios should yield valid, non-empty grounded responses whenever the SIIS contains actionable information.

## Correction 3 — `dummy_positive` is a permitted deeplink fallback

If a concrete SIIS-derived Settings target has no catalog match, use the documented:

`bixby://dummy_positive`

and identify the concrete target in the associated human-readable description/message.

This is different from inventing a troubleshooting step.

## Correction 4 — Theme 5 protocol is not Theme 2 protocol

The all-theme participant kit root is for Theme 5. Its interruption/audio/tool-call protocol must not be presented as a Theme 2 requirement.

The Theme 2-specific asset inside it is `Theme02_Input_Kit.zip`.

## Correction 5 — Do not overstate "one Action = one Screen"

The implementation should map coherent step groups to appropriate Settings deeplinks, but the phrase "exactly one screen per Action" should not be represented as an explicit Samsung rule unless an authoritative Theme 2 document states it.

## Correction 6 — Benchmark fixtures are not proof of generalization

Prewarmed canonical answers can demonstrate cache behavior. They do not prove that the engine can reason over unseen SIIS content. Generalization must be tested separately.
