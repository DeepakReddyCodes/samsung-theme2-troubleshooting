"""API Request and Response Models for Samsung Smart Guided Troubleshooting Engine.

Enforces strict Pydantic validation on incoming requests while ensuring the response
faithfully conforms to the authoritative ContextDeeplinkResponse schema.
"""
from typing import Any
from pydantic import BaseModel, ConfigDict, Field, field_validator


class SIISResponseInput(BaseModel):
    """SIIS article payload required in POST /v1/troubleshoot."""
    model_config = ConfigDict(extra="ignore")

    title: str = Field(..., description="Title of the SIIS document", min_length=1)
    content: str = Field(..., description="Full text content of the SIIS document", min_length=1)

    @field_validator("title", "content", mode="before")
    @classmethod
    def check_non_empty(cls, v: Any) -> str:
        if not isinstance(v, str):
            raise ValueError("Field must be a valid string")
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Field cannot be empty or whitespace only")
        return cleaned


class TroubleshootRequest(BaseModel):
    """Official request body schema for POST /v1/troubleshoot."""
    model_config = ConfigDict(extra="ignore")

    query: str = Field(..., description="User's natural language complaint", min_length=1)
    siis_response: SIISResponseInput = Field(..., description="SIIS knowledge payload object")

    @field_validator("query", mode="before")
    @classmethod
    def check_query_non_empty(cls, v: Any) -> str:
        if not isinstance(v, str):
            raise ValueError("Query must be a valid string")
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Query cannot be empty or whitespace only")
        return cleaned


class HealthResponse(BaseModel):
    """Health check response schema."""
    model_config = ConfigDict(extra="ignore")

    status: str = Field("ok", description="Health status (must be 'ok')")
    ready: bool = Field(True, description="Whether server is ready to handle traffic")
    version: str = Field("1.0.0", description="Application version")
    catalog_size: int = Field(..., description="Number of loaded catalog deeplinks")
    cache_entries: int = Field(..., description="Number of prewarmed/active cache entries")
    startup_time_s: float = Field(..., description="Time taken to initialize server in seconds")
