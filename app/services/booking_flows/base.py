from __future__ import annotations

from typing import Protocol

from app.models.booking import Booking
from app.models.user import User
from app.schemas.booking import BookingCreate


class BookingFlow(Protocol):
    """Each booking type (ROOM, SESSION, future PACKAGE…) is its own flow."""

    def matches(self, payload: BookingCreate) -> bool: ...

    async def create(
        self, payload: BookingCreate, user: User
    ) -> Booking: ...
