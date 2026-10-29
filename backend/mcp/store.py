"""Transactional SQLite persistence for rooms, bookings, tickets, orders, and events."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Generator
from uuid import uuid4

SEED_ROOMS: tuple[tuple[str, str, float], ...] = (
    ("R-101", "standard", 120.0),
    ("R-201", "deluxe", 180.0),
    ("R-301", "executive_suite", 260.0),
)

DINING_MENU: tuple[tuple[str, str, float], ...] = (
    ("burgers", "Cheeseburger", 18.0),
    ("fries", "Seasoned fries", 7.0),
    ("club_sandwich", "Club sandwich", 16.0),
)


def resolve_sqlite_path(database_url: str) -> Path:
    """Convert a SQLAlchemy-style sqlite URL into a filesystem path."""
    prefix = "sqlite:///"
    if database_url.startswith(prefix):
        return Path(database_url[len(prefix) :])
    return Path(database_url)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_iso_date(value: str) -> date:
    return date.fromisoformat(value)


class HotelStore:
    """SQLite-backed hotel operations store with ACID writes."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        if str(self.db_path) != ":memory:":
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @contextmanager
    def connect(self) -> Generator[sqlite3.Connection, None, None]:
        """Yield a transactional connection that commits on success."""
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _init_schema(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS rooms (
                    room_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    category TEXT NOT NULL,
                    nightly_rate REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS bookings (
                    booking_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    guest_name TEXT NOT NULL,
                    room_id TEXT NOT NULL,
                    check_in TEXT NOT NULL,
                    check_out TEXT NOT NULL,
                    total_price REAL NOT NULL,
                    status TEXT NOT NULL DEFAULT 'confirmed',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (room_id) REFERENCES rooms(room_id)
                );
                CREATE TABLE IF NOT EXISTS tickets (
                    ticket_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    details TEXT NOT NULL,
                    room_id TEXT,
                    status TEXT NOT NULL DEFAULT 'open',
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS orders (
                    order_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    guest_name TEXT NOT NULL,
                    items TEXT NOT NULL,
                    location TEXT NOT NULL,
                    total_price REAL NOT NULL,
                    status TEXT NOT NULL DEFAULT 'confirmed',
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS events (
                    event_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    start_at TEXT NOT NULL,
                    end_at TEXT NOT NULL,
                    location TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS messages (
                    message_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    recipient TEXT NOT NULL,
                    body TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )
            existing = conn.execute("SELECT COUNT(*) AS n FROM rooms").fetchone()["n"]
            if existing == 0:
                conn.executemany(
                    "INSERT INTO rooms (room_id, tenant_id, category, nightly_rate) VALUES (?, ?, ?, ?)",
                    [
                        (room_id, "grand-meridian", category, rate)
                        for room_id, category, rate in SEED_ROOMS
                    ],
                )
            order_count = conn.execute("SELECT COUNT(*) AS n FROM orders").fetchone()["n"]
            if order_count == 0:
                conn.execute(
                    """
                    INSERT INTO orders (order_id, tenant_id, guest_name, items, location, total_price, status, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "ORD-SEED-1",
                        "grand-meridian",
                        "Walk-in guest",
                        "burgers,fries",
                        "Booth B1",
                        25.0,
                        "confirmed",
                        _utc_now(),
                    ),
                )

    def get_room(self, room_id: str, tenant_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM rooms WHERE room_id = ? AND tenant_id = ?",
                (room_id, tenant_id),
            ).fetchone()
        return dict(row) if row else None

    def list_rooms(self, tenant_id: str, category: str | None = None) -> list[dict[str, Any]]:
        with self.connect() as conn:
            if category:
                rows = conn.execute(
                    "SELECT * FROM rooms WHERE tenant_id = ? AND category = ? ORDER BY room_id",
                    (tenant_id, category),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM rooms WHERE tenant_id = ? ORDER BY room_id",
                    (tenant_id,),
                ).fetchall()
        return [dict(row) for row in rows]

    def is_room_available(
        self,
        room_id: str,
        tenant_id: str,
        check_in: str,
        check_out: str,
        ignore_booking_id: str | None = None,
    ) -> bool:
        """Return True when no confirmed booking overlaps [check_in, check_out)."""
        query = """
            SELECT booking_id FROM bookings
            WHERE tenant_id = ? AND room_id = ? AND status = 'confirmed'
              AND check_in < ? AND check_out > ?
        """
        params: list[Any] = [tenant_id, room_id, check_out, check_in]
        if ignore_booking_id:
            query += " AND booking_id != ?"
            params.append(ignore_booking_id)
        with self.connect() as conn:
            conflict = conn.execute(query, params).fetchone()
        return conflict is None

    def available_rooms(
        self,
        tenant_id: str,
        check_in: str,
        check_out: str,
        category: str | None = None,
    ) -> list[dict[str, Any]]:
        rooms = self.list_rooms(tenant_id, category=category)
        return [
            room
            for room in rooms
            if self.is_room_available(room["room_id"], tenant_id, check_in, check_out)
        ]

    def create_booking(
        self,
        tenant_id: str,
        guest_name: str,
        room_id: str,
        check_in: str,
        check_out: str,
    ) -> dict[str, Any]:
        room = self.get_room(room_id, tenant_id)
        if room is None:
            raise ValueError(f"Unknown room {room_id}.")
        nights = (_parse_iso_date(check_out) - _parse_iso_date(check_in)).days
        if nights < 1:
            raise ValueError("Check-out date must be after check-in date.")
        if not self.is_room_available(room_id, tenant_id, check_in, check_out):
            raise ValueError(f"Room {room_id} is not available for those dates.")

        booking_id = f"BK-{uuid4().hex[:8].upper()}"
        total_price = round(room["nightly_rate"] * nights, 2)
        record = {
            "booking_id": booking_id,
            "tenant_id": tenant_id,
            "guest_name": guest_name,
            "room_id": room_id,
            "check_in": check_in,
            "check_out": check_out,
            "total_price": total_price,
            "status": "confirmed",
            "created_at": _utc_now(),
        }
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO bookings (
                    booking_id, tenant_id, guest_name, room_id, check_in, check_out,
                    total_price, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record["booking_id"],
                    record["tenant_id"],
                    record["guest_name"],
                    record["room_id"],
                    record["check_in"],
                    record["check_out"],
                    record["total_price"],
                    record["status"],
                    record["created_at"],
                ),
            )
        return record

    def get_booking(self, booking_id: str, tenant_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM bookings WHERE booking_id = ? AND tenant_id = ?",
                (booking_id, tenant_id),
            ).fetchone()
        return dict(row) if row else None

    def cancel_booking(self, booking_id: str, tenant_id: str) -> dict[str, Any]:
        booking = self.get_booking(booking_id, tenant_id)
        if booking is None:
            raise ValueError(f"Unknown booking {booking_id}.")
        if booking["status"] == "cancelled":
            raise ValueError(f"Booking {booking_id} is already cancelled.")
        with self.connect() as conn:
            conn.execute(
                "UPDATE bookings SET status = 'cancelled' WHERE booking_id = ? AND tenant_id = ?",
                (booking_id, tenant_id),
            )
        booking["status"] = "cancelled"
        return booking

    def create_ticket(
        self,
        tenant_id: str,
        kind: str,
        details: str,
        room_id: str | None = None,
    ) -> dict[str, Any]:
        ticket_id = f"TK-{uuid4().hex[:8].upper()}"
        record = {
            "ticket_id": ticket_id,
            "tenant_id": tenant_id,
            "kind": kind,
            "details": details,
            "room_id": room_id,
            "status": "open",
            "created_at": _utc_now(),
        }
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO tickets (ticket_id, tenant_id, kind, details, room_id, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record["ticket_id"],
                    record["tenant_id"],
                    record["kind"],
                    record["details"],
                    record["room_id"],
                    record["status"],
                    record["created_at"],
                ),
            )
        return record

    def list_tickets(self, tenant_id: str) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM tickets WHERE tenant_id = ? ORDER BY created_at DESC",
                (tenant_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def menu_item(self, item_id: str) -> tuple[str, str, float] | None:
        for entry in DINING_MENU:
            if entry[0] == item_id:
                return entry
        return None

    def create_order(
        self,
        tenant_id: str,
        guest_name: str,
        item_ids: list[str],
        location: str,
    ) -> dict[str, Any]:
        lines: list[str] = []
        total = 0.0
        for item_id in item_ids:
            menu = self.menu_item(item_id)
            if menu is None:
                raise ValueError(f"Unknown menu item {item_id}.")
            lines.append(menu[0])
            total += menu[2]
        order_id = f"ORD-{uuid4().hex[:8].upper()}"
        record = {
            "order_id": order_id,
            "tenant_id": tenant_id,
            "guest_name": guest_name,
            "items": ",".join(lines),
            "location": location,
            "total_price": round(total, 2),
            "status": "confirmed",
            "created_at": _utc_now(),
        }
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO orders (
                    order_id, tenant_id, guest_name, items, location, total_price, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record["order_id"],
                    record["tenant_id"],
                    record["guest_name"],
                    record["items"],
                    record["location"],
                    record["total_price"],
                    record["status"],
                    record["created_at"],
                ),
            )
        return record

    def get_order(self, order_id: str, tenant_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM orders WHERE order_id = ? AND tenant_id = ?",
                (order_id, tenant_id),
            ).fetchone()
        return dict(row) if row else None

    def cancel_order(self, order_id: str, tenant_id: str) -> dict[str, Any]:
        order = self.get_order(order_id, tenant_id)
        if order is None:
            raise ValueError(f"Unknown order {order_id}.")
        if order["status"] == "cancelled":
            raise ValueError(f"Order {order_id} is already cancelled.")
        with self.connect() as conn:
            conn.execute(
                "UPDATE orders SET status = 'cancelled' WHERE order_id = ? AND tenant_id = ?",
                (order_id, tenant_id),
            )
        order["status"] = "cancelled"
        return order

    def create_event(
        self,
        tenant_id: str,
        title: str,
        start_at: str,
        end_at: str,
        location: str,
    ) -> dict[str, Any]:
        event_id = f"EV-{uuid4().hex[:8].upper()}"
        record = {
            "event_id": event_id,
            "tenant_id": tenant_id,
            "title": title,
            "start_at": start_at,
            "end_at": end_at,
            "location": location,
            "created_at": _utc_now(),
        }
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO events (event_id, tenant_id, title, start_at, end_at, location, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record["event_id"],
                    record["tenant_id"],
                    record["title"],
                    record["start_at"],
                    record["end_at"],
                    record["location"],
                    record["created_at"],
                ),
            )
        return record

    def list_events(self, tenant_id: str) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM events WHERE tenant_id = ? ORDER BY start_at",
                (tenant_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def record_message(
        self,
        tenant_id: str,
        channel: str,
        recipient: str,
        body: str,
        status: str,
    ) -> dict[str, Any]:
        message_id = f"MSG-{uuid4().hex[:8].upper()}"
        record = {
            "message_id": message_id,
            "tenant_id": tenant_id,
            "channel": channel,
            "recipient": recipient,
            "body": body,
            "status": status,
            "created_at": _utc_now(),
        }
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO messages (
                    message_id, tenant_id, channel, recipient, body, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record["message_id"],
                    record["tenant_id"],
                    record["channel"],
                    record["recipient"],
                    record["body"],
                    record["status"],
                    record["created_at"],
                ),
            )
        return record
