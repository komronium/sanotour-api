"""add CHECK constraint: bookings.room_id XOR program_id

Revision ID: f9c2a3b8d4e7
Revises: e4f7a9d6c2b1
Create Date: 2026-05-17 00:00:01.000000

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "f9c2a3b8d4e7"
down_revision: Union[str, None] = "e4f7a9d6c2b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_bookings_room_xor_program",
        "bookings",
        "(room_id IS NULL) <> (program_id IS NULL)",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_bookings_room_xor_program", "bookings", type_="check"
    )
