"""commissions, discount tiers, drop users.sanatorium_id

Revision ID: b8d7e2f4a1c3
Revises: c5e9d3f6b2a4
Create Date: 2026-05-17 00:00:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b8d7e2f4a1c3"
down_revision: Union[str, None] = "c5e9d3f6b2a4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- migrate users.sanatorium_id → sanatoriums.admin_user_id (best-effort) ---
    op.execute(
        """
        UPDATE sanatoriums s
        SET admin_user_id = u.id
        FROM users u
        WHERE u.sanatorium_id = s.id
          AND s.admin_user_id IS NULL
        """
    )

    op.drop_constraint("fk_users_sanatorium_id", "users", type_="foreignkey")
    op.drop_index(op.f("ix_users_sanatorium_id"), table_name="users")
    op.drop_column("users", "sanatorium_id")

    # --- sanatoriums: commission + agent discount tiers ---
    op.add_column(
        "sanatoriums",
        sa.Column(
            "platform_commission_percent",
            sa.Numeric(5, 2),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "sanatoriums",
        sa.Column(
            "b2b_commission_percent",
            sa.Numeric(5, 2),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "sanatoriums",
        sa.Column(
            "agent_discount_tiers",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
    )

    # --- bookings: commission snapshot (single, based on is_b2b) ---
    op.add_column(
        "bookings",
        sa.Column("commission_snapshot", sa.Numeric(12, 2), nullable=True),
    )
    op.add_column(
        "bookings",
        sa.Column("commission_percent_snapshot", sa.Numeric(5, 2), nullable=True),
    )
    op.add_column(
        "bookings",
        sa.Column(
            "agent_discount_percent_snapshot", sa.Numeric(5, 2), nullable=True
        ),
    )

    # --- payments: index provider_payment_id ---
    op.create_index(
        op.f("ix_payments_provider_payment_id"),
        "payments",
        ["provider_payment_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_payments_provider_payment_id"), table_name="payments"
    )

    op.drop_column("bookings", "agent_discount_percent_snapshot")
    op.drop_column("bookings", "commission_percent_snapshot")
    op.drop_column("bookings", "commission_snapshot")

    op.drop_column("sanatoriums", "agent_discount_tiers")
    op.drop_column("sanatoriums", "b2b_commission_percent")
    op.drop_column("sanatoriums", "platform_commission_percent")

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
