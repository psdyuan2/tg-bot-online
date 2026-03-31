"""add merchant_code for short merchant identifiers

Revision ID: 20260401_0002
Revises: 20260331_0001
Create Date: 2026-04-01 00:00:01
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260401_0002"
down_revision = "20260331_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "merchants",
        sa.Column("merchant_code", sa.String(length=32), nullable=True),
    )
    op.create_index("ix_merchants_merchant_code", "merchants", ["merchant_code"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_merchants_merchant_code", table_name="merchants")
    op.drop_column("merchants", "merchant_code")
