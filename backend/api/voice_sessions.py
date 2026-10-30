"""SmallWebRTC session management for the consumer voice surface.

The session manager owns browser signalling and the typed DataChannel bridge.
It deliberately treats every client card interaction as conversational context:
it never invokes a booking, cancellation, or payment tool directly. Those writes
remain exclusively behind the existing spoken confirmation gate in ``backend.mcp``.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

from fastapi import HTTPException, status
from pydantic import TypeAdapter, ValidationError

from backend.api.schemas import (
    ClientTouchOverrideEvent,
    ClientUiEvent,
    ConsumerConfigurationResponse,
    ConsumerSessionRequest,
    PttStateEvent,
    RequestOutLoudConfirmationEvent,
    RequestSecureCheckoutEvent,
    TextMessageEvent,
    VoiceIcePatchRequest,
    VoiceOfferRequest,
    VoiceOfferResponse,
)
from backend.config.settings import AppSettings, TenantConfig, get_settings, load_tenant_config

try:
    from pipecat.transports.smallwebrtc.connection import SmallWebRTCConnection
    from pipecat.transports.smallwebrtc.request_handler import (
        IceCandidate,
        SmallWebRTCPatchRequest,
        SmallWebRTCRequest,
        SmallWebRTCRequestHandler,
    )
except ImportError as exc:  # pragma: no cover - exercised only in minimal deployments.
    raise RuntimeError(
        "Pipecat SmallWebRTC support is required for browser voice sessions. "
        "Install pipecat-ai[webrtc]."
    ) from exc

logger = logging.getLogger(__name__)
_CLIENT_EVENT_ADAPTER = TypeAdapter(ClientUiEvent)


@dataclass
class ConsumerVoiceSession:
    """In-memory, non-sensitive state associated with one peer connection."""

    connection: SmallWebRTCConnection
    request_context: ConsumerSessionRequest
    selected_room_id: str | None = None
    last_text_message: str | None = None
    ptt_active: bool = False
    event_count: int = 0
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class ConsumerVoiceSessionManager:
    """Negotiate local WebRTC sessions and safely dispatch DataChannel events."""

    def __init__(self, settings: AppSettings) -> None:
        self._settings = settings
        self._handler = SmallWebRTCRequestHandler()
        self._sessions: dict[str, ConsumerVoiceSession] = {}
        self._sessions_lock = asyncio.Lock()

    def configuration(self, tenant_id: str) -> ConsumerConfigurationResponse:
        """Return safe consumer bootstrap configuration for the requested tenant."""
        tenant = self._tenant_for(tenant_id)
        persona = tenant.get_active_persona()
        return ConsumerConfigurationResponse(
            tenant_id=tenant.tenant_id,
            tenant_name=tenant.tenant_name,
            agent_name=persona.name,
            persona=persona.key,
        )

    async def create_offer(self, request: VoiceOfferRequest) -> VoiceOfferResponse:
        """Turn a browser SDP offer into a SmallWebRTC answer."""
        tenant = self._tenant_for(request.request_data.tenant_id)
        persona = request.request_data.persona or tenant.get_active_persona().key
        if persona not in tenant.personas:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="The requested concierge persona is unavailable for this tenant.",
            )

        request_context = ConsumerSessionRequest(tenant_id=tenant.tenant_id, persona=persona)
        pipecat_request = SmallWebRTCRequest(
            sdp=request.sdp,
            type=request.type,
            pc_id=request.pc_id,
            restart_pc=request.restart_pc,
            request_data=request_context.model_dump(),
        )

        async def on_connection(connection: SmallWebRTCConnection) -> None:
            await self._register_connection(connection, request_context, tenant)

        answer = await self._handler.handle_web_request(pipecat_request, on_connection)
        if answer is None:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="The local voice transport did not produce an SDP answer.",
            )
        return VoiceOfferResponse.model_validate(answer)

    async def add_ice_candidates(self, request: VoiceIcePatchRequest) -> None:
        """Forward a small, validated candidate batch to SmallWebRTC."""
        patch_request = SmallWebRTCPatchRequest(
            pc_id=request.pc_id,
            candidates=[
                IceCandidate(
                    candidate=candidate.candidate,
                    sdp_mid=candidate.sdp_mid,
                    sdp_mline_index=candidate.sdp_mline_index,
                )
                for candidate in request.candidates
            ],
        )
        await self._handler.handle_patch_request(patch_request)

    async def close(self) -> None:
        """Disconnect all peer connections during application shutdown."""
        await self._handler.close()
        async with self._sessions_lock:
            self._sessions.clear()

    def _tenant_for(self, tenant_id: str) -> TenantConfig:
        """Resolve the configured local tenant without accepting arbitrary tenancy."""
        tenant = load_tenant_config()
        if tenant.tenant_id != tenant_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="The requested tenant is unavailable.",
            )
        return tenant

    async def _register_connection(
        self,
        connection: SmallWebRTCConnection,
        context: ConsumerSessionRequest,
        tenant: TenantConfig,
    ) -> None:
        """Attach lifecycle handlers and queue safe initial state for a connection."""
        session = ConsumerVoiceSession(connection=connection, request_context=context)
        async with self._sessions_lock:
            self._sessions[connection.pc_id] = session

        @connection.event_handler("app-message")
        async def handle_app_message(
            active_connection: SmallWebRTCConnection,
            message: dict[str, Any],
        ) -> None:
            await self._handle_app_message(active_connection, message)

        @connection.event_handler("closed")
        async def handle_closed(active_connection: SmallWebRTCConnection) -> None:
            async with self._sessions_lock:
                self._sessions.pop(active_connection.pc_id, None)

        await connection.connect()
        connection.send_app_message(
            {
                "type": "session_ready",
                "agent_name": tenant.get_active_persona().name,
                "message": "Your private concierge connection is ready.",
                "confirmation_required": True,
            }
        )

    async def _handle_app_message(
        self,
        connection: SmallWebRTCConnection,
        message: dict[str, Any],
    ) -> None:
        """Validate browser interaction events and return a non-committing acknowledgement."""
        try:
            event = _CLIENT_EVENT_ADAPTER.validate_python(message)
        except ValidationError:
            connection.send_app_message(
                {
                    "type": "ui_error",
                    "message": "That screen action could not be understood. Please try again.",
                }
            )
            logger.warning("Rejected invalid consumer UI event for peer %s", connection.pc_id)
            return

        async with self._sessions_lock:
            session = self._sessions.get(connection.pc_id)
        if session is None:
            return

        async with session.lock:
            session.event_count += 1
            reply = self._apply_event(session, event)
        connection.send_app_message(reply)

    @staticmethod
    def _apply_event(session: ConsumerVoiceSession, event: ClientUiEvent) -> dict[str, Any]:
        """Apply a typed interaction without bypassing voice confirmation safeguards."""
        if isinstance(event, ClientTouchOverrideEvent):
            session.selected_room_id = event.room_id
            return {
                "type": "selection_acknowledged",
                "room_id": event.room_id,
                "message": f"Selection received: {event.label}. Your concierge will confirm the details aloud.",
            }
        if isinstance(event, TextMessageEvent):
            session.last_text_message = event.text
            return {
                "type": "text_acknowledged",
                "message": "Your message is ready for the concierge. Booking changes still need spoken confirmation.",
            }
        if isinstance(event, PttStateEvent):
            session.ptt_active = event.active
            return {"type": "ptt_acknowledged", "active": event.active}
        if isinstance(event, RequestOutLoudConfirmationEvent):
            return {
                "type": "confirmation_required",
                "subject": event.subject,
                "message": "For your protection, please say yes or confirm aloud before any reservation is finalized.",
            }
        if isinstance(event, RequestSecureCheckoutEvent):
            return {
                "type": "checkout_unavailable",
                "message": "Secure payment handoff is not configured. Do not send card details by voice or chat.",
            }
        raise AssertionError("Unreachable discriminated ClientUiEvent variant")


@lru_cache(maxsize=1)
def get_voice_session_manager() -> ConsumerVoiceSessionManager:
    """Return the process-wide local browser session manager."""
    return ConsumerVoiceSessionManager(get_settings())
