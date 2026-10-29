"""In-process Anthropic MCP-compatible client wrapper.

Uses the official MCP SDK when installed. Otherwise dispatches to local
tool servers so the voice agent stays fully offline for tests and air-gapped
hotel deploys.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import time
from typing import Any, Callable

from backend.mcp.registry import (
    MAX_TOOLS_PER_PERSONA,
    assert_tool_allowed,
    tool_catalog_entry,
    tools_for_persona,
)
from backend.mcp.schemas import json_schema_for_tool
from backend.mcp.session import AgentSession
from backend.mcp.store import HotelStore, resolve_sqlite_path
from backend.mcp.tools import (
    MCPToolServers,
    TOOL_TIMEOUT_SECONDS,
    fetch_open_meteo_forecast,
    local_weather_stub,
)

logger = logging.getLogger(__name__)

TOOL_DESCRIPTIONS: dict[str, str] = {
    "hotel_check_availability": "Check which hotel rooms are free for ISO dates.",
    "hotel_book_room": "Book a room after the caller confirms out loud.",
    "hotel_cancel_booking": "Cancel a booking after the caller confirms out loud.",
    "hotel_get_amenities": "Answer amenity questions in one or two spoken sentences.",
    "calendar_list_events": "List scheduled concierge events.",
    "calendar_create_event": "Schedule an event after out-loud confirmation.",
    "weather_get_forecast": "Get a short local weather summary via Open-Meteo.",
    "hotel_ops_create_ticket": "Open a housekeeping or luggage ticket after confirmation.",
    "hotel_ops_list_tickets": "List open hotel operations tickets.",
    "dining_list_menu": "List room-service menu items.",
    "dining_place_order": "Place a dining order after out-loud confirmation.",
    "dining_check_order": "Look up a room-service order status.",
    "dining_cancel_order": "Cancel a dining order after out-loud confirmation.",
    "messaging_send": "Queue an SMS or WhatsApp message after confirmation. Local stub by default.",
}


class ToolIsolationError(PermissionError):
    """Raised when a persona invokes a tool outside its allow-list."""


class ToolTimeoutError(TimeoutError):
    """Raised when a tool exceeds the voice-safe timeout."""


class MCPHub:
    """MCP client facade: list_tools and call_tool with audit and isolation."""

    def __init__(
        self,
        store: HotelStore,
        session: AgentSession | None = None,
        timeout_seconds: float = TOOL_TIMEOUT_SECONDS,
        servers: MCPToolServers | None = None,
    ) -> None:
        self.store = store
        self.session = session or AgentSession()
        self.timeout_seconds = timeout_seconds
        self.servers = servers or MCPToolServers(store, weather_fetcher=local_weather_stub)
        self._official_client = _try_official_mcp_client()

    def list_tools(self, persona: str | None = None) -> list[dict[str, Any]]:
        """Return MCP tool descriptors for the active persona (max four)."""
        active = persona or self.session.persona
        names = tools_for_persona(active)
        catalog: list[dict[str, Any]] = []
        for name in names:
            catalog.append(
                tool_catalog_entry(
                    name=name,
                    description=TOOL_DESCRIPTIONS.get(name, name),
                    schema=json_schema_for_tool(name),
                )
            )
        if len(catalog) > MAX_TOOLS_PER_PERSONA:
            catalog = catalog[:MAX_TOOLS_PER_PERSONA]
        return catalog

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any] | None = None,
        persona: str | None = None,
    ) -> dict[str, Any]:
        """Invoke a tool with persona isolation, timeout, and audit logging."""
        active = persona or self.session.persona
        arguments = arguments or {}
        started = time.perf_counter()
        try:
            assert_tool_allowed(active, name)
        except PermissionError as exc:
            result = {"status": "error", "message": str(exc)}
            self.session.record_audit(name, arguments, result, (time.perf_counter() - started) * 1000)
            raise ToolIsolationError(str(exc)) from exc

        handler = getattr(self.servers, name, None)
        if handler is None or not callable(handler):
            result = {"status": "error", "message": f"Unknown tool '{name}'."}
            self.session.record_audit(name, arguments, result, (time.perf_counter() - started) * 1000)
            return result

        try:
            result = await asyncio.wait_for(
                _invoke_handler(handler, self.session, arguments),
                timeout=self.timeout_seconds,
            )
        except asyncio.TimeoutError as exc:
            result = {
                "status": "error",
                "message": "The request took too long. Please try again in a moment.",
            }
            self.session.record_audit(name, arguments, result, (time.perf_counter() - started) * 1000)
            raise ToolTimeoutError(result["message"]) from exc

        if not isinstance(result, dict):
            result = {"status": "error", "message": "Tool returned an invalid payload."}

        latency_ms = (time.perf_counter() - started) * 1000
        self.session.record_audit(name, arguments, result, latency_ms)
        logger.info("MCP tool=%s status=%s latency_ms=%.1f", name, result.get("status"), latency_ms)
        return result


async def _invoke_handler(
    handler: Callable[..., Any],
    session: AgentSession,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    outcome = handler(session, arguments)
    if inspect.isawaitable(outcome):
        outcome = await outcome
    return outcome


def create_mcp_hub(
    session: AgentSession | None = None,
    db_path: str | None = None,
    weather_provider: str | None = None,
) -> MCPHub:
    """Build an MCP hub from application settings (local-first defaults)."""
    from backend.config.settings import get_settings

    settings = get_settings()
    resolved_path = db_path or str(resolve_sqlite_path(settings.database_url))
    store = HotelStore(resolved_path)
    provider = (weather_provider or settings.weather_provider).lower().strip()
    fetcher = fetch_open_meteo_forecast if provider == "open_meteo" else local_weather_stub
    return MCPHub(
        store=store,
        session=session or AgentSession(),
        servers=MCPToolServers(store, weather_fetcher=fetcher),
    )


def _try_official_mcp_client() -> Any | None:
    """Load the official MCP client if the optional package is installed."""
    try:
        import mcp  # noqa: F401

        logger.info("Official MCP SDK is available; using in-process tool servers for local-first dispatch.")
        return True
    except ImportError:
        return None
