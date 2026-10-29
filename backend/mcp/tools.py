"""In-process MCP tool servers for hotel, calendar, weather, ops, dining, and messaging."""

from __future__ import annotations

import json
import logging
import urllib.request
from typing import Any, Callable

from pydantic import ValidationError

from backend.mcp.confirmation import confirmation_granted
from backend.mcp.schemas import (
    AmenitiesArgs,
    AvailabilityArgs,
    BookRoomArgs,
    CalendarCreateArgs,
    CancelBookingArgs,
    DiningLookupArgs,
    DiningOrderArgs,
    MessagingArgs,
    OpsTicketArgs,
    WeatherArgs,
)
from backend.mcp.session import AgentSession
from backend.mcp.store import DINING_MENU, HotelStore

logger = logging.getLogger(__name__)

TOOL_TIMEOUT_SECONDS = 1.5
DEFAULT_WEATHER_LATITUDE = 40.758
DEFAULT_WEATHER_LONGITUDE = -73.9855

AMENITIES: dict[str, str] = {
    "parking": "Valet parking is thirty five dollars per night. Self parking is twenty dollars.",
    "pets": "Dogs and cats up to fifty pounds are welcome with a seventy five dollar cleaning fee.",
    "pool": "The rooftop pool is open daily from 6 AM to 10 PM.",
    "wifi": "Complimentary Wi-Fi is available on GrandMeridian_Guest using your room number.",
    "breakfast": "Hot breakfast is served at The Grand Terrace from 6:30 AM to 10:30 AM.",
    "default": "Guests have complimentary Wi-Fi, a rooftop pool until 10 PM, and valet parking.",
}

WeatherFetcher = Callable[[float, float], dict[str, Any]]


def _needs_confirmation(message: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"status": "needs_confirmation", "message": message}
    if extra:
        payload.update(extra)
    return payload


def _error(message: str) -> dict[str, Any]:
    return {"status": "error", "message": message}


def _validation_error(exc: ValidationError) -> dict[str, Any]:
    first = exc.errors()[0]
    location = ".".join(str(part) for part in first.get("loc", ()))
    return _error(f"Invalid {location or 'arguments'}: {first.get('msg', 'invalid value')}.")


def _iso(value: Any) -> str:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


class MCPToolServers:
    """Concrete tool implementations used by the in-process MCP hub."""

    def __init__(
        self,
        store: HotelStore,
        weather_fetcher: WeatherFetcher | None = None,
    ) -> None:
        self.store = store
        self.weather_fetcher = weather_fetcher or fetch_open_meteo_forecast

    def hotel_check_availability(self, session: AgentSession, arguments: dict[str, Any]) -> dict[str, Any]:
        try:
            args = AvailabilityArgs.model_validate(arguments)
        except ValidationError as exc:
            return _validation_error(exc)
        rooms = self.store.available_rooms(
            tenant_id=session.tenant_id,
            check_in=args.date_in.isoformat(),
            check_out=args.date_out.isoformat(),
            category=args.category,
        )
        spoken = (
            f"{len(rooms)} rooms are available from {args.date_in.isoformat()} to {args.date_out.isoformat()}."
            if rooms
            else "No rooms are available for those dates."
        )
        return {
            "status": "ok",
            "rooms": [
                {
                    "room_id": room["room_id"],
                    "category": room["category"],
                    "nightly_rate": room["nightly_rate"],
                }
                for room in rooms
            ],
            "message": spoken,
        }

    def hotel_book_room(self, session: AgentSession, arguments: dict[str, Any]) -> dict[str, Any]:
        try:
            args = BookRoomArgs.model_validate(arguments)
        except ValidationError as exc:
            return _validation_error(exc)

        payload = {
            "room_id": args.room_id,
            "date_in": args.date_in.isoformat(),
            "date_out": args.date_out.isoformat(),
            "guest_name": args.guest_name,
        }
        if self.store.get_room(args.room_id, session.tenant_id) is None:
            return _error(f"Unknown room {args.room_id}.")
        if not self.store.is_room_available(
            args.room_id, session.tenant_id, payload["date_in"], payload["date_out"]
        ):
            return _error(f"Room {args.room_id} is not available for those dates.")
        if not confirmation_granted(session.pending, "hotel_book_room", payload, session.last_user_message):
            session.stage_pending("hotel_book_room", payload)
            return _needs_confirmation(
                f"Room {args.room_id} from {payload['date_in']} to {payload['date_out']} "
                f"for {args.guest_name}. Ask the caller to confirm out loud before booking.",
                extra={"room_id": args.room_id},
            )

        try:
            booking = self.store.create_booking(
                tenant_id=session.tenant_id,
                guest_name=args.guest_name,
                room_id=args.room_id,
                check_in=payload["date_in"],
                check_out=payload["date_out"],
            )
        except ValueError as exc:
            session.clear_pending()
            return _error(str(exc))

        session.clear_pending()
        return {
            "status": "confirmed",
            "booking_id": booking["booking_id"],
            "total_price": booking["total_price"],
            "message": f"Booking confirmed. Give the caller their booking reference number: {booking['booking_id']}.",
        }

    def hotel_cancel_booking(self, session: AgentSession, arguments: dict[str, Any]) -> dict[str, Any]:
        try:
            args = CancelBookingArgs.model_validate(arguments)
        except ValidationError as exc:
            return _validation_error(exc)

        payload = {"booking_id": args.booking_id}
        existing = self.store.get_booking(args.booking_id, session.tenant_id)
        if existing is None:
            return _error(f"Unknown booking {args.booking_id}.")
        if existing["status"] == "cancelled":
            return _error(f"Booking {args.booking_id} is already cancelled.")
        if not confirmation_granted(session.pending, "hotel_cancel_booking", payload, session.last_user_message):
            session.stage_pending("hotel_cancel_booking", payload)
            return _needs_confirmation(
                f"Cancel booking {args.booking_id}. Ask the caller to confirm out loud before cancelling."
            )

        try:
            booking = self.store.cancel_booking(args.booking_id, session.tenant_id)
        except ValueError as exc:
            session.clear_pending()
            return _error(str(exc))

        session.clear_pending()
        return {
            "status": "confirmed",
            "booking_id": booking["booking_id"],
            "message": f"Booking {booking['booking_id']} is cancelled.",
        }

    def hotel_get_amenities(self, session: AgentSession, arguments: dict[str, Any]) -> dict[str, Any]:
        try:
            args = AmenitiesArgs.model_validate(arguments or {})
        except ValidationError as exc:
            return _validation_error(exc)
        topic = (args.topic or "default").strip().lower()
        message = AMENITIES.get(topic, AMENITIES["default"])
        return {"status": "ok", "message": message}

    def calendar_list_events(self, session: AgentSession, arguments: dict[str, Any]) -> dict[str, Any]:
        events = self.store.list_events(session.tenant_id)
        return {
            "status": "ok",
            "events": events,
            "message": f"There are {len(events)} scheduled events on file.",
        }

    def calendar_create_event(self, session: AgentSession, arguments: dict[str, Any]) -> dict[str, Any]:
        try:
            args = CalendarCreateArgs.model_validate(arguments)
        except ValidationError as exc:
            return _validation_error(exc)

        payload = {
            "title": args.title.strip(),
            "start_at": _iso(args.start_at),
            "end_at": _iso(args.end_at),
            "location": args.location.strip(),
        }
        if not confirmation_granted(session.pending, "calendar_create_event", payload, session.last_user_message):
            session.stage_pending("calendar_create_event", payload)
            return _needs_confirmation(
                f"Schedule {payload['title']} at {payload['location']}. Ask the caller to confirm out loud."
            )

        event = self.store.create_event(
            tenant_id=session.tenant_id,
            title=payload["title"],
            start_at=payload["start_at"],
            end_at=payload["end_at"],
            location=payload["location"],
        )
        session.clear_pending()
        return {
            "status": "confirmed",
            "event_id": event["event_id"],
            "message": f"Event scheduled. Reference {event['event_id']}.",
        }

    def weather_get_forecast(self, session: AgentSession, arguments: dict[str, Any]) -> dict[str, Any]:
        raw = dict(arguments or {})
        raw.setdefault("latitude", DEFAULT_WEATHER_LATITUDE)
        raw.setdefault("longitude", DEFAULT_WEATHER_LONGITUDE)
        try:
            args = WeatherArgs.model_validate(raw)
        except ValidationError as exc:
            return _validation_error(exc)
        try:
            forecast = self.weather_fetcher(args.latitude, args.longitude)
        except Exception as exc:
            logger.warning("Weather fetch failed: %s", exc)
            return _error("Weather is unavailable right now. I can check with the front desk.")
        temperature = forecast.get("temperature_celsius")
        summary = forecast.get("summary") or f"Current temperature is {temperature} degrees Celsius."
        return {
            "status": "ok",
            "temperature_celsius": temperature,
            "summary": summary,
            "message": summary,
        }

    def hotel_ops_create_ticket(self, session: AgentSession, arguments: dict[str, Any]) -> dict[str, Any]:
        try:
            args = OpsTicketArgs.model_validate(arguments)
        except ValidationError as exc:
            return _validation_error(exc)

        payload = {
            "kind": args.kind,
            "details": args.details.strip(),
            "room_id": args.room_id,
        }
        if not confirmation_granted(session.pending, "hotel_ops_create_ticket", payload, session.last_user_message):
            session.stage_pending("hotel_ops_create_ticket", payload)
            return _needs_confirmation(
                f"Open a {args.kind} ticket. Ask the caller to confirm out loud before submitting."
            )

        ticket = self.store.create_ticket(
            tenant_id=session.tenant_id,
            kind=payload["kind"],
            details=payload["details"],
            room_id=payload["room_id"],
        )
        session.clear_pending()
        return {
            "status": "confirmed",
            "ticket_id": ticket["ticket_id"],
            "message": f"Ticket {ticket['ticket_id']} is open for {args.kind}.",
        }

    def hotel_ops_list_tickets(self, session: AgentSession, arguments: dict[str, Any]) -> dict[str, Any]:
        tickets = self.store.list_tickets(session.tenant_id)
        return {
            "status": "ok",
            "tickets": tickets,
            "message": f"There are {len(tickets)} operations tickets on file.",
        }

    def dining_list_menu(self, session: AgentSession, arguments: dict[str, Any]) -> dict[str, Any]:
        items = [
            {"item_id": item_id, "name": name, "price": price}
            for item_id, name, price in DINING_MENU
        ]
        return {
            "status": "ok",
            "items": items,
            "message": "The kitchen has burgers, fries, and a club sandwich.",
        }

    def dining_place_order(self, session: AgentSession, arguments: dict[str, Any]) -> dict[str, Any]:
        try:
            args = DiningOrderArgs.model_validate(arguments)
        except ValidationError as exc:
            return _validation_error(exc)

        payload = {
            "guest_name": args.guest_name.strip(),
            "items": list(args.items),
            "location": args.location.strip(),
        }
        if not confirmation_granted(session.pending, "dining_place_order", payload, session.last_user_message):
            session.stage_pending("dining_place_order", payload)
            return _needs_confirmation(
                f"Order {', '.join(payload['items'])} for {payload['guest_name']}. "
                "Ask the caller to confirm out loud before sending it to the kitchen."
            )

        try:
            order = self.store.create_order(
                tenant_id=session.tenant_id,
                guest_name=payload["guest_name"],
                item_ids=payload["items"],
                location=payload["location"],
            )
        except ValueError as exc:
            session.clear_pending()
            return _error(str(exc))

        session.clear_pending()
        return {
            "status": "confirmed",
            "order_id": order["order_id"],
            "total_price": order["total_price"],
            "message": f"Order confirmed. Reference {order['order_id']}.",
        }

    def dining_check_order(self, session: AgentSession, arguments: dict[str, Any]) -> dict[str, Any]:
        try:
            args = DiningLookupArgs.model_validate(arguments)
        except ValidationError as exc:
            return _validation_error(exc)
        order = self.store.get_order(args.order_id, session.tenant_id)
        if order is None:
            return _error(f"Unknown order {args.order_id}.")
        return {
            "status": "ok",
            "order": order,
            "message": f"Order {order['order_id']} is {order['status']}.",
        }

    def dining_cancel_order(self, session: AgentSession, arguments: dict[str, Any]) -> dict[str, Any]:
        try:
            args = DiningLookupArgs.model_validate(arguments)
        except ValidationError as exc:
            return _validation_error(exc)
        payload = {"order_id": args.order_id}
        if not confirmation_granted(session.pending, "dining_cancel_order", payload, session.last_user_message):
            session.stage_pending("dining_cancel_order", payload)
            return _needs_confirmation(
                f"Cancel order {args.order_id}. Ask the caller to confirm out loud before cancelling."
            )
        try:
            order = self.store.cancel_order(args.order_id, session.tenant_id)
        except ValueError as exc:
            session.clear_pending()
            return _error(str(exc))
        session.clear_pending()
        return {
            "status": "confirmed",
            "order_id": order["order_id"],
            "message": f"Order {order['order_id']} is cancelled.",
        }

    def messaging_send(self, session: AgentSession, arguments: dict[str, Any]) -> dict[str, Any]:
        try:
            args = MessagingArgs.model_validate(arguments)
        except ValidationError as exc:
            return _validation_error(exc)

        payload = {
            "channel": args.channel,
            "recipient": args.recipient.strip(),
            "body": args.body.strip(),
        }
        if not confirmation_granted(session.pending, "messaging_send", payload, session.last_user_message):
            session.stage_pending("messaging_send", payload)
            return _needs_confirmation(
                f"Send a {args.channel} message. Ask the caller to confirm out loud before sending."
            )

        record = self.store.record_message(
            tenant_id=session.tenant_id,
            channel=payload["channel"],
            recipient=payload["recipient"],
            body=payload["body"],
            status="queued_local",
        )
        session.clear_pending()
        return {
            "status": "confirmed",
            "message_id": record["message_id"],
            "delivery": "local_stub",
            "message": f"Message queued locally as {record['message_id']}. No external SMS was sent.",
        }


def fetch_open_meteo_forecast(latitude: float, longitude: float) -> dict[str, Any]:
    """Fetch current temperature from Open-Meteo (no API key)."""
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={latitude}&longitude={longitude}"
        "&current=temperature_2m,weather_code&timezone=auto"
    )
    request = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(request, timeout=TOOL_TIMEOUT_SECONDS) as response:
        body = json.loads(response.read().decode("utf-8"))
    current = body.get("current") or {}
    temperature = current.get("temperature_2m")
    if temperature is None:
        raise RuntimeError("Open-Meteo response missing temperature.")
    return {
        "temperature_celsius": temperature,
        "summary": f"Current temperature is {temperature} degrees Celsius.",
    }


def local_weather_stub(latitude: float, longitude: float) -> dict[str, Any]:
    """Deterministic offline forecast used by tests and air-gapped deploys."""
    _ = (latitude, longitude)
    return {
        "temperature_celsius": 21.0,
        "summary": "Current temperature is 21 degrees Celsius. Skies are clear.",
    }
