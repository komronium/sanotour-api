import uuid
from decimal import Decimal

from pydantic import BaseModel


class TopSanatoriumStat(BaseModel):
    id: uuid.UUID
    name: str
    booking_count: int
    revenue: Decimal


class MonthlyRevenue(BaseModel):
    month: str
    revenue: Decimal


class AdminStats(BaseModel):
    total_bookings: int
    bookings_this_month: int
    total_revenue_usd: Decimal
    revenue_this_month_usd: Decimal
    total_users: int
    new_users_this_month: int
    total_sanatoriums: int
    pending_sanatoriums: int
    top_sanatoriums: list[TopSanatoriumStat]
    monthly_revenue: list[MonthlyRevenue]
