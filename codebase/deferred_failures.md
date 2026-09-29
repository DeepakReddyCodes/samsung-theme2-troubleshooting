# Deferred W00 Compliance Test Failures

The following tests fail due to known downstream limitations or deferred scope that goes beyond the W01 Query Enrichment boundary.

1. **`test_irrelevant_or_contradictory_content`**
   - **Reason:** The DeterministicFallbackExtractor invents generic actions when the SIIS content does not contain relevant facts.
   - **Classification:** W02 Extractor Engine defect (Grounding boundaries for LLM extraction).

2. **`test_prompt_injection_embedded_in_siis`**
   - **Reason:** Prompt injection protection requires holistic system design inside the extraction engine to not trust embedded SIIS malicious content. W01 provides input query normalization, but W05 handles comprehensive security boundaries.
   - **Classification:** W05 Security defect.

3. **`test_catalog_deeplink_validity`**
   - **Reason:** DeeplinkResolver is modifying valid catalog URIs (e.g. `bixby://masked/act/cb03ac7425` instead of the expected `bixby://masked/act/fdd7f62e24`).
   - **Classification:** W03 Deeplink Resolution defect.

4. **`test_dummy_positive_requires_concrete_target`**
   - **Reason:** `create_grounded_dummy_positive` creates a `dummy_positive` fallback with a target when one does not concretely exist in SIIS, violating the strict dummy positive fallback condition.
   - **Classification:** W03 Deeplink Resolution defect.

5. **`test_unseen_siis_with_no_actionable_evidence_rejects`**
   - **Reason:** Similar to contradictory content, the engine falls back to generating a manual action from irrelevant/non-actionable SIIS content.
   - **Classification:** W02 Extractor Engine defect.

6. **`test_grounding_preserves_polarity`**
   - **Reason:** The current `GroundingChecker` is purely lexical and incorrectly marks "Enable the Wi-Fi connection" as grounded when the SIIS says "Disable the Wi-Fi connection". W01 normalizes polarity, but W02's `GroundingChecker` must implement the semantic grounding step correctly to catch this.
   - **Classification:** W02 Extractor Engine defect.
