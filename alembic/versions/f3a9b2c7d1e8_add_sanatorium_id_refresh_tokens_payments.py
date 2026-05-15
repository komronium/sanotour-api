"""add sanatorium_id to users, refresh_tokens, payments

Revision ID: f3a9b2c7d1e8
Revises: 083479e3cafa
Create Date: 2026-05-15 00:00:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f3a9b2c7d1e8"
down_revision: Union[str, None] = "083479e3cafa"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- users.sanatorium_id ---
    op.add_column(
        "users",
        sa.Column("sanatorium_id", sa.Uuid(), nullable=True),
    )
    op.create_index(
        op.f("ix_users_sanatorium_id"),
        "users",
        ["sanatorium_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_users_sanatorium_id",
        "users",
        "sanatoriums",
        ["sanatorium_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # --- refresh_tokens ---
    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("revoked", sa.Boolean(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_refresh_tokens_user_id"),
        "refresh_tokens",
        ["user_id"],
        unique=False,
    )

    # --- payments ---
    op.create_table(
        "payments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("booking_id", sa.Uuid(), nullable=False),
        sa.Column(
            "method",
            sa.Enum("payme", "click", "cash", name="paymentmethod", native_enum=False, length=20),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum("pending", "paid", "failed", "cancelled", name="paymentstatus", native_enum=False, length=20),
            nullable=False,
        ),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("merchant_trans_id", sa.String(64), nullable=True),
        sa.Column("provider_payment_id", sa.String(120), nullable=True),
        sa.Column(
            "raw_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["booking_id"], ["bookings.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_payments_booking_id"),
        "payments",
        ["booking_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_payments_merchant_trans_id"),
        "payments",
        ["merchant_trans_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_payments_status"),
        "payments",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_payments_status"), table_name="payments")
    op.drop_index(op.f("ix_payments_merchant_trans_id"), table_name="payments")
    op.drop_index(op.f("ix_payments_booking_id"), table_name="payments")
    op.drop_table("payments")

    op.drop_index(op.f("ix_refresh_tokens_user_id"), table_name="refresh_tokens")
    op.drop_table("refresh_tokens")

    op.drop_constraint("fk_users_sanatorium_id", "users", type_="foreignkey")
    op.drop_index(op.f("ix_users_sanatorium_id"), table_name="users")
    op.drop_column("users", "sanatorium_id")
