"""Data models for Next-Best-Evidence (NBE) and Expected Information Gain (EIG).

Provides mathematical contracts for hypothesis spaces, candidate evidence,
observational outcomes, and Bayesian inference results.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Hypothesis:
    """A single diagnostic hypothesis explaining a user device problem."""
    id: str
    name: str
    description: str = ""
    prior: float = 1.0
    target_action: Optional[str] = None
    target_settings_screen: Optional[str] = None

    def __post_init__(self):
        if not self.id:
            raise ValueError("Hypothesis id must not be empty.")
        if not self.name:
            raise ValueError("Hypothesis name must not be empty.")
        if self.prior < 0.0:
            raise ValueError(f"Hypothesis prior must be non-negative, got {self.prior}")


@dataclass
class CandidateEvidence:
    """A test, sensor check, or user question that can yield evidence observations."""
    id: str
    question: str
    target_feature: str
    outcomes: List[str] = field(default_factory=lambda: ["yes", "no"])
    # likelihood_matrix[hypothesis_id][outcome] = P(Outcome=outcome | Hypothesis=hypothesis_id)
    likelihood_matrix: Dict[str, Dict[str, float]] = field(default_factory=dict)
    cost: float = 1.0
    availability: float = 1.0

    def __post_init__(self):
        if not self.id:
            raise ValueError("CandidateEvidence id must not be empty.")
        if not self.question:
            raise ValueError("CandidateEvidence question must not be empty.")
        if not self.outcomes:
            raise ValueError("CandidateEvidence must have at least one possible outcome.")
        if self.cost <= 0.0:
            raise ValueError(f"Evidence cost must be positive, got {self.cost}")
        if not (0.0 <= self.availability <= 1.0):
            raise ValueError(f"Availability must be in [0.0, 1.0], got {self.availability}")


@dataclass
class NBEResult:
    """The outcome of NBE sufficiency assessment and information-theoretic ranking."""
    is_sufficient: bool
    top_hypothesis: Optional[Hypothesis]
    top_hypothesis_confidence: float
    current_entropy: float
    selected_evidence: Optional[CandidateEvidence] = None
    selected_eig: float = 0.0
    selected_utility: float = 0.0
    all_evidence_rankings: List[Dict[str, Any]] = field(default_factory=list)
    posterior_distribution: Dict[str, float] = field(default_factory=dict)
    explanation: str = ""
