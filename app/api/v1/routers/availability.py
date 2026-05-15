import calendar
import re
import uuid
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.availability import RoomAvailability
from app.models.room import RoomCategory
from app.models.sanatorium import Sanatorium, SanatoriumStatus

router = APIRouter(prefix="/availability", tags=["availability"])

_MONTH_RE = re.compile(r"^(\d{4})-(0[1-9]|1[0-2])$")


def _parse_month(value: str) -> tuple[date, date]:
    match = _MONTH_RE.match(value)
    if match is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="month must be in YYYY-MM format",
        )
    year, month = int(match.group(1)), int(match.group(2))
    first = date(year, month, 1)
    last_day = calendar.monthrange(year, month)[1]
    last = date(year, month, last_day)
    return first, last


@router.get("")
async def get_availability(
    sanatorium_id: uuid.UUID = Query(...),
    month: str = Query(..., description="YYYY-MM"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    first, last = _parse_month(month)

    sanatorium = (await db.execute(
        select(Sanatorium).where(
            Sanatorium.id == sanatorium_id,
            Sanatorium.status == SanatoriumStatus.APPROVED,
        )
    )).scalar_one_or_none()
    if sanatorium is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sanatorium not found",
        )

    # Sum available units per date across all active rooms of this sanatorium.
    stmt = (
        select(
            RoomAvailability.date,
            func.sum(RoomAvailability.units_available).label("rooms_left"),
        )
        .join(RoomCategory, RoomAvailability.room_category_id == RoomCategory.id)
        .where(
            RoomCategory.sanatorium_id == sanatorium_id,
            RoomCategory.is_active.is_(True),
            RoomAvailability.date >= first,
            RoomAvailability.date <= last,
        )
        .group_by(RoomAvailability.date)
    )
    rows = {row.date: int(row.rooms_left) for row in (await db.execute(stmt)).all()}

    dates: dict[str, dict] = {}
    current = first
    while current <= last:
        rooms_left = rows.get(current)
        if rooms_left is None:
            # No availability entry → not bookable that day
            dates[current.isoformat()] = {"available": False}
        elif rooms_left <= 0:
            dates[current.isoformat()] = {"available": False, "rooms_left": 0}
        else:
            dates[current.isoformat()] = {"available": True, "rooms_left": rooms_left}
        current += timedelta(days=1)

    return {"dates": dates}
