# W06 Evaluation and Benchmarking Report

## Metadata
- **Total Scenarios Evaluated**: 37
- **Total Evaluator Errors**: 0
- **Timestamp**: 1790695865.3742146

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
- **Valid Exact Catalog Matches**: 10
- **Valid Validation Catalog Matches**: 8
- **Dummy-Positive Candidate / Unable to Verify Provenance**: 0
- **Invalid Attempts (e.g. malformed or lacking description)**: 0
*(Limitation: The evaluator checks valid formatting and checks for the presence of a description for dummy positives, but it cannot prove end-to-end SIIS provenance from the final JSON alone. It is classified as a candidate, not automatically verified correct.)*

## 5. Adversarial Safety & Generalization
- **Safely Rejected (422 / Empty)**: 0
- **Safely Ignored Malicious Content (Action Output Valid)**: 0
- **Unsafe Propagation (Vulnerability)**: 4

## 6. Polarity Correctness
- **Strict Semantic Correctness Count**: 2 / 5 total polarity cases

## 7. Latency (ms)
- **Canonical**: p50: 3.30 | p95: 7.05 | p99: 8.41
- **Paraphrase**: p50: 247.12 | p95: 703.56 | p99: 733.63
- **Unseen**: p50: 2.39 | p95: 3.75 | p99: 3.90
*(Limitation: The latencies above rely on deterministic/offline benchmarking and cold-path fallbacks. They do not represent real LLM/API latency, which will be measured eventually.)*

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
