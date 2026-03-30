"""initial schema

Revision ID: 20260331_0001
Revises:
Create Date: 2026-03-31 00:00:01
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260331_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "system_config",
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("value", sa.String(length=255), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )
    op.create_table(
        "merchants",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("merchant_name", sa.String(length=255), nullable=False),
        sa.Column("tg_chat_id", sa.BigInteger(), nullable=False),
        sa.Column("balance", sa.BigInteger(), server_default="0", nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("merchant_name"),
        sa.UniqueConstraint("tg_chat_id"),
    )
    op.create_table(
        "transactions",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("merchant_id", sa.Integer(), nullable=False),
        sa.Column("tx_type", sa.String(length=32), nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("fee", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["merchant_id"], ["merchants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_transactions_merchant_id", "transactions", ["merchant_id"], unique=False)
    op.create_index("ix_transactions_created_at", "transactions", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_transactions_created_at", table_name="transactions")
    op.drop_index("ix_transactions_merchant_id", table_name="transactions")
    op.drop_table("transactions")
    op.drop_table("merchants")
    op.drop_table("system_config")
