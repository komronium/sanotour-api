import uuid
from collections.abc import Sequence
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from fastapi import Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.pricing import calculate_stay_total
from app.core.utils import date_range
from app.models.amenity import TreatmentProgram
from app.models.availability import RoomAvailability
from app.models.booking import Booking, BookingStatus, BookingType
from app.models.extra_bed import BookingExtraBed, ExtraBedConfig
from app.models.notification import Notification
from app.models.room import RoomCategory
from app.models.sanatorium import Sanatorium, SanatoriumStatus
from app.models.user import User, UserRole
from app.schemas.booking import BookingCreate
from app.services.email_service import (
    BookingEmailContext,
    send_booking_cancelled,
    send_booking_received,
)

_CANCELLABLE = {BookingStatus.PENDING, BookingStatus.CONFIRMED}
_TWO = Decimal("0.01")


class BookingService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── create ─────────────────────────────────────────────────────────────

    async def create(self, payload: BookingCreate, user: User) -> Booking:
        today = date.today()
        if payload.check_in < today:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="check_in must be today or in the future",
            )

        if payload.program_id is not None:
            return await self._create_session(payload, user)

        if payload.check_out is None or payload.check_out <= payload.check_in:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="check_out must be after check_in",
            )

        nights = (payload.check_out - payload.check_in).days
        all_dates = date_range(payload.check_in, payload.check_out)

        room = (
            await self.db.execute(
                select(RoomCategory)
                .where(RoomCategory.id == payload.room_category_id)
                .options(selectinload(RoomCategory.price_periods))
                .with_for_update(of=RoomCategory)
            )
        ).scalar_one_or_none()

        if room is None or not room.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Room not found"
            )

        sanatorium = (
            await self.db.execute(
                select(Sanatorium).where(Sanatorium.id == room.sanatorium_id)
            )
        ).scalar_one_or_none()
        if sanatorium is None or sanatorium.status != SanatoriumStatus.APPROVED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Sanatorium is not available for booking",
            )

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

        avail_rows = list(
            (
                await self.db.execute(
                    select(RoomAvailability)
                    .where(
                        RoomAvailability.room_category_id == room.id,
                        RoomAvailability.date.in_(all_dates),
                    )
                    .with_for_update()
                )
            ).scalars()
        )

        if len(avail_rows) != nights:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Not all dates are available",
            )

        for row in avail_rows:
            if row.units_available < 1:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"No units available on {row.date}",
                )

        for row in avail_rows:
            row.units_available -= 1

        # Total room price: sum of per-night prices (weekday/weekend + markup + discount)
        # Seasonal `price_periods` (if any) override base prices on covered dates.
        room_total = calculate_stay_total(room, list(all_dates), room.price_periods)

        # Validate and price extra beds
        extra_bed_records: list[BookingExtraBed] = []
        for item in payload.extra_beds:
            config = (await self.db.execute(
                select(ExtraBedConfig).where(ExtraBedConfig.id == item.config_id)
            )).scalar_one_or_none()

            if config is None or not config.is_active:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Extra bed config {item.config_id} not found",
                )
            if config.sanatorium_id != room.sanatorium_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Extra bed config does not belong to this sanatorium",
                )
            if item.count > config.max_count:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Maximum {config.max_count} of this bed type allowed",
                )

            bed_total = (config.price_per_night * item.count * nights).quantize(_TWO, ROUND_HALF_UP)
            extra_bed_records.append(
                BookingExtraBed(
                    config_id=config.id,
                    name_snapshot=config.name,
                    price_per_night_snapshot=config.price_per_night,
                    currency=config.currency,
                    count=item.count,
                    total_price=bed_total,
                )
            )

        booking = Booking(
            user_id=user.id,
            room_category_id=room.id,
            booking_type=BookingType.ROOM,
            check_in=payload.check_in,
            check_out=payload.check_out,
            guests=payload.guests,
            status=BookingStatus.CONFIRMED,
            final_price=room_total,
            currency=room.base_currency,
        )
        self.db.add(booking)
        await self.db.flush()

        for eb in extra_bed_records:
            eb.booking_id = booking.id
            self.db.add(eb)

        self.db.add(Notification(booking_id=booking.id, type="booking_created", channel="email"))
        await self.db.commit()
        await self._send_booking_email(
            booking, user, sanatorium.name, kind="received"
        )
        return await self._load_booking(booking.id)  # type: ignore[return-value]

    async def _create_session(self, payload: BookingCreate, user: User) -> Booking:
        program = (
            await self.db.execute(
                select(TreatmentProgram).where(TreatmentProgram.id == payload.program_id)
            )
        ).scalar_one_or_none()

        if program is None or not program.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Program not found"
            )
        if program.price is None or program.currency is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Program is not bookable (no price set)",
            )

        sanatorium = (
            await self.db.execute(
                select(Sanatorium).where(Sanatorium.id == program.sanatorium_id)
            )
        ).scalar_one_or_none()
        if sanatorium is None or sanatorium.status != SanatoriumStatus.APPROVED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Sanatorium is not available for booking",
            )

        if program.group_size_max is not None and payload.guests > program.group_size_max:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Maximum {program.group_size_max} participant(s) per session",
            )

        check_out = payload.check_out or payload.check_in
        if check_out < payload.check_in:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="check_out must be on or after check_in",
            )

        session_total = (program.price * payload.guests).quantize(_TWO, ROUND_HALF_UP)

        booking = Booking(
            user_id=user.id,
            program_id=program.id,
            booking_type=BookingType.SESSION,
            check_in=payload.check_in,
            check_out=check_out,
            guests=payload.guests,
            status=BookingStatus.CONFIRMED,
            final_price=session_total,
            currency=program.currency,
        )
        self.db.add(booking)
        await self.db.flush()

        self.db.add(Notification(booking_id=booking.id, type="booking_created", channel="email"))
        await self.db.commit()
        await self._send_booking_email(
            booking, user, sanatorium.name, kind="received"
        )
        return await self._load_booking(booking.id)  # type: ignore[return-value]

    # ── list / get ─────────────────────────────────────────────────────────

    async def list_for_user(
        self,
        user: User,
        *,
        limit: int,
        offset: int,
    ) -> tuple[Sequence[Booking], int]:
        base = self._visibility_filter(select(Booking), user)

        total = (
            await self.db.execute(select(func.count()).select_from(base.subquery()))
        ).scalar_one()

        stmt = (
            self._visibility_filter(
                select(Booking).options(selectinload(Booking.extra_beds)), user
            )
            .order_by(Booking.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = (await self.db.execute(stmt)).scalars().all()
        return rows, total

    async def get_by_id(self, booking_id: uuid.UUID) -> Booking | None:
        return await self._load_booking(booking_id)

    async def get_visible(self, booking_id: uuid.UUID, user: User) -> Booking | None:
        stmt = self._visibility_filter(
            select(Booking)
            .options(selectinload(Booking.extra_beds))
            .where(Booking.id == booking_id),
            user,
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def _load_booking(self, booking_id: uuid.UUID) -> Booking | None:
        stmt = (
            select(Booking)
            .options(selectinload(Booking.extra_beds))
            .where(Booking.id == booking_id)
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    def _visibility_filter(self, stmt, user: User):
        if user.role == UserRole.SUPER_ADMIN:
            return stmt
        if user.role == UserRole.ADMIN:
            room_sub = (
                select(RoomCategory.id)
                .join(Sanatorium, RoomCategory.sanatorium_id == Sanatorium.id)
                .where(Sanatorium.admin_user_id == user.id)
                .scalar_subquery()
            )
            program_sub = (
                select(TreatmentProgram.id)
                .join(Sanatorium, TreatmentProgram.sanatorium_id == Sanatorium.id)
                .where(Sanatorium.admin_user_id == user.id)
                .scalar_subquery()
            )
            return stmt.where(
                (Booking.room_category_id.in_(room_sub))
                | (Booking.program_id.in_(program_sub))
            )
        return stmt.where(Booking.user_id == user.id)

    # ── cancel ─────────────────────────────────────────────────────────────

    async def cancel(self, booking: Booking, user: User) -> Booking:
        self._assert_can_cancel(booking, user)

        if booking.booking_type == BookingType.ROOM and booking.room_category_id is not None:
            avail_rows = list(
                (
                    await self.db.execute(
                        select(RoomAvailability)
                        .where(
                            RoomAvailability.room_category_id == booking.room_category_id,
                            RoomAvailability.date >= booking.check_in,
                            RoomAvailability.date < booking.check_out,
                        )
                        .with_for_update()
                    )
                ).scalars()
            )

            for row in avail_rows:
                row.units_available = min(row.units_available + 1, row.units_total)

        booking.status = BookingStatus.CANCELLED
        self.db.add(Notification(booking_id=booking.id, type="booking_cancelled", channel="email"))
        await self.db.commit()
        sanatorium_name = await self._lookup_sanatorium_name(booking)
        if sanatorium_name is not None:
            await self._send_booking_email(
                booking, user, sanatorium_name, kind="cancelled"
            )
        return await self._load_booking(booking.id)  # type: ignore[return-value]

    async def _send_booking_email(
        self,
        booking: Booking,
        user: User,
        sanatorium_name: str,
        *,
        kind: str,
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
        if kind == "received":
            send_booking_received(to=user.email, ctx=ctx)
        elif kind == "cancelled":
            send_booking_cancelled(to=user.email, ctx=ctx)

    async def _lookup_sanatorium_name(self, booking: Booking) -> str | None:
        if booking.room_category_id is not None:
            row = (await self.db.execute(
                select(Sanatorium.name)
                .join(RoomCategory, RoomCategory.sanatorium_id == Sanatorium.id)
                .where(RoomCategory.id == booking.room_category_id)
            )).scalar_one_or_none()
            return row
        if booking.program_id is not None:
            row = (await self.db.execute(
                select(Sanatorium.name)
                .join(TreatmentProgram, TreatmentProgram.sanatorium_id == Sanatorium.id)
                .where(TreatmentProgram.id == booking.program_id)
            )).scalar_one_or_none()
            return row
        return None

    def _assert_can_cancel(self, booking: Booking, user: User) -> None:
        if booking.status not in _CANCELLABLE:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Booking cannot be cancelled (status: {booking.status})",
            )
        if user.role == UserRole.SUPER_ADMIN:
            return
        if user.role == UserRole.ADMIN:
            return
        if booking.user_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not allowed to cancel this booking",
            )


def get_booking_service(db: AsyncSession = Depends(get_db)) -> BookingService:
    return BookingService(db)
