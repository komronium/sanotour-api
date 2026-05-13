import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.booking import BookingStatus, BookingType
from app.schemas.extra_bed import BookingExtraBedRead, ExtraBedItem


class BookingCreate(BaseModel):
    room_category_id: uuid.UUID | None = None
    program_id: uuid.UUID | None = None
    check_in: date
    check_out: date | None = None
    guests: int = Field(default=1, ge=1)
    extra_beds: list[ExtraBedItem] = Field(default_factory=list)

    @model_validator(mode="after")
    def _exactly_one_target(self):
        if (self.room_category_id is None) == (self.program_id is None):
            raise ValueError("Provide exactly one of room_category_id or program_id")
        return self


class BookingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    user_id: uuid.UUID | None
    room_category_id: uuid.UUID | None
    program_id: uuid.UUID | None
    booking_type: BookingType
    check_in: date
    check_out: date
    guests: int
    status: BookingStatus
    final_price: Decimal
    currency: str
    extra_beds: list[BookingExtraBedRead] = []
    created_at: datetime


class BookingList(BaseModel):
    items: list[BookingRead]
    total: int
    limit: int
    offset: int
