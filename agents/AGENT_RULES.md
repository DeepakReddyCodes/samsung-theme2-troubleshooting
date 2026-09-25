# Agent Rules — Samsung Theme 2

1. Read `docs/IMPLEMENTATION.md` and `contracts/contracts.md` before editing code.
2. Do not redefine Samsung requirements from assumptions.
3. Treat SIIS as the source of truth.
4. Never invent troubleshooting facts to satisfy a test.
5. Never invent or mutate deeplink URIs.
6. Use `bixby://dummy_positive` only under the documented catalog-miss policy.
7. Preserve polarity and application/device identity.
8. Keep changes isolated to the assigned workstream.
9. Add or update tests with every behavioral change.
10. Run targeted tests, then the full regression suite.
11. Report files changed, tests run, results, limitations, and dependency changes.
12. Do not commit `.env`, API keys, `node_modules`, virtual environments, caches, build outputs, or secrets.
13. Do not change public API shape without an explicit contract review.
14. Do not optimize by deleting grounding checks.
15. If requirements appear contradictory, stop and flag the contradiction instead of guessing.
