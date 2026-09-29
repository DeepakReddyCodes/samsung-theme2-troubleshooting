from typing import Dict, List, Optional
from pydantic import BaseModel, Field

class Evidence(BaseModel):
    """Represents a piece of evidence that can be acquired."""
    id: str = Field(..., description="Unique identifier for the evidence")
    description: str = Field(..., description="Human-readable description of the evidence")
    cost: float = Field(1.0, description="Cost of acquiring this evidence (e.g., time, annoyance)")

class Hypothesis(BaseModel):
    """Represents a potential underlying state or problem."""
    id: str = Field(..., description="Unique identifier for the hypothesis")
    description: str = Field(..., description="Human-readable description of the hypothesis")
    prior_probability: float = Field(..., description="Initial probability of this hypothesis")

class EvidenceObservation(BaseModel):
    """Represents an observation of a piece of evidence."""
    evidence_id: str
    is_true: bool

class EvidenceLikelihood(BaseModel):
    """Represents P(Evidence | Hypothesis) for a specific evidence and hypothesis."""
    evidence_id: str
    hypothesis_id: str
    probability_true: float = Field(..., description="P(Evidence=True | Hypothesis)")

class NBERequest(BaseModel):
    """Input to the Next-Best-Evidence engine."""
    hypotheses: List[Hypothesis] = Field(..., description="Current competing hypotheses")
    available_evidence: List[Evidence] = Field(..., description="Evidence candidates that could be acquired")
    observations: List[EvidenceObservation] = Field(default_factory=list, description="Currently observed evidence")
    likelihoods: List[EvidenceLikelihood] = Field(..., description="Conditional probabilities P(E|H)")
    sufficiency_threshold: float = Field(0.9, description="Posterior probability required to consider a hypothesis sufficient")

class SelectedEvidence(BaseModel):
    evidence_id: str
    eig_score: float
    utility_score: float

class NBEResponse(BaseModel):
    """Output from the Next-Best-Evidence engine."""
    is_sufficient: bool = Field(..., description="True if a hypothesis meets the sufficiency threshold")
    top_hypothesis_id: Optional[str] = Field(None, description="The ID of the leading hypothesis")
    top_hypothesis_probability: Optional[float] = Field(None, description="The posterior probability of the leading hypothesis")
    selected_evidence: Optional[SelectedEvidence] = Field(None, description="The best piece of evidence to acquire next")
    posterior_probabilities: Dict[str, float] = Field(..., description="Posterior probabilities for all hypotheses")
