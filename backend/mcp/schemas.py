"""Pydantic v2 argument schemas for MCP hotel tools."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

RoomCategory = Literal["standard", "deluxe", "executive_suite"]
OpsKind = Literal["housekeeping", "luggage"]
MessageChannel = Literal["sms", "whatsapp"]
MenuItemId = Literal["burgers", "fries", "club_sandwich"]


class AvailabilityArgs(BaseModel):
    """Arguments for hotel_check_availability."""

    date_in: date
    date_out: date
    category: RoomCategory | None = None

    @model_validator(mode="after")
    def check_out_after_check_in(self) -> AvailabilityArgs:
        if self.date_out <= self.date_in:
            raise ValueError("date_out must be after date_in.")
        return self


class BookRoomArgs(BaseModel):
    """Arguments for hotel_book_room."""

    room_id: str = Field(min_length=3, max_length=16)
    date_in: date
    date_out: date
    guest_name: str = Field(min_length=1, max_length=80)

    @field_validator("room_id", "guest_name")
    @classmethod
    def strip_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Value cannot be empty.")
        return cleaned

    @model_validator(mode="after")
    def check_out_after_check_in(self) -> BookRoomArgs:
        if self.date_out <= self.date_in:
            raise ValueError("date_out must be after date_in.")
        return self


class CancelBookingArgs(BaseModel):
    """Arguments for hotel_cancel_booking."""

    booking_id: str = Field(min_length=4, max_length=32)

    @field_validator("booking_id")
    @classmethod
    def strip_id(cls, value: str) -> str:
        return value.strip().upper()


class AmenitiesArgs(BaseModel):
    """Arguments for hotel_get_amenities (no required fields)."""

    topic: str | None = None


class CalendarCreateArgs(BaseModel):
    """Arguments for calendar_create_event."""

    title: str = Field(min_length=1, max_length=120)
    start_at: datetime
    end_at: datetime
    location: str = Field(min_length=1, max_length=120)

    @model_validator(mode="after")
    def end_after_start(self) -> CalendarCreateArgs:
        if self.end_at <= self.start_at:
            raise ValueError("end_at must be after start_at.")
        return self


class WeatherArgs(BaseModel):
    """Arguments for weather_get_forecast. Defaults to Manhattan (Grand Meridian demo)."""

    latitude: float = Field(default=40.758, ge=-90.0, le=90.0)
    longitude: float = Field(default=-73.9855, ge=-180.0, le=180.0)


class OpsTicketArgs(BaseModel):
    """Arguments for hotel_ops_create_ticket."""

    kind: OpsKind
    details: str = Field(min_length=1, max_length=240)
    room_id: str | None = None


class DiningOrderArgs(BaseModel):
    """Arguments for dining_place_order."""

    guest_name: str = Field(min_length=1, max_length=80)
    items: list[MenuItemId] = Field(min_length=1, max_length=8)
    location: str = Field(min_length=1, max_length=80)


class DiningLookupArgs(BaseModel):
    """Arguments for dining_check_order / dining_cancel_order."""

    order_id: str = Field(min_length=4, max_length=32)

    @field_validator("order_id")
    @classmethod
    def strip_id(cls, value: str) -> str:
        return value.strip().upper()


class MessagingArgs(BaseModel):
    """Arguments for messaging_send."""

    channel: MessageChannel
    recipient: str = Field(min_length=5, max_length=32)
    body: str = Field(min_length=1, max_length=320)


class EmptyArgs(BaseModel):
    """Placeholder schema for read-only tools with no required arguments."""


TOOL_ARGUMENT_MODELS: dict[str, type[BaseModel]] = {
    "hotel_check_availability": AvailabilityArgs,
    "hotel_book_room": BookRoomArgs,
    "hotel_cancel_booking": CancelBookingArgs,
    "hotel_get_amenities": AmenitiesArgs,
    "calendar_list_events": EmptyArgs,
    "calendar_create_event": CalendarCreateArgs,
    "weather_get_forecast": WeatherArgs,
    "hotel_ops_create_ticket": OpsTicketArgs,
    "hotel_ops_list_tickets": EmptyArgs,
    "dining_list_menu": EmptyArgs,
    "dining_place_order": DiningOrderArgs,
    "dining_check_order": DiningLookupArgs,
    "dining_cancel_order": DiningLookupArgs,
    "messaging_send": MessagingArgs,
}


def json_schema_for_tool(name: str) -> dict[str, Any]:
    """Return a JSON Schema object for an MCP tool's arguments."""
    model = TOOL_ARGUMENT_MODELS.get(name, EmptyArgs)
    schema = model.model_json_schema()
    schema.pop("title", None)
    return schema
