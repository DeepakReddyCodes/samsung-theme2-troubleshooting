"""Next-Best-Evidence (NBE) Decision Loop & State Machine.

Coordinates multi-turn diagnostic evidence acquisition:
EVIDENCE SUFFICIENCY
       ↓
 sufficient?
   /          \
 YES           NO
 |             |
resolve       NBE/EIG
               ↓
        select next evidence
               ↓
        acquire evidence
               ↓
          reassess
               ↓
            resolve

Preserves the frozen REST API schema while providing clean internal
orchestration and a dedicated multi-turn decision state machine.
"""
import logging
from typing import Any, Callable, Dict, List, Optional, Tuple

from app.services.nbe.engine import NBEEngine
from app.services.nbe.models import CandidateEvidence, Hypothesis, NBEResult

logger = logging.getLogger(__name__)


class NBEDecisionLoop:
    """State machine managing Bayesian evidence acquisition and sufficiency reassessment."""

    def __init__(
        self,
        hypotheses: List[Hypothesis],
        candidate_evidence: Optional[List[CandidateEvidence]] = None,
        engine: Optional[NBEEngine] = None,
        initial_observations: Optional[Dict[str, str]] = None,
    ):
        if not hypotheses:
            raise ValueError("NBEDecisionLoop requires at least one hypothesis.")

        self.hypotheses = hypotheses
        self.candidate_evidence = candidate_evidence or []
        self.engine = engine or NBEEngine()
        self.observed_evidence: Dict[str, str] = dict(initial_observations or {})
        self.history: List[NBEResult] = []
        self.current_state: Optional[NBEResult] = None

    def assess_sufficiency(self) -> NBEResult:
        """Step 1: Determine if current evidence is sufficient to resolve the diagnosis."""
        result = self.engine.evaluate(
            hypotheses=self.hypotheses,
            candidate_evidence=self.candidate_evidence,
            observed_evidence=self.observed_evidence,
        )
        self.current_state = result
        self.history.append(result)
        return result

    def acquire_evidence(self, evidence_id: str, outcome: str) -> NBEResult:
        """Step 2: Record an acquired evidence observation and reassess sufficiency."""
        if not any(ev.id == evidence_id for ev in self.candidate_evidence):
            logger.warning(f"Acquired evidence '{evidence_id}' not in candidate pool.")

        self.observed_evidence[evidence_id] = outcome
        return self.assess_sufficiency()

    def run_until_sufficient(
        self,
        evidence_acquirer: Callable[[CandidateEvidence], str],
        max_turns: int = 5,
    ) -> Tuple[bool, List[NBEResult], Optional[Hypothesis]]:
        """Execute the multi-turn loop until sufficiency or max turns reached.
        
        Args:
            evidence_acquirer: Callable that simulates or prompts for evidence outcome given CandidateEvidence.
            max_turns: Safety guard to prevent infinite looping.
            
        Returns:
            Tuple of (is_resolved, history_of_evaluations, final_leading_hypothesis)
        """
        turns = 0
        while turns < max_turns:
            turns += 1
            result = self.assess_sufficiency()
            if result.is_sufficient:
                logger.info(f"NBE loop resolved at turn {turns}: '{result.top_hypothesis.name}' ({result.top_hypothesis_confidence:.1%})")
                return True, self.history, result.top_hypothesis

            selected_ev = result.selected_evidence
            if not selected_ev:
                # No further informative evidence can be acquired
                logger.info(f"NBE loop terminated at turn {turns}: no further informative evidence.")
                return True, self.history, result.top_hypothesis

            # Acquire next evidence
            outcome = evidence_acquirer(selected_ev)
            self.observed_evidence[selected_ev.id] = outcome

        # Terminated via max turns guard
        final_state = self.assess_sufficiency()
        return final_state.is_sufficient, self.history, final_state.top_hypothesis

    @classmethod
    def create_common_scenario(cls, scenario_key: str) -> "NBEDecisionLoop":
        """Factory for standard Samsung diagnostic disambiguation scenarios."""
        if scenario_key == "screen_blank_vs_battery":
            hypotheses = [
                Hypothesis(id="H_CRASH", name="System Frozen Blank", prior=0.5, target_action="Force Restart"),
                Hypothesis(id="H_BATTERY", name="Battery Completely Drained", prior=0.5, target_action="Charge Device"),
            ]
            candidates = [
                CandidateEvidence(
                    id="EV_CHARGER_VIBRATE",
                    question="Does the device vibrate or display a LED when plugged into a charger?",
                    target_feature="charging_haptic",
                    outcomes=["yes", "no"],
                    likelihood_matrix={
                        "H_CRASH": {"yes": 0.90, "no": 0.10},
                        "H_BATTERY": {"yes": 0.05, "no": 0.95},
                    },
                    cost=1.0,
                ),
                CandidateEvidence(
                    id="EV_RECENT_FALL",
                    question="Was the device recently dropped or exposed to water?",
                    target_feature="physical_impact",
                    outcomes=["yes", "no"],
                    likelihood_matrix={
                        "H_CRASH": {"yes": 0.30, "no": 0.70},
                        "H_BATTERY": {"yes": 0.10, "no": 0.90},
                    },
                    cost=1.5,
                ),
            ]
            return cls(hypotheses=hypotheses, candidate_evidence=candidates)

        elif scenario_key == "wifi_vs_network_reset":
            hypotheses = [
                Hypothesis(id="H_ROUTER", name="Wi-Fi AP Issue", prior=0.5, target_action="Reconnect Wi-Fi"),
                Hypothesis(id="H_NETWORK_STACK", name="Device Network Stack Glitch", prior=0.5, target_action="Reset Network Settings"),
            ]
            candidates = [
                CandidateEvidence(
                    id="EV_OTHER_DEVICES",
                    question="Can other devices connect to this Wi-Fi network without issues?",
                    target_feature="ap_health",
                    outcomes=["yes", "no"],
                    likelihood_matrix={
                        "H_ROUTER": {"yes": 0.05, "no": 0.95},
                        "H_NETWORK_STACK": {"yes": 0.90, "no": 0.10},
                    },
                    cost=1.0,
                ),
            ]
            return cls(hypotheses=hypotheses, candidate_evidence=candidates)

        raise ValueError(f"Unknown scenario key '{scenario_key}'")
