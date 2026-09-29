# W06 Evaluation and Benchmarking Report

## Metadata
- **Total Scenarios Evaluated**: 37
- **Total Evaluator Errors**: 0
- **Timestamp**: 1790691945.4181218

## 1. Grounding (Measured via Lexical Approximation)
- **Unseen Actionable Scenarios Checked**: 4
- **Grounded Action Outputs Detected**: 4
*(Note: This uses a lexical bounding approximation and does not establish semantic entailment.)*

## 2. Empty Response Semantics
- **Correctly Empty (Safe Rejection)**: 0
- **Incorrectly Empty (Failed Extraction)**: 0

## 3. Action Validity (Schema & Formatting)
- **Canonical Scenarios Valid Actions**: 20
- **Paraphrase Scenarios Valid Actions**: 4

## 4. Deeplink Resolution
- **Valid Catalog Matches**: 10
- **Dummy Positive Fallbacks (Valid Formatting)**: 0
- **Invalid Attempts (e.g. malformed or lacking concrete target)**: 0
*(Limitation: The evaluator checks valid formatting and target description length for dummy positives, but it cannot prove end-to-end SIIS provenance from the output JSON alone.)*

## 5. Adversarial Safety & Generalization
- **Safely Rejected (422 / Empty)**: 0
- **Safely Ignored Malicious Content (Action Output Valid)**: 0
- **Unsafe Propagation (Vulnerability)**: 4

## 6. Polarity Correctness
- **Strict Semantic Correctness Count**: 2 / 5 total polarity cases

## 7. Latency (ms)
- **Canonical**: p50: 4.42 | p95: 12.73 | p99: 39.53
- **Paraphrase**: p50: 54.19 | p95: 625.92 | p99: 699.50
- **Unseen**: p50: 2.61 | p95: 3.57 | p99: 3.70

## 8. Cost
- Cost implementation parameterized currently based on local testing (tokens currently unmetered due to deterministic/mock LLM logic in this checkpoint).

## 9. Cache Performance
- **Exact Cache Hit Rate**: 100.00%
- **Semantic Cache Hit Rate**: 50.00% (Observed value on this specific limited dataset)

## Evaluation Dataset Sizes
- Canonical Fixtures Evaluated: 20
- Paraphrase Fixtures Evaluated: 4
- Unseen SIIS Scenarios Evaluated: 4
- Adversarial Scenarios Evaluated: 4
- Polarity Scenarios Evaluated: 5
*(Note: These sizes represent small validation datasets for correctness behavior mapping. They do not imply statistically comprehensive generalization.)*

## Known Limitations and Defects
- The semantic cache hit rate for paraphrased queries is low due to the exact matching constraints currently present in the cache isolation strategy.
- Grounding evaluation currently uses a strict lexical overlap boundary logic which may falsely penalize sophisticated model paraphrasing (it serves as a conservative approximation, not semantic truth).
- Evaluator explicitly measures metrics based on system outputs. If the system is relying heavily on `DeterministicFallbackExtractor`, variations in extraction accuracy map directly to empty responses (incorrectly empty).
