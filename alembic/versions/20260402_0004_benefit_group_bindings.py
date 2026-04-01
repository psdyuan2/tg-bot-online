"""benefit group to merchant bindings

Revision ID: 20260402_0004
Revises: 20260401_0003
Create Date: 2026-04-02 12:00:00
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260402_0004"
down_revision = "20260401_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "benefit_group_bindings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("benefit_chat_id", sa.BigInteger(), nullable=False),
        sa.Column("merchant_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["merchant_id"], ["merchants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("benefit_chat_id", "merchant_id", name="uq_benefit_chat_merchant"),
    )
    op.create_index("ix_benefit_group_bindings_benefit_chat_id", "benefit_group_bindings", ["benefit_chat_id"])
    op.create_index("ix_benefit_group_bindings_merchant_id", "benefit_group_bindings", ["merchant_id"])


def downgrade() -> None:
    op.drop_index("ix_benefit_group_bindings_merchant_id", table_name="benefit_group_bindings")
    op.drop_index("ix_benefit_group_bindings_benefit_chat_id", table_name="benefit_group_bindings")
    op.drop_table("benefit_group_bindings")
