"""Persona-scoped MCP tool allow-lists (max four tools per persona)."""

from __future__ import annotations

from typing import Any

MAX_TOOLS_PER_PERSONA = 4

PERSONA_TOOLS: dict[str, list[str]] = {
    "hotel_booking_specialist": [
        "hotel_check_availability",
        "hotel_book_room",
        "hotel_cancel_booking",
        "hotel_get_amenities",
    ],
    "receptionist": [
        "hotel_check_availability",
        "hotel_get_amenities",
        "weather_get_forecast",
        "hotel_ops_create_ticket",
    ],
    "restaurant_dining": [
        "dining_list_menu",
        "dining_place_order",
        "dining_check_order",
        "dining_cancel_order",
    ],
    "travel_desk": [
        "weather_get_forecast",
        "calendar_list_events",
        "calendar_create_event",
        "messaging_send",
    ],
    "customer_care": [
        "hotel_ops_create_ticket",
        "hotel_ops_list_tickets",
        "messaging_send",
        "hotel_get_amenities",
    ],
    "hotel_ops": [
        "hotel_ops_create_ticket",
        "hotel_ops_list_tickets",
        "hotel_get_amenities",
        "messaging_send",
    ],
}


class UnknownPersonaError(ValueError):
    """Raised when a session persona is not registered."""


def tools_for_persona(persona: str) -> list[str]:
    """Return at most four tool names allowed for the active persona."""
    if persona not in PERSONA_TOOLS:
        raise UnknownPersonaError(f"Unknown persona '{persona}'.")
    allowed = PERSONA_TOOLS[persona]
    return allowed[:MAX_TOOLS_PER_PERSONA]


def assert_tool_allowed(persona: str, tool_name: str) -> None:
    """Raise if the active persona is not allowed to invoke ``tool_name``."""
    allowed = tools_for_persona(persona)
    if tool_name not in allowed:
        raise PermissionError(
            f"Tool '{tool_name}' is not available to persona '{persona}'."
        )


def tool_catalog_entry(name: str, description: str, schema: dict[str, Any]) -> dict[str, Any]:
    """Build an MCP-compatible tool descriptor for LLM function calling."""
    return {
        "name": name,
        "description": description,
        "inputSchema": schema,
    }
