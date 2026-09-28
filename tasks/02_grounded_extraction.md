# Workstream 02 — Grounded Extraction

Owner: Agent C

Refactor extraction to produce structured actions with evidence references and a conservative deterministic SIIS fallback.

Acceptance: every action can be traced to SIIS; unsupported claims are rejected.



Implement Stage 2 troubleshooting structuring.

Inputs:
- enriched query
- SIIS response

Output:
contract-compliant candidate troubleshooting JSON.

Every troubleshooting fact must be grounded in SIIS.

Remove/rework any generic fallback that invents troubleshooting steps.

Do not implement NBE.
