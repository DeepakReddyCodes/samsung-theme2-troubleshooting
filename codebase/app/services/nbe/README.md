# Next-Best-Evidence (NBE) / Expected Information Gain (EIG)

## Purpose
This isolated module implements the Next-Best-Evidence (NBE) decision-making layer for the Samsung PRISM Y2026 Theme 2 project. It determines:
- Whether currently observed evidence is sufficient to resolve a troubleshooting case.
- What missing evidence would provide the highest Expected Information Gain (EIG).
- Whether acquiring that evidence is justified given its cost.

It is a deterministic mathematical engine. It *does not* generate facts, run external LLMs, or call databases.

## Core Concepts

### Expected Information Gain (EIG)
EIG determines the value of acquiring a new piece of evidence $E$ given current uncertainty about hypotheses $H$.

$EIG(E) = H(H) - \mathbb{E}_e[H(H | E=e)]$

Where:
- $H(H)$ is the Shannon entropy of the current probability distribution over hypotheses.
- $\mathbb{E}_e[H(H | E=e)]$ is the expected conditional entropy of the hypotheses after observing evidence $E$, marginalized over the possible outcomes of $E$ (True or False).

### Utility
Evidence acquisition is not free. It has a cost (e.g., user annoyance, time).
$Utility(E) = \frac{EIG(E)}{Cost(E)}$

The engine selects the candidate evidence with the highest Utility score.

### Sufficiency
If the posterior probability of the leading hypothesis exceeds a defined threshold (e.g., 0.9), the engine declares `is_sufficient=True`, meaning troubleshooting steps can proceed safely without asking more questions.

## Edge Cases Handled
1. **No Competing Hypotheses**: If only 1 hypothesis exists, it immediately returns `is_sufficient=True`.
2. **Zero Information Gain**: If all available evidence fails to change the probability distribution, EIG is 0, and no evidence is selected.
3. **Equal Utility**: Tie breaking is explicitly deterministic, resolving tied candidate outputs using their alphabetic ID sorting.
4. **Acquisition Cost**: High-cost evidence will be penalized in Utility scoring, preferring cheaper but slightly less informative evidence.
5. **Already-Observed Evidence**: The engine filters out candidates that have already been observed.

## Integration Path (Future)
This module is currently isolated for Workstream W05E. Its intended place in the pipeline:
1. `SIIS -> query enrichment -> grounded hypotheses`
2. `grounded hypotheses -> evidence assessment -> NBE Request`
3. `NBE Engine (this module) -> NBE Response`
4. If `is_sufficient`: `-> resolution / Settings intent extraction -> cache -> return`
5. If `not is_sufficient`: `-> targeted evidence acquisition (ask user question) -> loop back`

## Files
- `models.py`: Data structures (Hypothesis, Evidence, NBERequest, NBEResponse).
- `engine.py`: The deterministic calculation logic.
- `tests/test_nbe.py`: Mathematical correctness unit tests.
## Current Implementation Semantics
- The sufficiency threshold of `0.9` is an ENGINEERING DECISION, not a Samsung requirement.
- EIG computation relies on a numerical tolerance (`EIG_TOLERANCE=1e-9`) to filter out floating-point noise around zero rather than an arbitrary positive selection cutoff.
- Any evidence evaluating to missing or incomplete likelihood matrices across competing hypotheses is explicitly excluded. The engine does not fabricate `0.5` prior assignments for missing target mappings.
- Deterministic tie-breaking enforces stable selection logic by picking identical tied outputs according to alphabetic ID sorting.
- Zero-cost evidence natively scales to `+inf` utility only when mathematical EIG > numerical tolerance noise, and correctly evaluates to `0` otherwise.
