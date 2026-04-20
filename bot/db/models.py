from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.db.base import Base


class SystemConfig(Base):
    __tablename__ = "system_config"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(String(255), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class Merchant(Base):
    __tablename__ = "merchants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    merchant_name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    merchant_code: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
        unique=True,
        index=True,
    )
    tg_chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False, unique=True)
    balance: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")
    benefit_balance: Mapped[Decimal] = mapped_column(
        Numeric(24, 8),
        nullable=False,
        default=Decimal("0"),
        server_default="0",
    )
    benefit_rate: Mapped[Decimal] = mapped_column(
        Numeric(12, 8),
        nullable=False,
        default=Decimal("0"),
        server_default="0",
    )

    transactions: Mapped[list[Transaction]] = relationship(
        back_populates="merchant",
        cascade="all, delete-orphan",
    )
    benefit_bindings: Mapped[list[BenefitGroupBinding]] = relationship(
        back_populates="merchant",
        cascade="all, delete-orphan",
    )


class BenefitGroupBinding(Base):
    __tablename__ = "benefit_group_bindings"
    __table_args__ = (UniqueConstraint("benefit_chat_id", "merchant_id", name="uq_benefit_chat_merchant"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    benefit_chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    merchant_id: Mapped[int] = mapped_column(
        ForeignKey("merchants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    merchant: Mapped[Merchant] = relationship(back_populates="benefit_bindings")


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    merchant_id: Mapped[int] = mapped_column(
        ForeignKey("merchants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tx_type: Mapped[str] = mapped_column(String(32), nullable=False)
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    fee: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")
    is_reported: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    merchant: Mapped[Merchant] = relationship(back_populates="transactions")
