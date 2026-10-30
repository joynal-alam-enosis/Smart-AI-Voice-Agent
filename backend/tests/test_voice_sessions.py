"""Regression tests for bounded consumer WebRTC and DataChannel contracts."""

from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient
from pydantic import TypeAdapter, ValidationError

from backend.api.app import create_app
from backend.api.schemas import ClientUiEvent, ConsumerSessionRequest
from backend.api.voice_sessions import ConsumerVoiceSession, ConsumerVoiceSessionManager
from backend.config.settings import AppSettings


class FakeConnection:
    """Minimal connection double that captures outbound browser messages."""

    def __init__(self, pc_id: str = "consumer-test") -> None:
        self.pc_id = pc_id
        self.sent_messages: list[dict[str, object]] = []

    def send_app_message(self, message: dict[str, object]) -> None:
        self.sent_messages.append(message)


def test_consumer_config_is_safe_and_browser_cors_is_explicit() -> None:
    """The consumer bootstrap exposes only non-secret metadata to an approved origin."""
    with TestClient(create_app()) as client:
        response = client.get(
            "/api/v1/voice/config?tenant_id=grand-meridian",
            headers={"Origin": "http://localhost:3000"},
        )

    assert response.status_code == 200
    assert response.json()["agent_name"] == "Elena"
    assert response.json()["payment_collection_available"] is False
    assert "api_key" not in response.text
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_data_channel_events_cannot_bypass_spoken_confirmation() -> None:
    """Only presentation/context events are accepted from the consumer browser."""
    adapter = TypeAdapter(ClientUiEvent)
    with pytest.raises(ValidationError):
        adapter.validate_python({"type": "confirm_booking", "booking_id": "BK-101"})


def test_touch_selection_and_confirmation_request_remain_non_committing() -> None:
    """Screen interaction is acknowledged but never routed to an MCP booking write."""
    manager = ConsumerVoiceSessionManager(AppSettings())
    connection = FakeConnection()
    session = ConsumerVoiceSession(
        connection=connection,  # type: ignore[arg-type] - focused transport double.
        request_context=ConsumerSessionRequest(),
    )
    manager._sessions[connection.pc_id] = session

    async def exercise_events() -> None:
        await manager._handle_app_message(
            connection,  # type: ignore[arg-type] - focused transport double.
            {"type": "client_touch_override", "room_id": "R-301", "label": "Executive Suite"},
        )
        await manager._handle_app_message(
            connection,  # type: ignore[arg-type] - focused transport double.
            {"type": "request_out_loud_confirmation", "subject": "Executive Suite reservation"},
        )

    asyncio.run(exercise_events())

    assert session.selected_room_id == "R-301"
    assert connection.sent_messages[0]["type"] == "selection_acknowledged"
    assert connection.sent_messages[1]["type"] == "confirmation_required"
    assert "aloud" in str(connection.sent_messages[1]["message"]).lower()
