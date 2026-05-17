"""Tests for PATCH /rooms/{id}/availability/{date} and RoomRead extra fields."""
from __future__ import annotations

from datetime import date, timedelta

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.availability import RoomAvailability
from app.models.sanatorium import SanatoriumStatus
from tests.factories import make_sanatorium
from tests.test_availability import make_room


class TestAvailabilityUpsert:
    async def test_upsert_creates_when_missing(
        self,
        client: AsyncClient,
        db: AsyncSession,
        admin_user,
        admin_headers,
    ):
        san = await make_sanatorium(
            db, slug="upsert-1", admin_user_id=admin_user.id,
            status=SanatoriumStatus.APPROVED,
        )
        room = await make_room(db, sanatorium=san)
        target = (date.today() + timedelta(days=7)).isoformat()
        resp = await client.patch(
            f"/api/rooms/{room.id}/availability/{target}",
            json={"units_total": 5},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["units_total"] == 5
        assert body["units_available"] == 5

    async def test_upsert_updates_existing_preserves_booked(
        self,
        client: AsyncClient,
        db: AsyncSession,
        admin_user,
        admin_headers,
    ):
        san = await make_sanatorium(
            db, slug="upsert-2", admin_user_id=admin_user.id,
            status=SanatoriumStatus.APPROVED,
        )
        room = await make_room(db, sanatorium=san)
        target = date.today() + timedelta(days=7)

        # Existing row: 5 units, 2 already booked → 3 available
        row = RoomAvailability(
            room_id=room.id, date=target, units_total=5, units_available=3
        )
        db.add(row)
        await db.commit()

        # Increase total to 10 → should preserve booked count, new available = 8
        resp = await client.patch(
            f"/api/rooms/{room.id}/availability/{target.isoformat()}",
            json={"units_total": 10},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json() == {
            "date": target.isoformat(),
            "units_total": 10,
            "units_available": 8,
        }

    async def test_upsert_below_booked_returns_409(
        self,
        client: AsyncClient,
        db: AsyncSession,
        admin_user,
        admin_headers,
    ):
        san = await make_sanatorium(
            db, slug="upsert-3", admin_user_id=admin_user.id,
            status=SanatoriumStatus.APPROVED,
        )
        room = await make_room(db, sanatorium=san)
        target = date.today() + timedelta(days=7)
        row = RoomAvailability(
            room_id=room.id, date=target, units_total=5, units_available=2
        )
        db.add(row)
        await db.commit()
        # 3 bookings exist (5 - 2). Try setting total to 2 → rejected.
        resp = await client.patch(
            f"/api/rooms/{room.id}/availability/{target.isoformat()}",
            json={"units_total": 2},
            headers=admin_headers,
        )
        assert resp.status_code == 409

    async def test_upsert_to_zero_blocks_date(
        self,
        client: AsyncClient,
        db: AsyncSession,
        admin_user,
        admin_headers,
    ):
        san = await make_sanatorium(
            db, slug="upsert-4", admin_user_id=admin_user.id,
            status=SanatoriumStatus.APPROVED,
        )
        room = await make_room(db, sanatorium=san)
        target = (date.today() + timedelta(days=7)).isoformat()
        resp = await client.patch(
            f"/api/rooms/{room.id}/availability/{target}",
            json={"units_total": 0},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["units_total"] == 0
        assert resp.json()["units_available"] == 0

    async def test_upsert_anon_returns_401(
        self, client: AsyncClient, db: AsyncSession
    ):
        san = await make_sanatorium(db, slug="upsert-anon")
        room = await make_room(db, sanatorium=san)
        target = (date.today() + timedelta(days=7)).isoformat()
        resp = await client.patch(
            f"/api/rooms/{room.id}/availability/{target}",
            json={"units_total": 5},
        )
        assert resp.status_code == 401

    async def test_upsert_other_admin_returns_403(
        self,
        client: AsyncClient,
        db: AsyncSession,
        admin_user,
        admin_headers,
    ):
        # Create sanatorium owned by someone else
        san = await make_sanatorium(db, slug="upsert-other")
        room = await make_room(db, sanatorium=san)
        target = (date.today() + timedelta(days=7)).isoformat()
        resp = await client.patch(
            f"/api/rooms/{room.id}/availability/{target}",
            json={"units_total": 5},
            headers=admin_headers,
        )
        assert resp.status_code == 403


class TestRoomAvailabilityFields:
    async def test_room_without_availability_flags(
        self, client: AsyncClient, db: AsyncSession
    ):
        san = await make_sanatorium(db, slug="avail-1")
        room = await make_room(db, sanatorium=san)
        resp = await client.get(f"/api/rooms/{room.id}")
        body = resp.json()
        assert body["has_availability"] is False
        assert body["availability_until"] is None

    async def test_room_with_future_availability(
        self,
        client: AsyncClient,
        db: AsyncSession,
        admin_user,
        admin_headers,
    ):
        san = await make_sanatorium(
            db, slug="avail-2", admin_user_id=admin_user.id,
            status=SanatoriumStatus.APPROVED,
        )
        room = await make_room(db, sanatorium=san)
        target = (date.today() + timedelta(days=30)).isoformat()
        await client.patch(
            f"/api/rooms/{room.id}/availability/{target}",
            json={"units_total": 3},
            headers=admin_headers,
        )
        resp = await client.get(f"/api/rooms/{room.id}")
        body = resp.json()
        assert body["has_availability"] is True
        assert body["availability_until"] == target

    async def test_room_with_only_zero_units_no_availability(
        self,
        client: AsyncClient,
        db: AsyncSession,
        admin_user,
        admin_headers,
    ):
        san = await make_sanatorium(
            db, slug="avail-3", admin_user_id=admin_user.id,
            status=SanatoriumStatus.APPROVED,
        )
        room = await make_room(db, sanatorium=san)
        target = (date.today() + timedelta(days=30)).isoformat()
        await client.patch(
            f"/api/rooms/{room.id}/availability/{target}",
            json={"units_total": 0},
            headers=admin_headers,
        )
        resp = await client.get(f"/api/rooms/{room.id}")
        body = resp.json()
        # Zero-units rows don't count as "has availability"
        assert body["has_availability"] is False
