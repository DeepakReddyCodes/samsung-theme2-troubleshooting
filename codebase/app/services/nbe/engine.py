import math
from typing import Dict, List, Optional
from .models import NBERequest, NBEResponse, SelectedEvidence

class NBEEvaluationEngine:
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
                if e_id in likelihoods and h_id in likelihoods[e_id]:
                    p_e_given_h = likelihoods[e_id][h_id]
                    if not is_true:
                        p_e_given_h = 1.0 - p_e_given_h
                    prob *= p_e_given_h
                else:
                    # If likelihood is unknown, assume it doesn't inform the hypothesis
                    # (Uniform likelihood 0.5)
                    prob *= 0.5
            unnormalized_posteriors[h_id] = prob

        total_prob = sum(unnormalized_posteriors.values())
        if total_prob == 0:
            # Handle zero total probability by reverting to uniform distribution over priors
            return {h_id: 1.0 / len(priors) for h_id in priors}

        return {h_id: p / total_prob for h_id, p in unnormalized_posteriors.items()}

    def evaluate(self, request: NBERequest) -> NBEResponse:
        if not request.hypotheses:
            return NBEResponse(
                is_sufficient=False,
                posterior_probabilities={}
            )

        # 1. Structure data
        priors = {h.id: h.prior_probability for h in request.hypotheses}

        # Normalize priors if they don't sum to 1
        total_prior = sum(priors.values())
        if total_prior > 0:
            priors = {h: p / total_prior for h, p in priors.items()}
        else:
            priors = {h: 1.0 / len(priors) for h in priors}

        observations = {o.evidence_id: o.is_true for o in request.observations}

        likelihoods = {} # likelihoods[e_id][h_id] = P(E=True|H)
        for lh in request.likelihoods:
            if lh.evidence_id not in likelihoods:
                likelihoods[lh.evidence_id] = {}
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

            # Calculate P(Candidate=True) and P(Candidate=False)
            p_e_true = 0.0
            for h_id, p_h in current_posteriors.items():
                p_e_given_h = likelihoods.get(candidate.id, {}).get(h_id, 0.5)
                p_e_true += p_h * p_e_given_h

            p_e_false = 1.0 - p_e_true

            # Expected entropy if candidate is True
            posteriors_if_true = self.get_posterior_probabilities(
                current_posteriors, {candidate.id: True}, likelihoods
            )
            entropy_if_true = self.calculate_entropy(list(posteriors_if_true.values()))

            # Expected entropy if candidate is False
            posteriors_if_false = self.get_posterior_probabilities(
                current_posteriors, {candidate.id: False}, likelihoods
            )
            entropy_if_false = self.calculate_entropy(list(posteriors_if_false.values()))

            # E_e[H(H | E=e)]
            expected_conditional_entropy = (p_e_true * entropy_if_true) + (p_e_false * entropy_if_false)

            # EIG(E) = H(H) - E_e[H(H | E=e)]
            eig = current_entropy - expected_conditional_entropy

            # Utility = EIG / Cost
            cost = max(candidate.cost, 0.001) # Avoid division by zero
            utility = eig / cost

            if utility > max_utility and eig > 0.0001: # Small threshold for meaningful EIG
                max_utility = utility
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
