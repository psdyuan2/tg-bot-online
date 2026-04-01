"""merchant benefit_balance USDT cumulative

Revision ID: 20260401_0003
Revises: 20260401_0002
Create Date: 2026-04-01 12:00:00
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260401_0003"
down_revision = "20260401_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "merchants",
        sa.Column("benefit_balance", sa.Numeric(24, 8), server_default="0", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("merchants", "benefit_balance")
