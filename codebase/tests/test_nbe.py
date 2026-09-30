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

from pydantic import ValidationError

def test_pydantic_validation():
    with pytest.raises(ValidationError):
        Hypothesis(id="h1", description="desc", prior_probability=-0.1)
    with pytest.raises(ValidationError):
        Hypothesis(id="h1", description="desc", prior_probability=1.1)

    with pytest.raises(ValidationError):
        EvidenceLikelihood(evidence_id="e1", hypothesis_id="h1", probability_true=-0.1)
    with pytest.raises(ValidationError):
        EvidenceLikelihood(evidence_id="e1", hypothesis_id="h1", probability_true=1.1)

    with pytest.raises(ValidationError):
        Evidence(id="e1", description="desc", cost=-1.0)

    with pytest.raises(ValidationError):
        NBERequest(
            hypotheses=[Hypothesis(id="h1", description="desc", prior_probability=1.0)],
            available_evidence=[],
            likelihoods=[],
            sufficiency_threshold=1.5
        )

def test_engine_zero_total_prior(engine):
    req = NBERequest(
        hypotheses=[
            Hypothesis(id="h1", description="desc", prior_probability=0.0),
            Hypothesis(id="h2", description="desc", prior_probability=0.0)
        ],
        available_evidence=[],
        likelihoods=[]
    )
    with pytest.raises(ValueError, match="Total prior probability must be strictly positive"):
        engine.evaluate(req)

def test_engine_zero_total_posterior(engine):
    priors = {"h1": 0.5, "h2": 0.5}
    observations = {"e1": True}
    likelihoods = {
        "e1": {"h1": 0.0, "h2": 0.0}
    }
    with pytest.raises(ValueError, match="Zero total posterior probability: observations contradict all hypotheses."):
        engine.get_posterior_probabilities(priors, observations, likelihoods)

def test_engine_unavailable_likelihood_semantics(engine):
    priors = {"h1": 0.7, "h2": 0.3}
    observations = {"e1": True}
    likelihoods = {} # Unknown likelihood

    posteriors = engine.get_posterior_probabilities(priors, observations, likelihoods)
    # Should be uninformative (0.5), posterior equals prior
    assert posteriors["h1"] == pytest.approx(0.7)
    assert posteriors["h2"] == pytest.approx(0.3)

def test_eig_hand_calculated(engine):
    # Setup simple 2-hypothesis case
    req = NBERequest(
        hypotheses=[
            Hypothesis(id="h1", description="Problem A", prior_probability=0.5),
            Hypothesis(id="h2", description="Problem B", prior_probability=0.5)
        ],
        available_evidence=[
            Evidence(id="e1", description="Evidence 1", cost=1.0)
        ],
        observations=[],
        likelihoods=[
            EvidenceLikelihood(evidence_id="e1", hypothesis_id="h1", probability_true=1.0),
            EvidenceLikelihood(evidence_id="e1", hypothesis_id="h2", probability_true=0.0)
        ],
        sufficiency_threshold=0.9
    )

    # current priors are 0.5, 0.5 -> H(H) = 1.0
    # if e1 is True: P(h1|e1)=1, P(h2|e1)=0 -> H(H|e1) = 0
    # if e1 is False: P(h1|~e1)=0, P(h2|~e1)=1 -> H(H|~e1) = 0
    # EIG = 1.0 - 0 = 1.0

    resp = engine.evaluate(req)
    assert resp.selected_evidence is not None
    assert resp.selected_evidence.eig_score == pytest.approx(1.0)

def test_eig_uninformative_evidence(engine):
    req = NBERequest(
        hypotheses=[
            Hypothesis(id="h1", description="Problem A", prior_probability=0.8),
            Hypothesis(id="h2", description="Problem B", prior_probability=0.2)
        ],
        available_evidence=[
            Evidence(id="e1", description="Uninformative", cost=1.0)
        ],
        observations=[],
        likelihoods=[
            EvidenceLikelihood(evidence_id="e1", hypothesis_id="h1", probability_true=0.5),
            EvidenceLikelihood(evidence_id="e1", hypothesis_id="h2", probability_true=0.5)
        ],
        sufficiency_threshold=0.9
    )

    resp = engine.evaluate(req)
    assert resp.selected_evidence is None # Because eig is 0 (or very close)

def test_eig_discriminative_evidence(engine):
    req = NBERequest(
        hypotheses=[
            Hypothesis(id="h1", description="Problem A", prior_probability=0.5),
            Hypothesis(id="h2", description="Problem B", prior_probability=0.5)
        ],
        available_evidence=[
            Evidence(id="e1", description="Discriminative", cost=1.0)
        ],
        observations=[],
        likelihoods=[
            EvidenceLikelihood(evidence_id="e1", hypothesis_id="h1", probability_true=0.9),
            EvidenceLikelihood(evidence_id="e1", hypothesis_id="h2", probability_true=0.1)
        ],
        sufficiency_threshold=0.9
    )

    resp = engine.evaluate(req)
    assert resp.selected_evidence is not None
    assert resp.selected_evidence.eig_score > 0
    # conditional entropy should be strictly less than prior entropy
    # prior entropy = 1.0
    assert resp.selected_evidence.eig_score > 0.0
    assert resp.selected_evidence.eig_score <= 1.0

def test_eig_zero_cost_evidence(engine):
    req = NBERequest(
        hypotheses=[
            Hypothesis(id="h1", description="Problem A", prior_probability=0.5),
            Hypothesis(id="h2", description="Problem B", prior_probability=0.5)
        ],
        available_evidence=[
            Evidence(id="e1", description="Free evidence", cost=0.0) # Zero cost
        ],
        observations=[],
        likelihoods=[
            EvidenceLikelihood(evidence_id="e1", hypothesis_id="h1", probability_true=0.9),
            EvidenceLikelihood(evidence_id="e1", hypothesis_id="h2", probability_true=0.1)
        ],
        sufficiency_threshold=0.9
    )

    # Should not raise DivisionByZero
    resp = engine.evaluate(req)
    assert resp.selected_evidence is not None
    assert resp.selected_evidence.utility_score > 0 # utility will be large due to small cost substitute

def test_max_utility_tie_breaking(engine):
    req = NBERequest(
        hypotheses=[
            Hypothesis(id="h1", description="Problem A", prior_probability=0.5),
            Hypothesis(id="h2", description="Problem B", prior_probability=0.5)
        ],
        available_evidence=[
            Evidence(id="e2", description="Evidence 2", cost=1.0),
            Evidence(id="e1", description="Evidence 1", cost=1.0)
        ],
        observations=[],
        likelihoods=[
            EvidenceLikelihood(evidence_id="e2", hypothesis_id="h1", probability_true=0.9),
            EvidenceLikelihood(evidence_id="e2", hypothesis_id="h2", probability_true=0.1),
            EvidenceLikelihood(evidence_id="e1", hypothesis_id="h1", probability_true=0.9),
            EvidenceLikelihood(evidence_id="e1", hypothesis_id="h2", probability_true=0.1)
        ],
        sufficiency_threshold=0.9
    )

    resp = engine.evaluate(req)
    assert resp.selected_evidence is not None
    # since max() will keep the first strictly greater utility, tie goes to e1 (first in list)
    assert resp.selected_evidence.evidence_id == "e1"

def test_eig_impossible_branch(engine):
    # If P(E=True|H)=1 for all H, then P(E=False)=0.
    # Should not throw ValueError ("Zero total posterior probability") for the False branch because it shouldn't evaluate it.
    req = NBERequest(
        hypotheses=[
            Hypothesis(id="h1", description="Problem A", prior_probability=0.5),
            Hypothesis(id="h2", description="Problem B", prior_probability=0.5)
        ],
        available_evidence=[
            Evidence(id="e1", description="Useless 100% true evidence", cost=1.0)
        ],
        observations=[],
        likelihoods=[
            EvidenceLikelihood(evidence_id="e1", hypothesis_id="h1", probability_true=1.0),
            EvidenceLikelihood(evidence_id="e1", hypothesis_id="h2", probability_true=1.0)
        ],
        sufficiency_threshold=0.9
    )

    # EIG should be 0, not crashing
    resp = engine.evaluate(req)
    assert resp.selected_evidence is None

def test_engine_duplicate_ids(engine):
    # Test duplicate hypothesis
    with pytest.raises(ValueError, match="Duplicate hypothesis ID"):
        engine.evaluate(NBERequest(
            hypotheses=[
                Hypothesis(id="h1", description="Desc", prior_probability=0.5),
                Hypothesis(id="h1", description="Desc2", prior_probability=0.5)
            ],
            available_evidence=[],
            likelihoods=[]
        ))

    # Test duplicate candidate evidence
    with pytest.raises(ValueError, match="Duplicate evidence candidate ID"):
        engine.evaluate(NBERequest(
            hypotheses=[Hypothesis(id="h1", description="Desc", prior_probability=1.0)],
            available_evidence=[
                Evidence(id="e1", description="Desc", cost=1.0),
                Evidence(id="e1", description="Desc2", cost=2.0)
            ],
            likelihoods=[]
        ))

    # Test duplicate observations
    with pytest.raises(ValueError, match="Duplicate observation ID"):
        engine.evaluate(NBERequest(
            hypotheses=[Hypothesis(id="h1", description="Desc", prior_probability=1.0)],
            available_evidence=[],
            observations=[
                EvidenceObservation(evidence_id="e1", is_true=True),
                EvidenceObservation(evidence_id="e1", is_true=False)
            ],
            likelihoods=[]
        ))

    # Test duplicate likelihoods
    with pytest.raises(ValueError, match="Duplicate likelihood mapping"):
        engine.evaluate(NBERequest(
            hypotheses=[Hypothesis(id="h1", description="Desc", prior_probability=1.0)],
            available_evidence=[],
            likelihoods=[
                EvidenceLikelihood(evidence_id="e1", hypothesis_id="h1", probability_true=0.8),
                EvidenceLikelihood(evidence_id="e1", hypothesis_id="h1", probability_true=0.5)
            ]
        ))

def test_eig_infinite_utility(engine):
    req = NBERequest(
        hypotheses=[
            Hypothesis(id="h1", description="Problem A", prior_probability=0.5),
            Hypothesis(id="h2", description="Problem B", prior_probability=0.5)
        ],
        available_evidence=[
            Evidence(id="e1", description="Perfect, free evidence", cost=0.0),
            Evidence(id="e2", description="Perfect, free evidence 2", cost=0.0)
        ],
        observations=[],
        likelihoods=[
            EvidenceLikelihood(evidence_id="e1", hypothesis_id="h1", probability_true=1.0),
            EvidenceLikelihood(evidence_id="e1", hypothesis_id="h2", probability_true=0.0),
            EvidenceLikelihood(evidence_id="e2", hypothesis_id="h1", probability_true=1.0),
            EvidenceLikelihood(evidence_id="e2", hypothesis_id="h2", probability_true=0.0)
        ],
        sufficiency_threshold=0.9
    )

    # Both e1 and e2 have EIG=1.0, cost=0.0 -> utility = infinity.
    # Deterministic tie-breaking should pick e1.
    resp = engine.evaluate(req)
    assert resp.selected_evidence is not None
    assert resp.selected_evidence.utility_score == float('inf')
    assert resp.selected_evidence.evidence_id == "e1"
