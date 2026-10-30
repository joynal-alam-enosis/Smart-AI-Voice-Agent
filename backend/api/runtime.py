"""Runtime services backing the administrative API.

Only non-secret provider choices are persisted. Cloud credentials stay in the
environment and are represented to the UI only as configured/not-configured.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from threading import RLock
from typing import Any

from backend.api.schemas import (
    LatencyBreakdown,
    LLMProvider,
    ProviderOption,
    ProviderSettingsResponse,
    ProviderSettingsUpdate,
    RuntimeProviderConfig,
)
from backend.config.settings import AppSettings, get_settings
from backend.engine.providers.base import ProviderConfigurationError

logger = logging.getLogger(__name__)

PROVIDER_METADATA: dict[LLMProvider, tuple[str, str, str | None]] = {
    "ollama": ("Local Ollama", "llama3.2:3b", None),
    "gemini": ("Google Gemini", "gemini-2.0-flash", "gemini_api_key"),
    "groq": ("Groq", "llama-3.3-70b-versatile", "groq_api_key"),
    "openai": ("OpenAI", "gpt-4o-mini", "openai_api_key"),
}


def utc_now() -> datetime:
    """Return an aware UTC timestamp for persisted admin metadata."""
    return datetime.now(timezone.utc)


class ProviderRuntimeStore:
    """Thread-safe persistence for the active, non-secret LLM selection."""

    def __init__(self, settings: AppSettings, state_path: Path | None = None) -> None:
        self._settings = settings
        self._state_path = state_path or Path("data/admin_provider_runtime.json")
        self._lock = RLock()
        self._active, self._updated_at = self._load_or_default()

    def _default(self) -> RuntimeProviderConfig:
        return RuntimeProviderConfig(
            provider=self._settings.llm_provider,
            model=self._settings.ollama_model
            if self._settings.llm_provider == "ollama"
            else PROVIDER_METADATA[self._settings.llm_provider][1],
            base_url=self._settings.ollama_base_url if self._settings.llm_provider == "ollama" else None,
        )

    def _load_or_default(self) -> tuple[RuntimeProviderConfig, datetime]:
        if not self._state_path.exists():
            return self._default(), utc_now()
        try:
            payload = json.loads(self._state_path.read_text(encoding="utf-8"))
            return (
                RuntimeProviderConfig.model_validate(payload["active"]),
                datetime.fromisoformat(payload["updated_at"]),
            )
        except (KeyError, OSError, ValueError, json.JSONDecodeError) as exc:
            logger.warning("Ignoring invalid admin provider runtime state: %s", exc)
            return self._default(), utc_now()

    def _write(self) -> None:
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self._state_path.with_suffix(".tmp")
        temporary_path.write_text(
            json.dumps(
                {
                    "active": self._active.model_dump(mode="json"),
                    "updated_at": self._updated_at.isoformat(),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        temporary_path.replace(self._state_path)

    def is_configured(self, provider: LLMProvider) -> bool:
        """Return whether the provider can be initialized without exposing a key."""
        required_field = PROVIDER_METADATA[provider][2]
        return required_field is None or bool(getattr(self._settings, required_field, None))

    def get_active(self) -> RuntimeProviderConfig:
        """Return the current selection as an immutable schema."""
        with self._lock:
            return self._active.model_copy(deep=True)

    def response(self) -> ProviderSettingsResponse:
        """Build a safe configuration payload for the browser."""
        with self._lock:
            providers = [
                ProviderOption(
                    provider=provider,
                    display_name=metadata[0],
                    configured=self.is_configured(provider),
                    local=provider == "ollama",
                    default_model=metadata[1],
                )
                for provider, metadata in PROVIDER_METADATA.items()
            ]
            return ProviderSettingsResponse(
                active=self._active,
                providers=providers,
                updated_at=self._updated_at,
            )

    def update(self, update: ProviderSettingsUpdate) -> ProviderSettingsResponse:
        """Persist a valid provider selection after verifying cloud key availability."""
        with self._lock:
            if not self.is_configured(update.provider):
                raise ProviderConfigurationError(
                    f"{PROVIDER_METADATA[update.provider][0]} is unavailable because its API key is not configured."
                )

            self._active = RuntimeProviderConfig(
                provider=update.provider,
                model=update.model,
                base_url=update.base_url if update.provider == "ollama" else None,
            )
            self._updated_at = utc_now()
            self._write()
            return self.response()


class AdminTelemetry:
    """In-memory bounded telemetry consumed by the admin dashboard."""

    def __init__(self, max_turns: int = 100) -> None:
        self._max_turns = max_turns
        self._turns: list[LatencyBreakdown] = []
        self._tool_call_timestamps: list[datetime] = []
        self._lock = RLock()

    def record_turn(
        self,
        vad_ms: float,
        stt_ms: float,
        rag_ms: float,
        llm_ms: float,
        tts_ms: float,
    ) -> None:
        """Record one finished voice turn for the latency waterfall."""
        with self._lock:
            self._turns.append(
                LatencyBreakdown(
                    vad_ms=round(vad_ms, 2),
                    stt_ms=round(stt_ms, 2),
                    rag_ms=round(rag_ms, 2),
                    llm_ms=round(llm_ms, 2),
                    tts_ms=round(tts_ms, 2),
                    total_ms=round(vad_ms + stt_ms + rag_ms + llm_ms + tts_ms, 2),
                    recorded_at=utc_now(),
                )
            )
            del self._turns[:-self._max_turns]

    def latest_turn(self) -> LatencyBreakdown | None:
        """Return the latest complete turn, if the voice pipeline has reported one."""
        with self._lock:
            return self._turns[-1] if self._turns else None

    def record_tool_call(self) -> None:
        """Track MCP tool activity for a lightweight dashboard signal."""
        with self._lock:
            self._tool_call_timestamps.append(utc_now())

    def tool_calls_last_hour(self) -> int:
        """Return the number of tool calls inside the previous 60 minutes."""
        cutoff = utc_now().timestamp() - 3600
        with self._lock:
            self._tool_call_timestamps = [
                timestamp for timestamp in self._tool_call_timestamps if timestamp.timestamp() >= cutoff
            ]
            return len(self._tool_call_timestamps)


@lru_cache(maxsize=1)
def get_provider_runtime_store() -> ProviderRuntimeStore:
    """Return the process-wide active provider settings store."""
    return ProviderRuntimeStore(get_settings())


@lru_cache(maxsize=1)
def get_admin_telemetry() -> AdminTelemetry:
    """Return the process-wide admin telemetry buffer."""
    return AdminTelemetry()

