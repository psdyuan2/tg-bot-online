from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from bot.db.base import Base
from bot.db.models import Merchant
from bot.services.ledger import MerchantService, merchant_display


@pytest.mark.asyncio
async def test_get_by_identifier_resolves_merchant_code_case_insensitive() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        session.add(
            Merchant(
                merchant_name="g_ab12cd34",
                merchant_code="ab12cd34",
                tg_chat_id=-100,
                balance=0,
                benefit_balance=Decimal("0"),
            )
        )
        await session.commit()

    async with session_factory() as session:
        m = await MerchantService.get_by_identifier(session, "AB12CD34")
        assert m is not None
        assert m.merchant_code == "ab12cd34"


def test_merchant_display_prefers_code() -> None:
    m = Merchant(
        merchant_name="g_x",
        merchant_code="abc12345",
        tg_chat_id=1,
        balance=0,
        benefit_balance=Decimal("0"),
    )
    assert merchant_display(m) == "abc12345"

    m2 = Merchant(
        merchant_name="legacy",
        merchant_code=None,
        tg_chat_id=2,
        balance=0,
        benefit_balance=Decimal("0"),
    )
    assert merchant_display(m2) == "legacy"
