"""Unit tests for the MCP hub, confirmation gate, and hotel tool servers."""

from __future__ import annotations

import asyncio
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.config.settings import load_tenant_config
from backend.mcp.client import MCPHub, ToolIsolationError, ToolTimeoutError
from backend.mcp.confirmation import user_confirms
from backend.mcp.registry import MAX_TOOLS_PER_PERSONA, tools_for_persona
from backend.mcp.session import AgentSession
from backend.mcp.store import HotelStore
from backend.mcp.tools import MCPToolServers, local_weather_stub


def _hub(tmp: str, persona: str = "hotel_booking_specialist") -> MCPHub:
    store = HotelStore(Path(tmp) / "voice_agent.db")
    session = AgentSession(persona=persona)
    servers = MCPToolServers(store, weather_fetcher=local_weather_stub)
    return MCPHub(store=store, session=session, servers=servers)


class TestConfirmationGate(unittest.TestCase):
    """Spoken confirmation must be short and explicit."""

    def test_short_yes(self):
        self.assertTrue(user_confirms("Yes, confirm the booking"))
        self.assertTrue(user_confirms("ok"))
        self.assertTrue(user_confirms("go ahead"))

    def test_long_utterance_is_not_confirmation(self):
        self.assertFalse(user_confirms("Yes please book room R-201 for Smith tonight thanks"))

    def test_empty_is_not_confirmation(self):
        self.assertFalse(user_confirms(""))
        self.assertFalse(user_confirms(None))


class TestMCPHotelBooking(unittest.IsolatedAsyncioTestCase):
    """Confirm-before-book never writes until the caller says yes."""

    async def asyncSetUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.hub = _hub(self._tmp.name)

    async def asyncTearDown(self):
        self._tmp.cleanup()

    async def test_booking_refuses_without_confirmation(self):
        self.hub.session.set_last_user_message("Book room R-201 for Smith")
        result = await self.hub.call_tool(
            "hotel_book_room",
            {
                "room_id": "R-201",
                "date_in": "2026-11-14",
                "date_out": "2026-11-17",
                "guest_name": "Smith",
            },
        )
        self.assertEqual(result["status"], "needs_confirmation")
        self.assertIsNotNone(self.hub.session.pending)
        self.assertIsNone(self.hub.store.get_booking("BK-DOES-NOT-EXIST", "grand-meridian"))

    async def test_yes_without_pending_does_not_book(self):
        self.hub.session.set_last_user_message("yes")
        result = await self.hub.call_tool(
            "hotel_book_room",
            {
                "room_id": "R-201",
                "date_in": "2026-11-14",
                "date_out": "2026-11-17",
                "guest_name": "Smith",
            },
        )
        self.assertEqual(result["status"], "needs_confirmation")

    async def test_booking_completes_with_confirmation(self):
        args = {
            "room_id": "R-201",
            "date_in": "2026-11-14",
            "date_out": "2026-11-17",
            "guest_name": "Smith",
        }
        self.hub.session.set_last_user_message("Book room R-201 for Smith")
        first = await self.hub.call_tool("hotel_book_room", args)
        self.assertEqual(first["status"], "needs_confirmation")

        self.hub.session.set_last_user_message("Yes, confirm the booking")
        second = await self.hub.call_tool("hotel_book_room", args)
        self.assertEqual(second["status"], "confirmed")
        self.assertIn("BK-", second["booking_id"])
        self.assertEqual(second["total_price"], 540.0)
        self.assertIsNone(self.hub.session.pending)

        stored = self.hub.store.get_booking(second["booking_id"], "grand-meridian")
        self.assertIsNotNone(stored)
        self.assertEqual(stored["status"], "confirmed")

    async def test_unknown_room_does_not_stage_pending(self):
        self.hub.session.set_last_user_message("Book room R-999")
        result = await self.hub.call_tool(
            "hotel_book_room",
            {
                "room_id": "R-999",
                "date_in": "2026-11-14",
                "date_out": "2026-11-17",
                "guest_name": "Smith",
            },
        )
        self.assertEqual(result["status"], "error")
        self.assertIsNone(self.hub.session.pending)

    async def test_overlap_is_unavailable(self):
        args = {
            "room_id": "R-101",
            "date_in": "2026-12-01",
            "date_out": "2026-12-04",
            "guest_name": "Patel",
        }
        self.hub.session.set_last_user_message("book it")
        await self.hub.call_tool("hotel_book_room", args)
        self.hub.session.set_last_user_message("yes")
        confirmed = await self.hub.call_tool("hotel_book_room", args)
        self.assertEqual(confirmed["status"], "confirmed")

        self.hub.session.set_last_user_message("Book the same room again")
        blocked = await self.hub.call_tool(
            "hotel_book_room",
            {
                "room_id": "R-101",
                "date_in": "2026-12-02",
                "date_out": "2026-12-03",
                "guest_name": "Lee",
            },
        )
        self.assertEqual(blocked["status"], "error")
        self.assertIn("not available", blocked["message"])

    async def test_availability_and_cancel_gate(self):
        available = await self.hub.call_tool(
            "hotel_check_availability",
            {"date_in": "2026-11-14", "date_out": "2026-11-15", "category": "deluxe"},
        )
        self.assertEqual(available["status"], "ok")
        self.assertEqual(available["rooms"][0]["room_id"], "R-201")

        args = {
            "room_id": "R-201",
            "date_in": "2026-11-14",
            "date_out": "2026-11-15",
            "guest_name": "Ng",
        }
        self.hub.session.set_last_user_message("book deluxe")
        await self.hub.call_tool("hotel_book_room", args)
        self.hub.session.set_last_user_message("confirm")
        booked = await self.hub.call_tool("hotel_book_room", args)

        self.hub.session.set_last_user_message("cancel that booking")
        pending_cancel = await self.hub.call_tool(
            "hotel_cancel_booking",
            {"booking_id": booked["booking_id"]},
        )
        self.assertEqual(pending_cancel["status"], "needs_confirmation")
        still = self.hub.store.get_booking(booked["booking_id"], "grand-meridian")
        self.assertEqual(still["status"], "confirmed")

        self.hub.session.set_last_user_message("yes")
        cancelled = await self.hub.call_tool(
            "hotel_cancel_booking",
            {"booking_id": booked["booking_id"]},
        )
        self.assertEqual(cancelled["status"], "confirmed")

    async def test_invalid_dates_rejected(self):
        result = await self.hub.call_tool(
            "hotel_check_availability",
            {"date_in": "2026-11-17", "date_out": "2026-11-14"},
        )
        self.assertEqual(result["status"], "error")

    async def test_amenities_are_spoken(self):
        result = await self.hub.call_tool("hotel_get_amenities", {"topic": "parking"})
        self.assertEqual(result["status"], "ok")
        self.assertIn("thirty five", result["message"])

    async def test_audit_log_written(self):
        await self.hub.call_tool("hotel_get_amenities", {})
        self.assertEqual(len(self.hub.session.audit), 1)
        self.assertEqual(self.hub.session.audit[0]["tool_name"], "hotel_get_amenities")
        self.assertIn("latency_ms", self.hub.session.audit[0])


class TestPersonaIsolation(unittest.IsolatedAsyncioTestCase):
    """Personas cannot invoke another desk's tools and see at most four tools."""

    async def asyncSetUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.hub = _hub(self._tmp.name, persona="hotel_booking_specialist")

    async def asyncTearDown(self):
        self._tmp.cleanup()

    def test_max_four_tools(self):
        for persona, names in {
            "hotel_booking_specialist": True,
            "restaurant_dining": True,
            "travel_desk": True,
        }.items():
            tools = tools_for_persona(persona)
            self.assertLessEqual(len(tools), MAX_TOOLS_PER_PERSONA)
            self.assertTrue(names)

    async def test_hotel_cannot_place_dining_order(self):
        with self.assertRaises(ToolIsolationError):
            await self.hub.call_tool(
                "dining_place_order",
                {"guest_name": "Smith", "items": ["burgers"], "location": "Room R-201"},
            )

    async def test_dining_cannot_book_room(self):
        dining = _hub(self._tmp.name, persona="restaurant_dining")
        with self.assertRaises(ToolIsolationError):
            await dining.call_tool(
                "hotel_book_room",
                {
                    "room_id": "R-201",
                    "date_in": "2026-11-14",
                    "date_out": "2026-11-17",
                    "guest_name": "Smith",
                },
            )

    def test_list_tools_matches_tenant_yaml(self):
        tenant = load_tenant_config("default_hotel.yaml")
        persona = tenant.get_active_persona()
        listed = [entry["name"] for entry in self.hub.list_tools(persona.key)]
        self.assertEqual(listed, persona.tools)
        self.assertEqual(len(listed), 4)

    def test_tool_catalog_includes_json_schema(self):
        catalog = {entry["name"]: entry for entry in self.hub.list_tools()}
        book_schema = catalog["hotel_book_room"]["inputSchema"]
        self.assertIn("room_id", book_schema.get("properties", {}))
        self.assertIn("guest_name", book_schema.get("properties", {}))

    async def test_tool_timeout(self):
        class SlowServers(MCPToolServers):
            async def hotel_get_amenities(self, session, arguments):
                await asyncio.sleep(1.0)
                return {"status": "ok", "message": "late"}

        store = HotelStore(Path(self._tmp.name) / "timeout.db")
        hub = MCPHub(
            store=store,
            session=AgentSession(),
            timeout_seconds=0.05,
            servers=SlowServers(store, weather_fetcher=local_weather_stub),
        )
        with self.assertRaises(ToolTimeoutError):
            await hub.call_tool("hotel_get_amenities", {})


class TestOtherMcpServers(unittest.IsolatedAsyncioTestCase):
    """Calendar, weather, ops, dining, and messaging servers."""

    async def asyncSetUp(self):
        self._tmp = tempfile.TemporaryDirectory()

    async def asyncTearDown(self):
        self._tmp.cleanup()

    async def test_weather_offline_stub(self):
        hub = _hub(self._tmp.name, persona="travel_desk")
        result = await hub.call_tool("weather_get_forecast", {})
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["temperature_celsius"], 21.0)

    async def test_calendar_requires_confirmation(self):
        hub = _hub(self._tmp.name, persona="travel_desk")
        args = {
            "title": "Airport pickup",
            "start_at": "2026-11-14T15:00:00",
            "end_at": "2026-11-14T16:00:00",
            "location": "Lobby",
        }
        hub.session.set_last_user_message("schedule airport pickup")
        first = await hub.call_tool("calendar_create_event", args)
        self.assertEqual(first["status"], "needs_confirmation")
        hub.session.set_last_user_message("yes")
        second = await hub.call_tool("calendar_create_event", args)
        self.assertEqual(second["status"], "confirmed")
        self.assertIn("EV-", second["event_id"])

    async def test_dining_order_and_seed_lookup(self):
        hub = _hub(self._tmp.name, persona="restaurant_dining")
        lookup = await hub.call_tool("dining_check_order", {"order_id": "ORD-SEED-1"})
        self.assertEqual(lookup["status"], "ok")
        self.assertEqual(lookup["order"]["location"], "Booth B1")

        args = {
            "guest_name": "Rivera",
            "items": ["burgers", "fries"],
            "location": "Room R-101",
        }
        hub.session.set_last_user_message("order burgers")
        pending = await hub.call_tool("dining_place_order", args)
        self.assertEqual(pending["status"], "needs_confirmation")
        hub.session.set_last_user_message("yes")
        placed = await hub.call_tool("dining_place_order", args)
        self.assertEqual(placed["status"], "confirmed")
        self.assertEqual(placed["total_price"], 25.0)

    async def test_ops_ticket_confirmation(self):
        hub = _hub(self._tmp.name, persona="hotel_ops")
        args = {"kind": "housekeeping", "details": "Need extra towels", "room_id": "R-101"}
        hub.session.set_last_user_message("send housekeeping")
        pending = await hub.call_tool("hotel_ops_create_ticket", args)
        self.assertEqual(pending["status"], "needs_confirmation")
        hub.session.set_last_user_message("okay")
        created = await hub.call_tool("hotel_ops_create_ticket", args)
        self.assertEqual(created["status"], "confirmed")
        self.assertIn("TK-", created["ticket_id"])

    async def test_messaging_is_local_stub(self):
        hub = _hub(self._tmp.name, persona="customer_care")
        args = {"channel": "sms", "recipient": "+15551212", "body": "Your room is ready."}
        hub.session.set_last_user_message("text the guest")
        pending = await hub.call_tool("messaging_send", args)
        self.assertEqual(pending["status"], "needs_confirmation")
        hub.session.set_last_user_message("yes")
        sent = await hub.call_tool("messaging_send", args)
        self.assertEqual(sent["status"], "confirmed")
        self.assertEqual(sent["delivery"], "local_stub")


if __name__ == "__main__":
    unittest.main()
