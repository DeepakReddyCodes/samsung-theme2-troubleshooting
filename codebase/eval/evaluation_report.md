# W06 Evaluation and Benchmarking Report

## Metadata
- **Total Scenarios Evaluated**: 36
- **Total Evaluator Errors**: 0
- **Timestamp**: 1790689975.5566697

## 1. Grounding (Measured via Lexical Approximation)
- **Unseen Actionable Scenarios Checked**: 4
- **Grounded Action Outputs Detected**: 4

## 2. Empty Response Semantics
- **Correctly Empty (Safe Rejection)**: 0
- **Incorrectly Empty (Failed Extraction)**: 0

## 3. Action Validity (Schema & Formatting)
- **Canonical Scenarios Valid Actions**: 20
- **Paraphrase Scenarios Valid Actions**: 4

## 4. Deeplink Resolution
- **Valid Catalog Matches**: 10
- **Dummy Positive Fallbacks (Valid)**: 0
- **Invalid Attempts (e.g. malformed or lacking concrete target)**: 0

## 5. Adversarial Safety & Generalization
- **Safely Rejected (422 / Empty)**: 0
- **Safely Ignored Malicious Content (Action Output Valid)**: 0
- **Unsafe Propagation (Vulnerability)**: 4

## 6. Polarity Correctness
- **Strict Semantic Correctness Count**: 2 / 4 total polarity cases

## 7. Latency (ms)
- **Canonical**: p50: 3.89 | p95: 11.35 | p99: 37.89
- **Paraphrase**: p50: 260.07 | p95: 742.24 | p99: 774.09
- **Unseen**: p50: 5.80 | p95: 929.03 | p99: 1059.01

## 8. Cost
- Cost implementation parameterized currently based on local testing (tokens currently unmetered due to deterministic/mock LLM logic in this checkpoint).

## 9. Cache Performance
- **Exact Cache Hit Rate**: 100.00%
- **Semantic Cache Hit Rate**: 50.00% (Observed value, not an explicit requirement test for this small fixture)

## Known Limitations and Defects
- The semantic cache hit rate for paraphrased queries is low due to the exact matching constraints currently present in the cache isolation strategy.
- Grounding evaluation currently uses a strict lexical overlap boundary logic which may falsely penalize sophisticated model paraphrasing (it serves as a conservative approximation, not semantic truth).
- Evaluator explicitly measures metrics based on system outputs. If the system is relying heavily on `DeterministicFallbackExtractor`, variations in extraction accuracy map directly to empty responses (incorrectly empty).
