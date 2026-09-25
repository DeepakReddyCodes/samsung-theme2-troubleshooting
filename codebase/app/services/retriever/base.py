"""Base interface and dataclasses for deeplink catalog retrieval."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional

from app.core.schema import Deeplink, ValidationDeepLink


@dataclass
class TroubleshootingIntent:
    """Represents a troubleshooting intent extracted from user query and SIIS steps."""
    action_name: str
    steps: List[str] = field(default_factory=list)
    screen_hint: Optional[str] = ""
    category: Optional[str] = "auto"

    def full_text(self) -> str:
        """Combine all intent text for retrieval."""
        parts = [self.action_name]
        if self.screen_hint:
            parts.append(self.screen_hint)
        parts.extend(self.steps)
        return " ".join(parts)


@dataclass
class DeeplinkResolutionResult:
    """Detailed resolution result containing matched deeplinks and audit evidence."""
    actionable_deeplink: Deeplink
    validation_deeplink: Optional[ValidationDeepLink]
    matched_entry_id: str
    matched_fields: List[str]
    confidence_score: float
    is_fallback: bool
    debug_explanation: str


class IDeeplinkMatcher(ABC):
    """Abstract interface for deeplink catalog matchers."""

    @abstractmethod
    def match(self, intent: TroubleshootingIntent) -> DeeplinkResolutionResult:
        """Resolve an intent to an actionable deeplink with validation."""
        pass
