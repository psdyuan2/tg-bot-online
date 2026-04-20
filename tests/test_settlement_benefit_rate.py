from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from bot.db.base import Base
from bot.db.models import Merchant
from bot.services.finance import MoneyService
from bot.services.ledger import LedgerService


@pytest.mark.asyncio
async def test_settle_uses_merchant_specific_benefit_rate() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        merchant = Merchant(
            merchant_name="zw",
            merchant_code="zw",
            tg_chat_id=-10001,
            balance=0,
            benefit_balance=Decimal("0"),
            benefit_rate=Decimal("0.01"),
        )
        session.add(merchant)
        await session.commit()
        await session.refresh(merchant)

        result, dividend_usdt = await LedgerService.settle(
            session,
            merchant,
            10_000,
            settle_fee_rate=Decimal("0.065"),
            default_u_rate=Decimal("100"),
        )

        assert result.net_amount_cents == 9_350
        assert dividend_usdt is not None
        assert dividend_usdt == Decimal("0.94") / Decimal("100.5")
        assert Decimal(merchant.benefit_balance) == Decimal(MoneyService.format_usdt_balance(dividend_usdt))

    await engine.dispose()


@pytest.mark.asyncio
async def test_settle_skips_dividend_when_merchant_benefit_rate_is_zero() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        merchant = Merchant(
            merchant_name="zero",
            merchant_code="zero",
            tg_chat_id=-10002,
            balance=0,
            benefit_balance=Decimal("0"),
            benefit_rate=Decimal("0"),
        )
        session.add(merchant)
        await session.commit()
        await session.refresh(merchant)

        result, dividend_usdt = await LedgerService.settle(
            session,
            merchant,
            10_000,
            settle_fee_rate=Decimal("0.065"),
            default_u_rate=Decimal("100"),
        )

        assert result.net_amount_cents == 9_350
        assert dividend_usdt is None
        assert Decimal(merchant.benefit_balance) == Decimal("0")

    await engine.dispose()
