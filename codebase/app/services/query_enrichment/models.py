"""Data models for Stage 1 Query Enrichment.

Represents normalized technical query, extracted entities, polarity, and domain intent.
Does NOT generate troubleshooting steps or actions.
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class EnrichedQuery(BaseModel):
    """Structured representation of the user complaint after Stage 1 Enrichment."""

    raw_query: str = Field(..., description="Original user complaint text")
    normalized_query: str = Field(..., description="Cleaned, lowercased, compound-normalized text")
    technical_query: str = Field(..., description="Technical terminology representation of the issue")
    domain: str = Field("General Device Support", description="Galaxy device domain (Display, Battery, Connectivity, etc.)")
    symptoms: List[str] = Field(default_factory=list, description="Extracted problem symptoms")
    entities: List[str] = Field(default_factory=list, description="Detected apps, features, hardware components")
    polarity: str = Field("negative", description="Problem polarity: negative, positive, enable, disable, reset, backup, restore")
    requested_action: Optional[str] = Field(None, description="Action requested by user if explicit (e.g. enable, disable, configure, reset)")
    constraints: List[str] = Field(default_factory=list, description="Specific conditions or constraints mentioned by user")
    intent_category: str = Field("troubleshooting", description="Goal type: troubleshooting, configuration, inquiry")
    candidate_settings_screens: List[str] = Field(default_factory=list, description="Candidate Samsung Settings screens related to domain/feature")
    siis_fingerprint: Optional[str] = Field(None, description="Fingerprint of the accompanying SIIS context if available")
    stage1_confidence: float = Field(1.0, ge=0.0, le=1.0, description="Confidence of the query enrichment extraction")
    provider_used: str = Field("deterministic", description="Provider used for Stage 1 enrichment (gemini, deterministic, or deterministic_fallback)")
