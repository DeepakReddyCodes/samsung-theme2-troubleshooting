# Workstream 03 — Deeplink Resolution

Owner: Agent D

Implement metadata-based lexical + semantic retrieval, reranking, confidence gating, exact URI preservation, and dummy-positive fallback.

Acceptance: no invented URI; catalog URI is copied verbatim; catalog misses are handled only for concrete grounded targets.



Every action requiring a Settings destination must go through deeplink resolution.

Do not restrict resolution to auto actions.

Matching must use human-readable catalog metadata rather than URI semantics alone.

Use exact catalog URI.

dummy_positive is permitted only when:
1. SIIS provides a concrete Settings target;
2. no catalog URI matches that target.

Never invent a Display target as a generic fallback.
