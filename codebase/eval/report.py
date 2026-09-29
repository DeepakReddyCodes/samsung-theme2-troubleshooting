import json
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent

def generate_markdown_report(json_report_path: Path, output_markdown_path: Path):
    if not json_report_path.exists():
        print(f"Error: JSON report not found at {json_report_path}")
        return

    with open(json_report_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    md_content = f"""# W06 Evaluation and Benchmarking Report

## Metadata
- **Total Scenarios Evaluated**: {data['metadata']['total_evaluated']}
- **Total Evaluator Errors**: {data['metadata']['total_eval_errors']}
- **Timestamp**: {data['metadata']['timestamp']}

## 1. Grounding (Measured via Lexical Approximation)
- **Unseen Actionable Scenarios Checked**: {data['grounding']['unseen_actionable_total']}
- **Grounded Action Outputs Detected**: {data['grounding']['measured_unseen_grounded_actions']}

## 2. Empty Response Semantics
- **Correctly Empty (Safe Rejection)**: {data['empty_response_semantics']['correctly_empty']}
- **Incorrectly Empty (Failed Extraction)**: {data['empty_response_semantics']['incorrectly_empty']}

## 3. Action Validity (Schema & Formatting)
- **Canonical Scenarios Valid Actions**: {data['action_validity']['canonical_valid_actions']}
- **Paraphrase Scenarios Valid Actions**: {data['action_validity']['paraphrase_valid_actions']}

## 4. Deeplink Resolution
- **Valid Catalog Matches**: {data['deeplink_resolution']['catalog_matches']}
- **Dummy Positive Fallbacks (Valid)**: {data['deeplink_resolution']['dummy_positives']}
- **Invalid Attempts (e.g. malformed or lacking concrete target)**: {data['deeplink_resolution']['invalid_attempts']}

## 5. Adversarial Safety & Generalization
- **Safely Rejected (422 / Empty)**: {data['adversarial_safety']['safely_rejected_422_or_empty']}
- **Safely Ignored Malicious Content (Action Output Valid)**: {data['adversarial_safety']['safely_ignored_malicious_content']}
- **Unsafe Propagation (Vulnerability)**: {data['adversarial_safety']['unsafe_propagation']}

## 6. Polarity Correctness
- **Strict Semantic Correctness Count**: {data['polarity']['semantic_correctness_count']} / {data['polarity']['total_polarity_cases']} total polarity cases

## 7. Latency (ms)
- **Canonical**: p50: {data['latency_ms']['canonical']['p50']:.2f} | p95: {data['latency_ms']['canonical']['p95']:.2f} | p99: {data['latency_ms']['canonical']['p99']:.2f}
- **Paraphrase**: p50: {data['latency_ms']['paraphrase']['p50']:.2f} | p95: {data['latency_ms']['paraphrase']['p95']:.2f} | p99: {data['latency_ms']['paraphrase']['p99']:.2f}
- **Unseen**: p50: {data['latency_ms']['unseen']['p50']:.2f} | p95: {data['latency_ms']['unseen']['p95']:.2f} | p99: {data['latency_ms']['unseen']['p99']:.2f}

## 8. Cost
- Cost implementation parameterized currently based on local testing (tokens currently unmetered due to deterministic/mock LLM logic in this checkpoint).

## 9. Cache Performance
- **Exact Cache Hit Rate**: {data['cache']['canonical_hit_rate']:.2f}%
- **Semantic Cache Hit Rate**: {data['cache']['semantic_hit_rate']:.2f}% (Observed value, not an explicit requirement test for this small fixture)

## Known Limitations and Defects
- The semantic cache hit rate for paraphrased queries is low due to the exact matching constraints currently present in the cache isolation strategy.
- Grounding evaluation currently uses a strict lexical overlap boundary logic which may falsely penalize sophisticated model paraphrasing (it serves as a conservative approximation, not semantic truth).
- Evaluator explicitly measures metrics based on system outputs. If the system is relying heavily on `DeterministicFallbackExtractor`, variations in extraction accuracy map directly to empty responses (incorrectly empty).
"""

    with open(output_markdown_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    print(f"Markdown report generated successfully at {output_markdown_path}")

if __name__ == "__main__":
    json_path = WORKSPACE_ROOT / "eval" / "evaluation_report.json"
    md_path = WORKSPACE_ROOT / "eval" / "evaluation_report.md"
    generate_markdown_report(json_path, md_path)
