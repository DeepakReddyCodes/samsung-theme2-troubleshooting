# Instructions for Any LLM/Agent Working on Theme 2

1. Read this entire `04_compliance_guide/` directory before modifying code.
2. Read `01_authoritative_sources/` before making a requirement claim.
3. Read `02_theme02_input_kit/` before changing schema, catalog matching, or benchmark logic.
4. Treat `03_current_smartguide/` as the implementation under audit, not as an authority.
5. Do not import Theme 5 protocol requirements into Theme 2.
6. Do not remove `siis_response` from the API contract.
7. Do not create generic empty/no-match behavior merely because a scenario is unseen.
8. Do not invent troubleshooting facts outside SIIS.
9. Do not invent deeplink URIs.
10. Use `bixby://dummy_positive` only under the documented no-catalog-match condition and keep the Settings target grounded.
11. Do not weaken the validation firewall to make tests pass.
12. Every implementation change must add or update tests.
13. Every performance claim must identify whether it is cached or cold-path.
14. Every benchmark must record dataset, engine, model, and catalog versions.
15. Do not delete working behavior without a regression test proving the replacement.
16. If a requirement is ambiguous, mark it `DOUBT` and escalate it for human review rather than inventing a rule.
