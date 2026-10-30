"""LLM Service Factory: instantiates Ollama, Gemini, Groq, or OpenAI services."""

from __future__ import annotations

import logging
from typing import Any

from backend.config.settings import AppSettings, LLMSettings, get_settings
from backend.engine.providers.base import (
    LLMProviderType,
    MissingDependencyError,
    ProviderConfigurationError,
    UnsupportedProviderError,
)

logger = logging.getLogger(__name__)


def create_llm_service(
    settings: AppSettings | None = None,
    override: LLMSettings | None = None,
) -> Any:
    """Creates and returns the configured LLM service instance."""
    app_cfg = settings or get_settings()
    runtime_override: LLMSettings | None = None
    if settings is None and override is None:
        try:
            from backend.api.runtime import get_provider_runtime_store

            active = get_provider_runtime_store().get_active()
            runtime_override = LLMSettings(
                provider=active.provider,
                model=active.model,
                base_url=active.base_url,
            )
        except Exception as exc:
            logger.debug("Admin runtime provider selection unavailable: %s", exc)

    selected = override or runtime_override
    provider: LLMProviderType = selected.provider if selected else app_cfg.llm_provider

    if provider == "ollama":
        try:
            from pipecat.services.openai.llm import OpenAILLMService
        except ImportError as exc:
            raise MissingDependencyError(
                "pipecat-ai[openai] is required for Ollama LLM service."
            ) from exc

        model = selected.model if selected else app_cfg.ollama_model
        base_url = selected.base_url if selected and selected.base_url else app_cfg.ollama_base_url

        logger.info("Initializing Local Ollama LLM: model=%s, base_url=%s", model, base_url)
        return OpenAILLMService(
            api_key="ollama",
            base_url=base_url,
            model=model,
        )

    elif provider == "groq":
        api_key = (override.api_key if override and override.api_key else app_cfg.groq_api_key)
        if not api_key:
            raise ProviderConfigurationError("GROQ_API_KEY is required for Groq provider.")

        try:
            from pipecat.services.openai.llm import OpenAILLMService
        except ImportError as exc:
            raise MissingDependencyError(
                "pipecat-ai[openai] is required for Groq LLM service."
            ) from exc

        model = selected.model if selected else app_cfg.groq_model
        logger.info("Initializing Groq LLM: model=%s", model)
        return OpenAILLMService(
            api_key=api_key,
            base_url="https://api.groq.com/openai/v1",
            model=model,
        )

    elif provider == "openai":
        api_key = (override.api_key if override and override.api_key else app_cfg.openai_api_key)
        if not api_key:
            raise ProviderConfigurationError("OPENAI_API_KEY is required for OpenAI provider.")

        try:
            from pipecat.services.openai.llm import OpenAILLMService
        except ImportError as exc:
            raise MissingDependencyError(
                "pipecat-ai[openai] is required for OpenAI LLM service."
            ) from exc

        model = selected.model if selected else app_cfg.openai_model
        logger.info("Initializing OpenAI LLM: model=%s", model)
        return OpenAILLMService(
            api_key=api_key,
            model=model,
        )

    elif provider == "gemini":
        api_key = (override.api_key if override and override.api_key else app_cfg.gemini_api_key)
        if not api_key:
            raise ProviderConfigurationError("GEMINI_API_KEY is required for Gemini provider.")

        try:
            from pipecat.services.google.gemini import GeminiLLMService
        except ImportError as exc:
            raise MissingDependencyError(
                "pipecat-ai[google] or google-genai is required for Gemini LLM service."
            ) from exc

        model = selected.model if selected else "gemini-2.0-flash"
        logger.info("Initializing Gemini LLM: model=%s", model)
        return GeminiLLMService(
            api_key=api_key,
            model=model,
        )

    else:
        raise UnsupportedProviderError(f"Unsupported LLM provider: {provider}")
