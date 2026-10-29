"""Base types, protocols, and exceptions for AI provider factories."""

from __future__ import annotations

from typing import Literal

LLMProviderType = Literal["ollama", "gemini", "groq", "openai"]
STTProviderType = Literal["faster_whisper", "deepgram", "groq"]
TTSProviderType = Literal["kokoro", "piper", "cartesia", "elevenlabs"]


class ProviderError(Exception):
    """Base exception for all AI provider errors."""


class UnsupportedProviderError(ProviderError):
    """Raised when an unrecognized or unsupported provider is requested."""


class ProviderConfigurationError(ProviderError):
    """Raised when required API keys or endpoints are missing."""


class MissingDependencyError(ProviderError):
    """Raised when an optional provider library is not installed in the environment."""
