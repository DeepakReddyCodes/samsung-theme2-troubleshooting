import pytest
from app.services.nbe.models import (
    Evidence,
    Hypothesis,
    EvidenceObservation,
    EvidenceLikelihood,
    NBERequest
)
from app.services.nbe.engine import NBEEvaluationEngine

@pytest.fixture
def engine():
    return NBEEvaluationEngine()

def test_entropy_calculation(engine):
    assert engine.calculate_entropy([1.0, 0.0]) == 0.0
    assert engine.calculate_entropy([0.5, 0.5]) == 1.0

    # 3 options: log2(3) approx 1.58
    entropy_3 = engine.calculate_entropy([1/3, 1/3, 1/3])
    assert 1.58 < entropy_3 < 1.59

def test_posterior_calculation(engine):
    priors = {"h1": 0.5, "h2": 0.5}
    observations = {"e1": True}
    likelihoods = {
        "e1": {"h1": 0.8, "h2": 0.2}
    }

    posteriors = engine.get_posterior_probabilities(priors, observations, likelihoods)
    # P(e1) = 0.5*0.8 + 0.5*0.2 = 0.5
    # P(h1|e1) = (0.8 * 0.5) / 0.5 = 0.8
    # P(h2|e1) = (0.2 * 0.5) / 0.5 = 0.2
    assert posteriors["h1"] == 0.8
    assert posteriors["h2"] == 0.2

def test_nbe_evaluate_sufficient_evidence(engine):
    req = NBERequest(
        hypotheses=[
            Hypothesis(id="h1", description="Wifi is broken", prior_probability=0.95),
            Hypothesis(id="h2", description="Bluetooth is broken", prior_probability=0.05)
        ],
        available_evidence=[],
        observations=[],
        likelihoods=[],
        sufficiency_threshold=0.9
    )

    resp = engine.evaluate(req)
    assert resp.is_sufficient is True
    assert resp.top_hypothesis_id == "h1"

def test_nbe_evaluate_single_hypothesis(engine):
    req = NBERequest(
        hypotheses=[
            Hypothesis(id="h1", description="Only option", prior_probability=1.0)
        ],
        available_evidence=[Evidence(id="e1", description="Test", cost=1.0)],
        observations=[],
        likelihoods=[]
    )

    resp = engine.evaluate(req)
    assert resp.is_sufficient is True
    assert resp.top_hypothesis_id == "h1"

def test_nbe_evaluate_selects_best_evidence(engine):
    req = NBERequest(
        hypotheses=[
            Hypothesis(id="h1", description="Problem A", prior_probability=0.5),
            Hypothesis(id="h2", description="Problem B", prior_probability=0.5)
        ],
        available_evidence=[
            Evidence(id="e1", description="Weak evidence", cost=1.0),
            Evidence(id="e2", description="Strong evidence", cost=1.0)
        ],
        observations=[],
        likelihoods=[
            EvidenceLikelihood(evidence_id="e1", hypothesis_id="h1", probability_true=0.6),
            EvidenceLikelihood(evidence_id="e1", hypothesis_id="h2", probability_true=0.4),
            EvidenceLikelihood(evidence_id="e2", hypothesis_id="h1", probability_true=0.99),
            EvidenceLikelihood(evidence_id="e2", hypothesis_id="h2", probability_true=0.01)
        ],
        sufficiency_threshold=0.9
    )

    resp = engine.evaluate(req)
    assert resp.is_sufficient is False
    assert resp.selected_evidence is not None
    assert resp.selected_evidence.evidence_id == "e2" # e2 separates h1/h2 much better

def test_nbe_evaluate_considers_cost(engine):
    req = NBERequest(
        hypotheses=[
            Hypothesis(id="h1", description="Problem A", prior_probability=0.5),
            Hypothesis(id="h2", description="Problem B", prior_probability=0.5)
        ],
        available_evidence=[
            Evidence(id="e1", description="Good evidence, low cost", cost=1.0),
            Evidence(id="e2", description="Great evidence, huge cost", cost=100.0)
        ],
        observations=[],
        likelihoods=[
            EvidenceLikelihood(evidence_id="e1", hypothesis_id="h1", probability_true=0.8),
            EvidenceLikelihood(evidence_id="e1", hypothesis_id="h2", probability_true=0.2),
            EvidenceLikelihood(evidence_id="e2", hypothesis_id="h1", probability_true=0.99),
            EvidenceLikelihood(evidence_id="e2", hypothesis_id="h2", probability_true=0.01)
        ],
        sufficiency_threshold=0.9
    )

    resp = engine.evaluate(req)
    assert resp.is_sufficient is False
    assert resp.selected_evidence is not None
    assert resp.selected_evidence.evidence_id == "e1" # e1 is chosen because e2's cost penalizes it

def test_nbe_evaluate_no_information_gain(engine):
    req = NBERequest(
        hypotheses=[
            Hypothesis(id="h1", description="Problem A", prior_probability=0.5),
            Hypothesis(id="h2", description="Problem B", prior_probability=0.5)
        ],
        available_evidence=[
            Evidence(id="e1", description="Useless evidence", cost=1.0)
        ],
        observations=[],
        likelihoods=[
            EvidenceLikelihood(evidence_id="e1", hypothesis_id="h1", probability_true=0.5),
            EvidenceLikelihood(evidence_id="e1", hypothesis_id="h2", probability_true=0.5)
        ],
        sufficiency_threshold=0.9
    )

    resp = engine.evaluate(req)
    assert resp.is_sufficient is False
    assert resp.selected_evidence is None # e1 gives 0 EIG, so nothing is selected

def test_nbe_evaluate_already_observed(engine):
    req = NBERequest(
        hypotheses=[
            Hypothesis(id="h1", description="Problem A", prior_probability=0.5),
            Hypothesis(id="h2", description="Problem B", prior_probability=0.5)
        ],
        available_evidence=[
            Evidence(id="e1", description="Observed evidence", cost=1.0)
        ],
        observations=[
            EvidenceObservation(evidence_id="e1", is_true=True)
        ],
        likelihoods=[
            EvidenceLikelihood(evidence_id="e1", hypothesis_id="h1", probability_true=0.9),
            EvidenceLikelihood(evidence_id="e1", hypothesis_id="h2", probability_true=0.1)
        ],
        sufficiency_threshold=0.99
    )

    resp = engine.evaluate(req)
    assert resp.is_sufficient is False
    assert resp.selected_evidence is None # It's already observed
