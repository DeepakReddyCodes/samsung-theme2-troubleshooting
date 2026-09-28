# Workstream 04 — Cache Isolation

Owner: Agent E

Redesign exact/semantic caching around query + SIIS + engine + catalog versions.

Acceptance: different SIIS contexts cannot contaminate each other; opposite intents do not collide.


Cache identity must include:

- normalized intent
- complete relevant SIIS content hash
- engine version
- catalog version

The SIIS hash must not be truncated to the first 500 characters.

Tests must cover:
- paraphrase hits
- polarity isolation
- SIIS isolation
- engine-version isolation
- catalog-version isolation
