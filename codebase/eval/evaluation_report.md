# W06 Evaluation and Benchmarking Report

## Metadata
- **Total Scenarios Evaluated**: 29
- **Timestamp**: 1790689055.3807688

## 1. Grounding
- **Unseen SIIS Grounded Rate**: 100.00%

## 2. Action Validity
- **Canonical Validity Rate**: 100.00%
- **Paraphrase Validity Rate**: 100.00%

## 3. Deeplink Resolution
- **Valid Catalog Matches**: 10
- **Dummy Positive Fallbacks**: 0
- **Invalid Attempts**: 0

## 4. Generalization
- **Unseen Scenarios Handled**: 3
- **Adversarial Safe Rejections**: 0

## 5. Polarity Correctness
- **Polarity Correctness Rate**: 100.00%

## 6. Latency (ms)
- **Canonical p50**: 2.23
- **Canonical p95**: 3.24
- **Paraphrase p50**: 1.92
- **Unseen p50**: 2.07

## 7. Cost
- Cost implementation parameterized currently based on local testing (tokens currently unmetered due to mock logic).

## 8. Cache Performance
- **Exact Cache Hit Rate**: 100.00%
- **Semantic Cache Hit Rate**: 0.00%

## Defect Summary
- Paraphrase and Adversarial checks currently show that exact matching does not yield 100% hits, marking areas for semantic improvements in the caching layer.
- Adversarial rejection rate requires further strictness in deterministic extraction boundaries.
