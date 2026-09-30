"""Unit and integration tests for Next-Best-Evidence (NBE) & Expected Information Gain (EIG)."""
import pytest

from app.services.nbe import (
    CandidateEvidence,
    Hypothesis,
    NBEDecisionLoop,
    NBEEngine,
    calculate_shannon_entropy,
    compute_evidence_eig,
    update_bayesian_posterior,
    validate_hypotheses,
)


def test_shannon_entropy_calculation():
    """Verify Shannon entropy in bits for discrete probability distributions."""
    # Certain state -> 0 bits
    assert calculate_shannon_entropy({"A": 1.0, "B": 0.0}) == 0.0
    # Binary uniform -> 1 bit
    assert pytest.approx(calculate_shannon_entropy({"A": 0.5, "B": 0.5}), 0.001) == 1.0
    # 4-state uniform -> 2 bits
    assert pytest.approx(calculate_shannon_entropy({"A": 0.25, "B": 0.25, "C": 0.25, "D": 0.25}), 0.001) == 2.0


def test_eig_calculation_perfect_discriminator():
    """Verify that a perfect diagnostic test has EIG equal to the full prior entropy."""
    h1 = Hypothesis(id="H1", name="Software Crash", prior=0.5)
    h2 = Hypothesis(id="H2", name="Hardware Defect", prior=0.5)
    priors = validate_hypotheses([h1, h2])

    # Perfect discriminator: outcome 'yes' if H1, 'no' if H2
    evidence = CandidateEvidence(
        id="EV_TEST_1",
        question="Does the device show the charging animation?",
        target_feature="charging_indicator",
        outcomes=["yes", "no"],
        likelihood_matrix={
            "H1": {"yes": 1.0, "no": 0.0},
            "H2": {"yes": 0.0, "no": 1.0},
        },
        cost=1.0,
        availability=1.0,
    )

    eig, utility, posteriors = compute_evidence_eig(priors, evidence)
    assert pytest.approx(eig, 0.001) == 1.0
    assert pytest.approx(utility, 0.001) == 1.0
    assert posteriors["yes"] == {"H1": 1.0, "H2": 0.0}
    assert posteriors["no"] == {"H1": 0.0, "H2": 1.0}


def test_eig_calculation_uninformative_test():
    """Verify that an uninformative test has zero EIG."""
    h1 = Hypothesis(id="H1", name="Software Crash", prior=0.5)
    h2 = Hypothesis(id="H2", name="Hardware Defect", prior=0.5)
    priors = validate_hypotheses([h1, h2])

    evidence = CandidateEvidence(
        id="EV_UNINFORMATIVE",
        question="Is the phone case blue?",
        target_feature="case_color",
        outcomes=["yes", "no"],
        likelihood_matrix={
            "H1": {"yes": 0.5, "no": 0.5},
            "H2": {"yes": 0.5, "no": 0.5},
        },
        cost=1.0,
        availability=1.0,
    )

    eig, utility, _ = compute_evidence_eig(priors, evidence)
    assert pytest.approx(eig, 0.001) == 0.0
    assert pytest.approx(utility, 0.001) == 0.0


def test_cost_aware_utility():
    """Verify that higher cost decreases utility proportionally."""
    h1 = Hypothesis(id="H1", name="H1", prior=0.5)
    h2 = Hypothesis(id="H2", name="H2", prior=0.5)
    priors = validate_hypotheses([h1, h2])

    ev_cheap = CandidateEvidence(
        id="EV_CHEAP",
        question="Cheap question",
        target_feature="f1",
        likelihood_matrix={"H1": {"yes": 1.0, "no": 0.0}, "H2": {"yes": 0.0, "no": 1.0}},
        cost=1.0,
    )
    ev_expensive = CandidateEvidence(
        id="EV_EXPENSIVE",
        question="Expensive lab test",
        target_feature="f1",
        likelihood_matrix={"H1": {"yes": 1.0, "no": 0.0}, "H2": {"yes": 0.0, "no": 1.0}},
        cost=4.0,
    )

    eig_c, util_c, _ = compute_evidence_eig(priors, ev_cheap)
    eig_e, util_e, _ = compute_evidence_eig(priors, ev_expensive)

    assert pytest.approx(eig_c, 0.001) == eig_e
    assert pytest.approx(util_c, 0.001) == util_e * 4.0


def test_bayesian_posterior_update():
    """Verify Bayes rule updating: P(H|E=e) = P(E=e|H) * P(H) / P(E=e)."""
    priors = {"H1": 0.6, "H2": 0.4}
    evidence = CandidateEvidence(
        id="EV_1",
        question="Is LED blinking?",
        target_feature="led",
        outcomes=["yes", "no"],
        likelihood_matrix={
            "H1": {"yes": 0.8, "no": 0.2},
            "H2": {"yes": 0.1, "no": 0.9},
        },
    )

    # Observed 'yes' -> P(yes) = 0.8*0.6 + 0.1*0.4 = 0.48 + 0.04 = 0.52
    # P(H1|yes) = 0.48 / 0.52 = 0.9231
    # P(H2|yes) = 0.04 / 0.52 = 0.0769
    post = update_bayesian_posterior(priors, evidence, "yes")
    assert pytest.approx(post["H1"], 0.001) == 0.9231
    assert pytest.approx(post["H2"], 0.001) == 0.0769


def test_duplicate_hypothesis_rejection():
    """Ensure duplicate hypothesis IDs raise ValueError."""
    h1 = Hypothesis(id="H_DUP", name="First")
    h2 = Hypothesis(id="H_DUP", name="Second")
    with pytest.raises(ValueError, match="Duplicate hypothesis id"):
        validate_hypotheses([h1, h2])


def test_duplicate_evidence_id_rejection():
    """Ensure duplicate candidate evidence IDs raise ValueError."""
    engine = NBEEngine()
    h = [Hypothesis(id="H1", name="H1"), Hypothesis(id="H2", name="H2")]
    ev1 = CandidateEvidence(
        id="EV_DUP",
        question="Q1",
        target_feature="f1",
        likelihood_matrix={"H1": {"yes": 1.0, "no": 0.0}, "H2": {"yes": 0.0, "no": 1.0}},
    )
    ev2 = CandidateEvidence(
        id="EV_DUP",
        question="Q2",
        target_feature="f2",
        likelihood_matrix={"H1": {"yes": 1.0, "no": 0.0}, "H2": {"yes": 0.0, "no": 1.0}},
    )
    with pytest.raises(ValueError, match="Duplicate candidate evidence id"):
        engine.evaluate(h, [ev1, ev2])


def test_incomplete_likelihood_matrix_rejection():
    """Ensure evidence missing likelihood for a hypothesis raises ValueError."""
    engine = NBEEngine()
    h = [Hypothesis(id="H1", name="H1"), Hypothesis(id="H2", name="H2")]
    ev = CandidateEvidence(
        id="EV_INCOMPLETE",
        question="Q1",
        target_feature="f1",
        likelihood_matrix={"H1": {"yes": 1.0, "no": 0.0}},  # Missing H2
    )
    with pytest.raises(ValueError, match="missing likelihood distribution"):
        engine.evaluate(h, [ev])


def test_nbe_sufficiency_when_confident():
    """When a single hypothesis is dominant, evaluate returns is_sufficient=True."""
    engine = NBEEngine(confidence_threshold=0.85)
    h1 = Hypothesis(id="H_DOMINANT", name="Clear Cause", prior=0.90)
    h2 = Hypothesis(id="H_MINOR", name="Unlikely Cause", prior=0.10)

    result = engine.evaluate([h1, h2], [])
    assert result.is_sufficient is True
    assert result.top_hypothesis.id == "H_DOMINANT"
    assert result.selected_evidence is None


def test_nbe_selects_highest_utility_question():
    """When uncertainty is high, NBE selects the candidate evidence with highest utility."""
    engine = NBEEngine(entropy_threshold=0.45, confidence_threshold=0.85)
    h1 = Hypothesis(id="H1", name="Display Dead", prior=0.5)
    h2 = Hypothesis(id="H2", name="Battery Drained", prior=0.5)

    ev_poor = CandidateEvidence(
        id="EV_POOR",
        question="Is it warm?",
        target_feature="temp",
        likelihood_matrix={"H1": {"yes": 0.6, "no": 0.4}, "H2": {"yes": 0.4, "no": 0.6}},
        cost=1.0,
    )
    ev_best = CandidateEvidence(
        id="EV_BEST",
        question="Does the phone vibrate when plugging in charger?",
        target_feature="haptic_on_charge",
        likelihood_matrix={"H1": {"yes": 0.95, "no": 0.05}, "H2": {"yes": 0.05, "no": 0.95}},
        cost=1.0,
    )

    result = engine.evaluate([h1, h2], [ev_poor, ev_best])
    assert result.is_sufficient is False
    assert result.selected_evidence.id == "EV_BEST"
    assert result.selected_eig > 0.6


def test_nbe_end_to_end_acquisition_loop():
    """Simulate complete 2-step troubleshooting interaction using NBE engine."""
    engine = NBEEngine(confidence_threshold=0.85)
    hypotheses = [
        Hypothesis(id="H_FROZEN", name="System Frozen", prior=0.5, target_action="Force Restart"),
        Hypothesis(id="H_DEAD_BATTERY", name="Battery Completely Drained", prior=0.5, target_action="Charge Device"),
    ]

    ev_vibrate = CandidateEvidence(
        id="EV_VIBRATE",
        question="Does the device vibrate when connected to charger?",
        target_feature="vibrate_check",
        outcomes=["yes", "no"],
        likelihood_matrix={
            "H_FROZEN": {"yes": 0.90, "no": 0.10},
            "H_DEAD_BATTERY": {"yes": 0.05, "no": 0.95},
        },
    )

    # Step 1: Initial query -> ambiguous
    r1 = engine.evaluate(hypotheses, [ev_vibrate])
    assert r1.is_sufficient is False
    assert r1.selected_evidence.id == "EV_VIBRATE"

    # Step 2: User responds "yes" (phone vibrates when plugged in)
    r2 = engine.evaluate(hypotheses, [ev_vibrate], observed_evidence={"EV_VIBRATE": "yes"})
    assert r2.is_sufficient is True
    assert r2.top_hypothesis.id == "H_FROZEN"
    assert r2.top_hypothesis_confidence >= 0.90
    assert r2.top_hypothesis.target_action == "Force Restart"


def test_nbe_decision_loop_state_machine():
    """Verify NBEDecisionLoop coordinates multi-turn evaluation, evidence acquisition, and resolution."""
    loop = NBEDecisionLoop.create_common_scenario("screen_blank_vs_battery")

    # Step 1: Initial evaluation -> insufficient
    res1 = loop.assess_sufficiency()
    assert res1.is_sufficient is False
    assert res1.selected_evidence is not None
    assert res1.selected_evidence.id == "EV_CHARGER_VIBRATE"

    # Step 2: Acquire evidence: user says phone vibrates when plugged in
    res2 = loop.acquire_evidence("EV_CHARGER_VIBRATE", "yes")
    assert res2.is_sufficient is True
    assert res2.top_hypothesis.id == "H_CRASH"
    assert res2.top_hypothesis_confidence >= 0.85
    assert res2.top_hypothesis.target_action == "Force Restart"


def test_nbe_decision_loop_run_until_sufficient():
    """Verify automated execution of evidence acquisition loop with oracle callback."""
    loop = NBEDecisionLoop.create_common_scenario("screen_blank_vs_battery")

    # Simulated oracle that answers 'no' to vibrate (indicating dead battery)
    def battery_oracle(ev: CandidateEvidence) -> str:
        if ev.id == "EV_CHARGER_VIBRATE":
            return "no"
        return "no"

    is_resolved, history, top_h = loop.run_until_sufficient(battery_oracle, max_turns=3)
    assert is_resolved is True
    assert top_h is not None
    assert top_h.id == "H_BATTERY"
    assert top_h.target_action == "Charge Device"
    assert len(history) == 2


def test_nbe_decision_loop_max_turns_guard():
    """Verify safety guard halts multi-turn loop when tests are exhausted or max turns hit."""
    h1 = Hypothesis(id="H1", name="Hypothesis 1", prior=0.5)
    h2 = Hypothesis(id="H2", name="Hypothesis 2", prior=0.5)
    # Evidence with identical likelihoods (0 information gain)
    uninformative = CandidateEvidence(
        id="EV_FLAT",
        question="Uninformative question?",
        target_feature="flat",
        likelihood_matrix={"H1": {"yes": 0.5, "no": 0.5}, "H2": {"yes": 0.5, "no": 0.5}},
    )

    loop = NBEDecisionLoop(hypotheses=[h1, h2], candidate_evidence=[uninformative])
    is_resolved, history, top_h = loop.run_until_sufficient(lambda ev: "yes", max_turns=2)
    # Loop safely terminates without crashing
    assert len(history) >= 1
    assert top_h is not None


def test_cold_path_engine_nbe_integration():
    """Verify ColdPathExtractionEngine incorporates NBE decision evaluation without breaking schema."""
    from app.services.extractor.engine import ColdPathExtractionEngine

    engine = ColdPathExtractionEngine()
    siis_content = (
        "## Network Settings\n"
        "1. Open Settings and tap Connections.\n"
        "2. Tap Wi-Fi and toggle on.\n"
        "3. Alternatively tap Reset network settings if connection fails."
    )
    plan = engine.extract_and_build(
        query="My device cannot connect to Wi-Fi",
        siis_response={"title": "Wi-Fi Connection", "content": siis_content},
    )
    assert plan is not None
    # Engine tracks NBE sufficiency internally
    assert engine.last_nbe_result is not None
    assert engine.last_nbe_result.is_sufficient is True


