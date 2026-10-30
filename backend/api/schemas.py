"""Pydantic contracts shared by the admin API and its React client."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

LLMProvider = Literal["ollama", "gemini", "groq", "openai"]
TTSProvider = Literal["kokoro", "piper", "cartesia", "elevenlabs"]


class StrictSchema(BaseModel):
    """Base API schema that rejects accidental or unsafe fields."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ProviderOption(StrictSchema):
    """Safe provider readiness metadata without exposing credentials."""

    provider: LLMProvider
    display_name: str
    configured: bool
    local: bool
    default_model: str


class RuntimeProviderConfig(StrictSchema):
    """The active LLM selection persisted by the admin console."""

    provider: LLMProvider
    model: str = Field(min_length=1, max_length=120)
    base_url: str | None = Field(default=None, max_length=500)

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: str | None) -> str | None:
        """Allow only HTTP service URLs; credentials belong in environment variables."""
        if value is None:
            return None
        if not value.startswith(("http://", "https://")):
            raise ValueError("Base URL must start with http:// or https://.")
        if "@" in value:
            raise ValueError("Base URL must not contain credentials.")
        return value.rstrip("/")


class ProviderSettingsUpdate(RuntimeProviderConfig):
    """Validated hot-swap request submitted by the Provider Settings view."""


class ProviderSettingsResponse(StrictSchema):
    """Current safe provider configuration and availability."""

    active: RuntimeProviderConfig
    providers: list[ProviderOption]
    updated_at: datetime


class VoiceProfileResponse(StrictSchema):
    """A voice catalog entry suitable for rendering in the Voice Studio."""

    voice_id: str
    name: str
    provider: TTSProvider
    gender: Literal["female", "male", "neutral"]
    accent: str
    recommended_speed: float
    description: str
    role_fit: list[str]


class VoiceAuditionRequest(StrictSchema):
    """A bounded voice preview request."""

    voice_id: str = Field(min_length=1, max_length=100)
    text: str = Field(
        default="Welcome to Grand Meridian. How may I make your stay exceptional today?",
        min_length=1,
        max_length=360,
    )
    speed: float = Field(default=1.0, ge=0.70, le=1.40)
    pitch: float = Field(default=0.0, ge=-20.0, le=20.0)


class LatencyBreakdown(StrictSchema):
    """One completed voice turn measured in milliseconds."""

    vad_ms: float = Field(ge=0)
    stt_ms: float = Field(ge=0)
    rag_ms: float = Field(ge=0)
    llm_ms: float = Field(ge=0)
    tts_ms: float = Field(ge=0)
    total_ms: float = Field(ge=0)
    recorded_at: datetime


class ServiceHealth(StrictSchema):
    """A dashboard-ready, non-secret service readiness record."""

    name: str
    status: Literal["ready", "attention"]
    detail: str


class DashboardResponse(StrictSchema):
    """Current dashboard snapshot; metrics remain empty until voice turns run."""

    active_provider: RuntimeProviderConfig
    latest_latency: LatencyBreakdown | None
    target_latency_ms: int = 800
    services: list[ServiceHealth]
    tool_calls_last_hour: int = Field(ge=0)
    knowledge_documents: int = Field(ge=0)


class KnowledgeChunkResponse(StrictSchema):
    """A concise, admin-only view of one retrieved knowledge chunk."""

    source: str
    excerpt: str
    score: float = Field(ge=0, le=1)


class KnowledgeSearchRequest(StrictSchema):
    """A tenant-scoped query for testing retrieval quality."""

    query: str = Field(min_length=2, max_length=500)
    tenant_id: str = Field(default="grand-meridian", min_length=1, max_length=64)


class KnowledgeSearchResponse(StrictSchema):
    """Search-test result including the spoken fallback when no context matches."""

    has_context: bool
    chunks: list[KnowledgeChunkResponse]
    fallback_spoken: str | None = None


class KnowledgeDocumentResponse(StrictSchema):
    """Knowledge document metadata retained by the local admin service."""

    name: str
    tenant_id: str
    chunks_indexed: int = Field(ge=0)
    uploaded_at: datetime
    status: Literal["indexed"]

