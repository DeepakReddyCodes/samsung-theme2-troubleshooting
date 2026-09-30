import math
from typing import Dict, List, Optional
from .models import NBERequest, NBEResponse, SelectedEvidence

class NBEEvaluationEngine:
    # Tolerance for floating point EIG comparisons to avoid selecting numerical noise
    EIG_TOLERANCE = 1e-9

    @staticmethod
    def calculate_entropy(probabilities: List[float]) -> float:
        """Calculates Shannon entropy."""
        entropy = 0.0
        for p in probabilities:
            if p > 0:
                entropy -= p * math.log2(p)
        return entropy

    @staticmethod
    def get_posterior_probabilities(
        priors: Dict[str, float],
        observations: Dict[str, bool],
        likelihoods: Dict[str, Dict[str, float]]
    ) -> Dict[str, float]:
        """Calculates posterior probabilities given observations using Bayes' theorem."""
        unnormalized_posteriors = {}
        for h_id, prior in priors.items():
            prob = prior
            for e_id, is_true in observations.items():
                if e_id not in likelihoods or h_id not in likelihoods[e_id]:
                    raise ValueError(f"Missing explicit likelihood for observed evidence {e_id} and hypothesis {h_id}")

                p_e_given_h = likelihoods[e_id][h_id]
                if not is_true:
                    p_e_given_h = 1.0 - p_e_given_h
                prob *= p_e_given_h
            unnormalized_posteriors[h_id] = prob

        total_prob = sum(unnormalized_posteriors.values())
        if total_prob == 0:
            raise ValueError("Zero total posterior probability: observations contradict all hypotheses.")

        return {h_id: p / total_prob for h_id, p in unnormalized_posteriors.items()}

    def evaluate(self, request: NBERequest) -> NBEResponse:
        if not request.hypotheses:
            return NBEResponse(
                is_sufficient=False,
                posterior_probabilities={}
            )

        # 1. Structure data
        priors = {}
        for h in request.hypotheses:
            if h.id in priors:
                raise ValueError(f"Duplicate hypothesis ID: {h.id}")
            priors[h.id] = h.prior_probability

        seen_evidence = set()
        for e in request.available_evidence:
            if e.id in seen_evidence:
                raise ValueError(f"Duplicate evidence candidate ID: {e.id}")
            seen_evidence.add(e.id)

        # Observations must refer to explicitly declared evidence items
        seen_observations = set()
        for o in request.observations:
            if o.evidence_id not in seen_evidence:
                raise ValueError(f"Observation references unknown evidence_id: {o.evidence_id}")
            if o.evidence_id in seen_observations:
                raise ValueError(f"Duplicate observation ID: {o.evidence_id}")
            seen_observations.add(o.evidence_id)

        # Normalize priors if they don't sum to 1
        total_prior = sum(priors.values())
        if total_prior <= 0:
            raise ValueError("Total prior probability must be strictly positive.")
        priors = {h: p / total_prior for h, p in priors.items()}

        observations = {o.evidence_id: o.is_true for o in request.observations}

        # Validate that likelihoods correctly refer back to explicitly declared evidence.
        likelihoods = {} # likelihoods[e_id][h_id] = P(E=True|H)
        for lh in request.likelihoods:
            if lh.hypothesis_id not in priors:
                raise ValueError(f"Likelihood references unknown hypothesis_id: {lh.hypothesis_id}")
            if lh.evidence_id not in seen_evidence:
                raise ValueError(f"Likelihood references unknown evidence_id: {lh.evidence_id}")
            if lh.evidence_id not in likelihoods:
                likelihoods[lh.evidence_id] = {}
            if lh.hypothesis_id in likelihoods[lh.evidence_id]:
                raise ValueError(f"Duplicate likelihood mapping for Evidence {lh.evidence_id}, Hypothesis {lh.hypothesis_id}")
            likelihoods[lh.evidence_id][lh.hypothesis_id] = lh.probability_true

        # 2. Calculate current posteriors given existing observations
        current_posteriors = self.get_posterior_probabilities(priors, observations, likelihoods)

        # 3. Check for sufficiency
        top_h_id = max(current_posteriors, key=current_posteriors.get)
        top_prob = current_posteriors[top_h_id]

        if top_prob >= request.sufficiency_threshold or len(request.hypotheses) == 1:
            return NBEResponse(
                is_sufficient=True,
                top_hypothesis_id=top_h_id,
                top_hypothesis_probability=top_prob,
                posterior_probabilities=current_posteriors
            )

        # 4. Calculate EIG for candidate evidence
        current_entropy = self.calculate_entropy(list(current_posteriors.values()))

        best_candidate: Optional[SelectedEvidence] = None
        max_utility = -float('inf')

        for candidate in request.available_evidence:
            if candidate.id in observations:
                continue # Already observed

            # Ensure complete likelihood matrix for this candidate over all hypotheses
            candidate_likelihoods = likelihoods.get(candidate.id, {})
            has_missing_likelihoods = False
            for h_id in current_posteriors:
                if h_id not in candidate_likelihoods:
                    has_missing_likelihoods = True
                    break

            # If we don't have likelihoods for every hypothesis, we cannot evaluate its info gain accurately.
            # (We do not fabricate 0.5 likelihoods for candidate evaluation)
            if has_missing_likelihoods:
                continue

            # Calculate P(Candidate=True) and P(Candidate=False)
            p_e_true = 0.0
            for h_id, p_h in current_posteriors.items():
                p_e_given_h = candidate_likelihoods[h_id]
                p_e_true += p_h * p_e_given_h

            p_e_false = 1.0 - p_e_true

            # Expected entropy if candidate is True
            if p_e_true > 0.0:
                posteriors_if_true = self.get_posterior_probabilities(
                    current_posteriors, {candidate.id: True}, likelihoods
                )
                entropy_if_true = self.calculate_entropy(list(posteriors_if_true.values()))
            else:
                entropy_if_true = 0.0

            # Expected entropy if candidate is False
            if p_e_false > 0.0:
                posteriors_if_false = self.get_posterior_probabilities(
                    current_posteriors, {candidate.id: False}, likelihoods
                )
                entropy_if_false = self.calculate_entropy(list(posteriors_if_false.values()))
            else:
                entropy_if_false = 0.0

            # E_e[H(H | E=e)]
            expected_conditional_entropy = (p_e_true * entropy_if_true) + (p_e_false * entropy_if_false)

            # EIG(E) = H(H) - E_e[H(H | E=e)]
            eig = current_entropy - expected_conditional_entropy

            # Zero out EIG if it's purely floating point negative noise.
            # Genuinely positive EIG (even < 1e-9) must be preserved.
            if eig < 0.0 and abs(eig) <= self.EIG_TOLERANCE:
                eig = 0.0

            is_informative = eig > 0.0

            # Utility = EIG / Cost
            cost = candidate.cost
            if cost == 0.0:
                utility = float('inf') if is_informative else 0.0
            else:
                utility = eig / cost

            # Only consider evidence if it gives positive info gain
            if is_informative:
                if utility > max_utility:
                    max_utility = utility
                    best_candidate = SelectedEvidence(
                        evidence_id=candidate.id,
                        eig_score=eig,
                        utility_score=utility
                    )
                elif utility == max_utility and best_candidate is not None:
                    # Deterministic tie-breaking by ID if utilities are tied (including infinite)
                    if candidate.id < best_candidate.evidence_id:
                        best_candidate = SelectedEvidence(
                            evidence_id=candidate.id,
                            eig_score=eig,
                            utility_score=utility
                        )

        return NBEResponse(
            is_sufficient=False,
            top_hypothesis_id=top_h_id,
            top_hypothesis_probability=top_prob,
            selected_evidence=best_candidate,
            posterior_probabilities=current_posteriors
        )
