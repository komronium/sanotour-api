from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.notifier import BookingNotifier
from app.core.pricing import calculate_stay_total
from app.core.utils import date_range
from app.models.availability import RoomAvailability
from app.models.booking import Booking, BookingStatus, BookingType
from app.models.extra_bed import BookingExtraBed, ExtraBedConfig
from app.models.notification import Notification
from app.models.room import Room
from app.models.sanatorium import Sanatorium, SanatoriumStatus
from app.models.user import User, UserRole
from app.schemas.booking import BookingCreate
from app.services.booking_pricing_policy import BookingPricingPolicy
from app.services.email_service import BookingEmailContext

_CENTS = Decimal("0.01")  # noqa: F841 — kept for symmetry with session flow


class RoomBookingFlow:
    booking_type = BookingType.ROOM

    def __init__(
        self,
        db: AsyncSession,
        pricing: BookingPricingPolicy,
        notifier: BookingNotifier,
    ) -> None:
        self.db = db
        self.pricing = pricing
        self.notifier = notifier

    def matches(self, payload: BookingCreate) -> bool:
        return payload.program_id is None

    async def create(self, payload: BookingCreate, user: User) -> Booking:
        if payload.check_out is None or payload.check_out <= payload.check_in:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="check_out must be after check_in",
            )

        nights = (payload.check_out - payload.check_in).days
        all_dates = date_range(payload.check_in, payload.check_out)

        room = await self._lock_room(payload.room_id)
        sanatorium = await self._approved_sanatorium(room.sanatorium_id)
        self._validate_room_constraints(room, payload, nights)

        avail_rows = await self._lock_availability(room.id, list(all_dates), nights)
        for row in avail_rows:
            row.units_available -= 1

        is_b2b = user.role == UserRole.AGENT
        base_total = calculate_stay_total(room, list(all_dates), room.price_periods)
        extra_bed_records = await self._build_extra_beds(
            payload, room.sanatorium_id, nights
        )

        pricing = await self.pricing.apply(
            base_total=base_total,
            sanatorium=sanatorium,
            user=user,
            is_b2b=is_b2b,
            payload=payload,
        )

        booking = Booking(
            user_id=user.id,
            room_id=room.id,
            booking_type=BookingType.ROOM,
            check_in=payload.check_in,
            check_out=payload.check_out,
            guests=payload.guests,
            status=BookingStatus.CONFIRMED,
            final_price=pricing.final_price,
            currency=room.base_currency,
            is_b2b=is_b2b,
            b2b_client_price=pricing.b2b_client_price,
            guest_details=[g.model_dump() for g in payload.guest_details],
            commission_snapshot=pricing.commission_amount,
            commission_percent_snapshot=pricing.commission_percent,
            agent_discount_percent_snapshot=(
                pricing.agent_discount_percent if is_b2b else None
            ),
        )
        self.db.add(booking)
        await self.db.flush()
        for eb in extra_bed_records:
            eb.booking_id = booking.id
            self.db.add(eb)
        self.db.add(
            Notification(
                booking_id=booking.id, type="booking_created", channel="email"
            )
        )
        await self.db.commit()

        await self._send_received_email(booking, user, sanatorium.name)
        return await self._load(booking.id)

    async def _lock_room(self, room_id) -> Room:
        room = (
            await self.db.execute(
                select(Room)
                .where(Room.id == room_id)
                .options(selectinload(Room.price_periods))
                .with_for_update(of=Room)
            )
        ).scalar_one_or_none()
        if room is None or not room.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Room not found"
            )
        return room

    async def _approved_sanatorium(self, sanatorium_id) -> Sanatorium:
        sanatorium = (
            await self.db.execute(
                select(Sanatorium).where(Sanatorium.id == sanatorium_id)
            )
        ).scalar_one_or_none()
        if sanatorium is None or sanatorium.status != SanatoriumStatus.APPROVED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Sanatorium is not available for booking",
            )
        return sanatorium

    @staticmethod
    def _validate_room_constraints(
        room: Room, payload: BookingCreate, nights: int
    ) -> None:
        if nights < room.min_nights:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Minimum stay is {room.min_nights} night(s)",
            )
        if room.capacity < payload.guests:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Room capacity is {room.capacity} guest(s)",
            )

    async def _lock_availability(
        self, room_id, dates: list, nights: int
    ) -> list[RoomAvailability]:
        rows = list(
            (
                await self.db.execute(
                    select(RoomAvailability)
                    .where(
                        RoomAvailability.room_id == room_id,
                        RoomAvailability.date.in_(dates),
                    )
                    .with_for_update()
                )
            ).scalars()
        )
        if len(rows) != nights:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Not all dates are available",
            )
        for row in rows:
            if row.units_available < 1:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"No units available on {row.date}",
                )
        return rows

    async def _build_extra_beds(
        self, payload: BookingCreate, sanatorium_id, nights: int
    ) -> list[BookingExtraBed]:
        records: list[BookingExtraBed] = []
        for item in payload.extra_beds:
            config = (
                await self.db.execute(
                    select(ExtraBedConfig).where(ExtraBedConfig.id == item.config_id)
                )
            ).scalar_one_or_none()
            if config is None or not config.is_active:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Extra bed config {item.config_id} not found",
                )
            if config.sanatorium_id != sanatorium_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Extra bed config does not belong to this sanatorium",
                )
            if item.count > config.max_count:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Maximum {config.max_count} of this bed type allowed",
                )
            total = (config.price_per_night * item.count * nights).quantize(
                _CENTS, ROUND_HALF_UP
            )
            records.append(
                BookingExtraBed(
                    config_id=config.id,
                    name_snapshot=config.name,
                    price_per_night_snapshot=config.price_per_night,
                    currency=config.currency,
                    count=item.count,
                    total_price=total,
                )
            )
        return records

    async def _load(self, booking_id) -> Booking:
        stmt = (
            select(Booking)
            .options(selectinload(Booking.extra_beds))
            .where(Booking.id == booking_id)
        )
        return (await self.db.execute(stmt)).scalar_one()

    async def _send_received_email(
        self, booking: Booking, user: User, sanatorium_name: str
    ) -> None:
        if not user.email:
            return
        ctx = BookingEmailContext(
            booking_code=booking.code,
            sanatorium_name=sanatorium_name,
            check_in=booking.check_in,
            check_out=booking.check_out,
            guest_name=user.full_name or user.email,
            total_price=booking.final_price,
            currency=booking.currency,
        )
        self.notifier.booking_received(to=user.email, ctx=ctx)
