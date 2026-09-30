"""Next-Best-Evidence (NBE) Decision Engine for Smart Guided Troubleshooting.

Orchestrates Bayesian hypothesis evaluation, uncertainty estimation,
and mathematical EIG question selection.
"""
import logging
from typing import Any, Dict, List, Optional, Set

from app.services.nbe.eig_calculator import (
    calculate_shannon_entropy,
    compute_evidence_eig,
    update_bayesian_posterior,
    validate_hypotheses,
    validate_likelihood_matrix,
)
from app.services.nbe.models import CandidateEvidence, Hypothesis, NBEResult

logger = logging.getLogger(__name__)

DEFAULT_ENTROPY_THRESHOLD = 0.45  # bits
DEFAULT_CONFIDENCE_THRESHOLD = 0.85  # max posterior probability


class NBEEngine:
    """Decision engine implementing Next-Best-Evidence and EIG information theory."""

    def __init__(
        self,
        entropy_threshold: float = DEFAULT_ENTROPY_THRESHOLD,
        confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
    ):
        self.entropy_threshold = entropy_threshold
        self.confidence_threshold = confidence_threshold

    def evaluate(
        self,
        hypotheses: List[Hypothesis],
        candidate_evidence: Optional[List[CandidateEvidence]] = None,
        observed_evidence: Optional[Dict[str, str]] = None,
    ) -> NBEResult:
        """Evaluate evidence sufficiency and select the most informative next evidence.
        
        Args:
            hypotheses: Candidate diagnostic hypotheses with prior weights.
            candidate_evidence: Available evidence tests/questions to acquire.
            observed_evidence: Dict of already observed {evidence_id: outcome}.
            
        Returns:
            NBEResult indicating whether evidence is sufficient or what question to ask next.
        """
        # 1. Validate hypotheses and get normalized prior distribution
        prior_dist = validate_hypotheses(hypotheses)
        h_map = {h.id: h for h in hypotheses}

        candidates = candidate_evidence or []
        # Check duplicate evidence IDs
        seen_ev_ids: Set[str] = set()
        for ev in candidates:
            if ev.id in seen_ev_ids:
                raise ValueError(f"Duplicate candidate evidence id '{ev.id}' detected.")
            seen_ev_ids.add(ev.id)
            validate_likelihood_matrix(ev, hypotheses)

        # 2. Apply existing observations via Bayesian updating
        ev_map = {ev.id: ev for ev in candidates}
        current_dist = dict(prior_dist)

        if observed_evidence:
            for ev_id, outcome in observed_evidence.items():
                if ev_id in ev_map:
                    current_dist = update_bayesian_posterior(
                        prior_dist=current_dist,
                        evidence=ev_map[ev_id],
                        observed_outcome=outcome,
                    )
                else:
                    logger.warning(f"Observed evidence id '{ev_id}' not found in candidate pool; skipping.")

        # 3. Assess current uncertainty
        current_entropy = calculate_shannon_entropy(current_dist)
        top_h_id = max(current_dist, key=current_dist.get)
        top_confidence = current_dist[top_h_id]
        top_hypothesis = h_map.get(top_h_id)

        # 4. Check sufficiency condition
        is_sufficient = (
            top_confidence >= self.confidence_threshold
            or current_entropy <= self.entropy_threshold
            or len(hypotheses) == 1
        )

        if is_sufficient:
            return NBEResult(
                is_sufficient=True,
                top_hypothesis=top_hypothesis,
                top_hypothesis_confidence=round(top_confidence, 4),
                current_entropy=round(current_entropy, 4),
                selected_evidence=None,
                selected_eig=0.0,
                selected_utility=0.0,
                posterior_distribution={k: round(v, 4) for k, v in current_dist.items()},
                explanation=f"Evidence is sufficient. Leading hypothesis '{top_h_id}' has {top_confidence:.1%} confidence (entropy: {current_entropy:.3f} bits).",
            )

        # 5. Evidence is insufficient: compute EIG for remaining unobserved candidates
        observed_ids = set(observed_evidence.keys()) if observed_evidence else set()
        unobserved_candidates = [ev for ev in candidates if ev.id not in observed_ids]

        if not unobserved_candidates:
            # Insufficient evidence but no more tests available -> proceed with top hypothesis
            return NBEResult(
                is_sufficient=True,
                top_hypothesis=top_hypothesis,
                top_hypothesis_confidence=round(top_confidence, 4),
                current_entropy=round(current_entropy, 4),
                selected_evidence=None,
                selected_eig=0.0,
                selected_utility=0.0,
                posterior_distribution={k: round(v, 4) for k, v in current_dist.items()},
                explanation=f"No further candidate evidence available. Best-effort resolution with '{top_h_id}' ({top_confidence:.1%}).",
            )

        # Rank candidates by Utility (EIG / Cost * Availability) with deterministic tie breaking
        rankings: List[Dict[str, Any]] = []
        for ev in unobserved_candidates:
            eig, utility, outcome_posteriors = compute_evidence_eig(current_dist, ev)
            rankings.append({
                "evidence": ev,
                "evidence_id": ev.id,
                "eig": eig,
                "utility": utility,
                "cost": ev.cost,
                "availability": ev.availability,
                "outcome_posteriors": outcome_posteriors,
            })

        # Deterministic sorting: highest utility, highest EIG, alphabetical evidence ID
        rankings.sort(key=lambda r: (-r["utility"], -r["eig"], r["evidence_id"]))

        top_rank = rankings[0]
        selected_ev = top_rank["evidence"]

        if top_rank["eig"] <= 1e-4:
            # All available tests have zero information gain
            return NBEResult(
                is_sufficient=True,
                top_hypothesis=top_hypothesis,
                top_hypothesis_confidence=round(top_confidence, 4),
                current_entropy=round(current_entropy, 4),
                selected_evidence=None,
                selected_eig=0.0,
                selected_utility=0.0,
                all_evidence_rankings=rankings,
                posterior_distribution={k: round(v, 4) for k, v in current_dist.items()},
                explanation=f"Remaining candidate tests offer no further information gain. Proceeding with '{top_h_id}'.",
            )

        return NBEResult(
            is_sufficient=False,
            top_hypothesis=top_hypothesis,
            top_hypothesis_confidence=round(top_confidence, 4),
            current_entropy=round(current_entropy, 4),
            selected_evidence=selected_ev,
            selected_eig=round(top_rank["eig"], 4),
            selected_utility=round(top_rank["utility"], 4),
            all_evidence_rankings=rankings,
            posterior_distribution={k: round(v, 4) for k, v in current_dist.items()},
            explanation=(
                f"Evidence insufficient (entropy: {current_entropy:.3f} bits). "
                f"Selected Next-Best-Evidence '{selected_ev.id}' (EIG: {top_rank['eig']:.3f} bits, Utility: {top_rank['utility']:.3f})."
            ),
        )
