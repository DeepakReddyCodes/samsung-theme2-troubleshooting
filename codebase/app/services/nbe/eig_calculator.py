"""Mathematical Expected Information Gain (EIG) calculation engine.

Implements information-theoretic entropy reduction for Bayesian diagnostic spaces:
H(H) = - sum_i P(h_i) * log2(P(h_i))
P(E=e) = sum_i P(E=e | h_i) * P(h_i)
P(h_i | E=e) = P(E=e | h_i) * P(h_i) / P(E=e)
H(H | E=e) = - sum_i P(h_i | E=e) * log2(P(h_i | E=e))
EIG(E) = H(H) - E_e[ H(H | E=e) ]
Utility(E) = (EIG(E) / Cost(E)) * Availability(E)
"""
import math
from typing import Dict, List, Set, Tuple

from app.services.nbe.models import CandidateEvidence, Hypothesis


def calculate_shannon_entropy(distribution: Dict[str, float]) -> float:
    """Compute Shannon entropy in bits for a discrete probability distribution.
    
    H(X) = - sum_{x} P(x) * log2(P(x))
    """
    entropy = 0.0
    for prob in distribution.values():
        if prob > 1e-12:
            entropy -= prob * math.log2(prob)
    return max(0.0, entropy)


def validate_hypotheses(hypotheses: List[Hypothesis]) -> Dict[str, float]:
    """Validate hypothesis list and compute normalized prior distribution."""
    if not hypotheses:
        raise ValueError("Hypothesis space must not be empty.")

    seen_ids: Set[str] = set()
    total_prior = 0.0
    priors: Dict[str, float] = {}

    for h in hypotheses:
        if h.id in seen_ids:
            raise ValueError(f"Duplicate hypothesis id '{h.id}' detected in hypothesis space.")
        seen_ids.add(h.id)
        if h.prior < 0.0:
            raise ValueError(f"Hypothesis '{h.id}' has negative prior: {h.prior}")
        total_prior += h.prior
        priors[h.id] = h.prior

    if total_prior <= 1e-12:
        raise ValueError("Sum of hypothesis priors must be greater than zero.")

    # Normalize priors so they sum to 1.0
    return {h_id: p / total_prior for h_id, p in priors.items()}


def validate_likelihood_matrix(
    evidence: CandidateEvidence,
    hypotheses: List[Hypothesis],
) -> None:
    """Strictly validate that likelihood matrix defines valid distributions for all hypotheses.
    
    Does NOT silently default missing hypotheses to 0.5.
    """
    matrix = evidence.likelihood_matrix
    outcomes = set(evidence.outcomes)

    for h in hypotheses:
        if h.id not in matrix:
            raise ValueError(
                f"Candidate evidence '{evidence.id}' missing likelihood distribution for hypothesis '{h.id}'"
            )
        h_dist = matrix[h.id]
        if not isinstance(h_dist, dict):
            raise ValueError(
                f"Candidate evidence '{evidence.id}' likelihood for '{h.id}' must be a dict of outcome probabilities"
            )

        # Check all outcomes are accounted for
        total_p = 0.0
        for outcome in evidence.outcomes:
            if outcome not in h_dist:
                raise ValueError(
                    f"Candidate evidence '{evidence.id}' missing probability for outcome '{outcome}' under hypothesis '{h.id}'"
                )
            p = h_dist[outcome]
            if p < -1e-6 or p > 1.0 + 1e-6:
                raise ValueError(
                    f"Invalid probability {p} for outcome '{outcome}' under hypothesis '{h.id}'"
                )
            total_p += p

        if abs(total_p - 1.0) > 1e-3:
            raise ValueError(
                f"Likelihood probabilities for hypothesis '{h.id}' on evidence '{evidence.id}' must sum to 1.0 (got {total_p:.4f})"
            )


def update_bayesian_posterior(
    prior_dist: Dict[str, float],
    evidence: CandidateEvidence,
    observed_outcome: str,
) -> Dict[str, float]:
    """Compute posterior distribution P(H | E=e) given an observed outcome."""
    if observed_outcome not in evidence.outcomes:
        raise ValueError(
            f"Observed outcome '{observed_outcome}' is not a valid outcome for evidence '{evidence.id}' (valid: {evidence.outcomes})"
        )

    marginal_p = 0.0
    unnormalized_posteriors: Dict[str, float] = {}

    for h_id, prior in prior_dist.items():
        likelihood = evidence.likelihood_matrix[h_id].get(observed_outcome, 0.0)
        joint = likelihood * prior
        unnormalized_posteriors[h_id] = joint
        marginal_p += joint

    if marginal_p <= 1e-12:
        # Impossible observation under current model; preserve prior
        return dict(prior_dist)

    return {h_id: joint / marginal_p for h_id, joint in unnormalized_posteriors.items()}


def compute_evidence_eig(
    prior_dist: Dict[str, float],
    evidence: CandidateEvidence,
) -> Tuple[float, float, Dict[str, Dict[str, float]]]:
    """Compute the Expected Information Gain and Utility for candidate evidence.
    
    Returns:
        (eig_bits, utility_score, outcome_posteriors)
    """
    current_entropy = calculate_shannon_entropy(prior_dist)
    expected_conditional_entropy = 0.0
    outcome_posteriors: Dict[str, Dict[str, float]] = {}

    for outcome in evidence.outcomes:
        # Marginal probability P(E=e) = sum_i P(E=e | h_i) * P(h_i)
        marginal_p = sum(
            evidence.likelihood_matrix[h_id].get(outcome, 0.0) * prior
            for h_id, prior in prior_dist.items()
        )

        if marginal_p > 1e-12:
            # Posterior P(h_i | E=e)
            post_dist = {
                h_id: (evidence.likelihood_matrix[h_id].get(outcome, 0.0) * prior) / marginal_p
                for h_id, prior in prior_dist.items()
            }
            outcome_posteriors[outcome] = post_dist
            cond_entropy = calculate_shannon_entropy(post_dist)
            expected_conditional_entropy += marginal_p * cond_entropy
        else:
            outcome_posteriors[outcome] = dict(prior_dist)

    eig = max(0.0, current_entropy - expected_conditional_entropy)
    cost = max(evidence.cost, 1e-6)
    utility = (eig / cost) * evidence.availability

    return eig, utility, outcome_posteriors
