import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.sanatorium import SanatoriumStatus
from app.schemas.common import Translations


class SanatoriumImageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    url: str
    order: int
    is_primary: bool
    caption: str | None
    created_at: datetime


class SanatoriumBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: Translations = Field(default_factory=Translations)
    city: str = Field(min_length=1, max_length=120)
    address: str = Field(min_length=1, max_length=500)
    lat: Decimal | None = Field(default=None, ge=-90, le=90)
    lng: Decimal | None = Field(default=None, ge=-180, le=180)
    stars: int = Field(ge=1, le=5)


class SanatoriumCreate(SanatoriumBase):
    slug: str | None = Field(default=None, max_length=255)
    admin_user_id: uuid.UUID | None = None


class SanatoriumUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    slug: str | None = Field(default=None, max_length=255)
    description: Translations | None = None
    city: str | None = Field(default=None, min_length=1, max_length=120)
    address: str | None = Field(default=None, min_length=1, max_length=500)
    lat: Decimal | None = Field(default=None, ge=-90, le=90)
    lng: Decimal | None = Field(default=None, ge=-180, le=180)
    stars: int | None = Field(default=None, ge=1, le=5)
    admin_user_id: uuid.UUID | None = None


class SanatoriumRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    description: Translations
    city: str
    address: str
    lat: Decimal | None
    lng: Decimal | None
    stars: int
    status: SanatoriumStatus
    admin_user_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
    images: list[SanatoriumImageRead] = Field(default_factory=list)


class SanatoriumList(BaseModel):
    items: list[SanatoriumRead]
    total: int
    limit: int
    offset: int
