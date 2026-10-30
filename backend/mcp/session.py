"""In-call agent session state for MCP tools."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class AgentSession:
    """Mutable per-call state: persona, pending confirmation, and audit log."""

    tenant_id: str = "grand-meridian"
    persona: str = "hotel_booking_specialist"
    session_id: str = field(default_factory=lambda: uuid4().hex[:12])
    last_user_message: str = ""
    pending: dict[str, Any] | None = None
    audit: list[dict[str, Any]] = field(default_factory=list)

    def set_last_user_message(self, text: str) -> None:
        """Record the latest caller utterance used by the confirmation gate."""
        self.last_user_message = (text or "").strip()

    def stage_pending(self, kind: str, payload: dict[str, Any]) -> None:
        """Store a write that must be confirmed out loud before commit."""
        self.pending = {"kind": kind, "payload": payload}

    def clear_pending(self) -> None:
        """Drop the staged write after commit or caller abandonment."""
        self.pending = None

    def record_audit(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        result: dict[str, Any],
        latency_ms: float,
    ) -> None:
        """Append a compact tool-call audit record."""
        self.audit.append(
            {
                "tool_name": tool_name,
                "arguments": arguments,
                "result_status": result.get("status"),
                "latency_ms": round(latency_ms, 2),
                "at": _utc_now(),
            }
        )
        try:
            from backend.api.runtime import get_admin_telemetry

            get_admin_telemetry().record_tool_call()
        except Exception:
            # Admin telemetry must never affect confirmation or tool execution.
            pass
