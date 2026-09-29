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
- **Timestamp**: {data['metadata']['timestamp']}

## 1. Grounding
- **Unseen SIIS Grounded Rate**: {data['grounding']['unseen_grounded_pct']:.2f}%

## 2. Action Validity
- **Canonical Validity Rate**: {data['action_validity']['canonical_valid_pct']:.2f}%
- **Paraphrase Validity Rate**: {data['action_validity']['paraphrase_valid_pct']:.2f}%

## 3. Deeplink Resolution
- **Valid Catalog Matches**: {data['deeplink_resolution']['catalog_matches']}
- **Dummy Positive Fallbacks**: {data['deeplink_resolution']['dummy_positives']}
- **Invalid Attempts**: {data['deeplink_resolution']['invalid_attempts']}

## 4. Generalization
- **Unseen Scenarios Handled**: {data['generalization']['unseen_scenarios_handled']}
- **Adversarial Safe Rejections**: {data['generalization']['adversarial_safe_rejections']}

## 5. Polarity Correctness
- **Polarity Correctness Rate**: {data['polarity']['correctness_pct']:.2f}%

## 6. Latency (ms)
- **Canonical p50**: {data['latency_ms']['canonical_p50']:.2f}
- **Canonical p95**: {data['latency_ms']['canonical_p95']:.2f}
- **Paraphrase p50**: {data['latency_ms']['paraphrase_p50']:.2f}
- **Unseen p50**: {data['latency_ms']['unseen_p50']:.2f}

## 7. Cost
- Cost implementation parameterized currently based on local testing (tokens currently unmetered due to mock logic).

## 8. Cache Performance
- **Exact Cache Hit Rate**: {data['cache']['canonical_hit_rate']:.2f}%
- **Semantic Cache Hit Rate**: {data['cache']['semantic_hit_rate']:.2f}%

## Defect Summary
- Paraphrase and Adversarial checks currently show that exact matching does not yield 100% hits, marking areas for semantic improvements in the caching layer.
- Adversarial rejection rate requires further strictness in deterministic extraction boundaries.
"""

    with open(output_markdown_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    print(f"Markdown report generated successfully at {output_markdown_path}")

if __name__ == "__main__":
    json_path = WORKSPACE_ROOT / "eval" / "evaluation_report.json"
    md_path = WORKSPACE_ROOT / "eval" / "evaluation_report.md"
    generate_markdown_report(json_path, md_path)
