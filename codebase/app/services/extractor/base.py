"""Base contracts and intermediate models for the knowledge extraction pipeline.

Guarantees:
- Decouples raw LLM outputs from final API schema.
- The LLM only produces intermediate structured intent.
- Every extracted action carries evidence traceable to SIIS text.
- Never directly generates URIs or final ContextDeeplinkResponse.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ExtractedAction:
    """Intermediate action parsed directly from SIIS knowledge."""
    action_name: str
    description: str
    category: str  # "auto", "manual", or "critical"
    steps: List[str]
    screen_hint: Optional[str] = ""
    evidence: Optional[str] = ""


@dataclass
class IntermediateIntent:
    """Intermediate structured troubleshooting intent before deeplink resolution and firewall."""
    topic: str
    goal_mode: str  # "Troubleshooting" or "Configuration"
    title: str  # 2-3 words
    actions: List[ExtractedAction] = field(default_factory=list)
    raw_siis_title: str = ""


class ILLMProvider(ABC):
    """Abstract interface for intermediate intent extraction providers."""

    @abstractmethod
    def extract(self, query: str, siis_title: str, siis_content: str) -> IntermediateIntent:
        """Extract structured intermediate intent from user query and SIIS knowledge."""
        pass
