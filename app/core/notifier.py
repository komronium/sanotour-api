from __future__ import annotations

from typing import Protocol

from app.services.email_service import (
    BookingEmailContext,
    send_booking_cancelled,
    send_booking_confirmed,
    send_booking_received,
)


class BookingNotifier(Protocol):
    def booking_received(self, *, to: str, ctx: BookingEmailContext) -> None: ...
    def booking_confirmed(self, *, to: str, ctx: BookingEmailContext) -> None: ...
    def booking_cancelled(self, *, to: str, ctx: BookingEmailContext) -> None: ...


class EmailBookingNotifier:
    """Default Notifier — delegates to the email_service module."""

    def booking_received(self, *, to: str, ctx: BookingEmailContext) -> None:
        send_booking_received(to=to, ctx=ctx)

    def booking_confirmed(self, *, to: str, ctx: BookingEmailContext) -> None:
        send_booking_confirmed(to=to, ctx=ctx)

    def booking_cancelled(self, *, to: str, ctx: BookingEmailContext) -> None:
        send_booking_cancelled(to=to, ctx=ctx)


def get_booking_notifier() -> BookingNotifier:
    return EmailBookingNotifier()
