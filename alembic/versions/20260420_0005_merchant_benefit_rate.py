"""add merchant benefit rate

Revision ID: 20260420_0005
Revises: 788539564a6c
Create Date: 2026-04-20 12:00:00
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260420_0005"
down_revision = "788539564a6c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "merchants",
        sa.Column("benefit_rate", sa.Numeric(12, 8), server_default="0", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("merchants", "benefit_rate")
