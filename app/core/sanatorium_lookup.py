from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.booking import Booking
from app.models.program import TreatmentProgram
from app.models.room import Room
from app.models.sanatorium import Sanatorium


async def sanatorium_name_for_booking(
    db: AsyncSession, booking: Booking
) -> str | None:
    """Resolve the sanatorium name behind a booking (via room or program)."""
    if booking.room_id is not None:
        return (
            await db.execute(
                select(Sanatorium.name)
                .join(Room, Room.sanatorium_id == Sanatorium.id)
                .where(Room.id == booking.room_id)
            )
        ).scalar_one_or_none()
    if booking.program_id is not None:
        return (
            await db.execute(
                select(Sanatorium.name)
                .join(
                    TreatmentProgram,
                    TreatmentProgram.sanatorium_id == Sanatorium.id,
                )
                .where(TreatmentProgram.id == booking.program_id)
            )
        ).scalar_one_or_none()
    return None
