# Final Submission Gate

Before creating the judged release:

## Repository

- [ ] Public/shared GitHub repository as required.
- [ ] README has reproducible setup.
- [ ] Dockerfile / required Docker configuration works from a clean environment.
- [ ] No secrets committed.
- [ ] No `.env` with credentials.
- [ ] No `node_modules`.
- [ ] No Python virtual environment.
- [ ] No generated cache directories.
- [ ] No unnecessary private data.

## API

- [ ] `POST /v1/troubleshoot` works.
- [ ] `GET /health` or documented health endpoint works.
- [ ] Input schema is correct.
- [ ] Output schema is correct.
- [ ] Error responses are deterministic and useful.

## Theme 2 functionality

- [ ] Query enrichment works.
- [ ] Two-stage processing is demonstrable.
- [ ] SIIS grounding is enforced.
- [ ] Deeplinks are catalog-grounded.
- [ ] `dummy_positive` fallback works only where appropriate.
- [ ] Fast-path cache works.
- [ ] Semantic paraphrases work.
- [ ] New SIIS scenarios work.
- [ ] Output has all required actions/steps/deeplinks.

## Evaluation

- [ ] Canonical benchmark passes.
- [ ] Paraphrase benchmark passes.
- [ ] Unseen-SIIS benchmark passes.
- [ ] Adversarial benchmark passes.
- [ ] Latency measurements are reproducible.
- [ ] Cost measurements are reproducible.
- [ ] Known limitations are documented.

## Submission tag

The published hackathon submission instructions require the final judged commit to use:

`PRISM_GENAI_HACKATHON_Y2026`

The tag must point to the exact commit containing all referenced submission material.
