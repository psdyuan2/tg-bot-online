from __future__ import annotations

import secrets
import string
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from decimal import Decimal

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import Merchant, SystemConfig, Transaction
from bot.services.finance import FinanceService, PayoutResult, SettlementResult


U_RATE_KEY = "U_RATE"


def merchant_display(merchant: Merchant) -> str:
    return merchant.merchant_code or merchant.merchant_name


@dataclass(frozen=True, slots=True)
class DailyReport:
    merchant: Merchant
    settle_count: int
    settle_amount_cents: int
    settle_fee_cents: int
    payout_count: int
    payout_amount_cents: int
    payout_fee_cents: int


class SystemConfigService:
    @staticmethod
    async def get_u_rate(session: AsyncSession, default_rate: Decimal) -> Decimal:
        record = await session.get(SystemConfig, U_RATE_KEY)
        if record is None:
            record = SystemConfig(key=U_RATE_KEY, value=str(default_rate))
            session.add(record)
            await session.commit()
            return default_rate
        return Decimal(record.value)

    @staticmethod
    async def set_u_rate(session: AsyncSession, rate: Decimal) -> Decimal:
        record = await session.get(SystemConfig, U_RATE_KEY)
        if record is None:
            record = SystemConfig(key=U_RATE_KEY, value=str(rate))
            session.add(record)
        else:
            record.value = str(rate)
        await session.commit()
        return rate


class MerchantService:
    @staticmethod
    def _generate_code_candidate(length: int = 8) -> str:
        alphabet = string.ascii_lowercase + string.digits
        return "".join(secrets.choice(alphabet) for _ in range(length))

    @staticmethod
    async def create_unique_merchant_code(session: AsyncSession) -> str:
        for _ in range(128):
            code = MerchantService._generate_code_candidate()
            result = await session.execute(
                select(Merchant.id).where(Merchant.merchant_code == code).limit(1)
            )
            if result.scalar_one_or_none() is None:
                return code
        raise RuntimeError("无法生成唯一商户标识，请稍后重试")

    @staticmethod
    async def register_merchant_code_for_chat(
        session: AsyncSession,
        chat_id: int,
    ) -> str:
        merchant = await MerchantService.get_by_chat_id(session, chat_id)
        if merchant is not None and merchant.merchant_code is not None:
            return f"本群已设置商户标识: {merchant.merchant_code}，无需重复创建。"

        if merchant is not None:
            code = await MerchantService.create_unique_merchant_code(session)
            merchant.merchant_code = code
            await session.commit()
            await session.refresh(merchant)
            return f"已为本群设置商户标识: {code}"

        code = await MerchantService.create_unique_merchant_code(session)
        merchant_name = f"g_{code}"[:255]
        session.add(
            Merchant(
                merchant_name=merchant_name,
                merchant_code=code,
                tg_chat_id=chat_id,
                balance=0,
            )
        )
        await session.commit()
        return f"已为本群创建商户并分配标识: {code}"

    @staticmethod
    def merchant_identifier_query(identifier: str) -> Select[tuple[Merchant]]:
        value = identifier.strip()
        lowered = value.lower()
        conditions = [
            Merchant.merchant_name == value,
            Merchant.merchant_code == lowered,
        ]
        if value.isdigit():
            conditions.append(Merchant.id == int(value))
        return select(Merchant).where(or_(*conditions))

    @staticmethod
    async def get_by_identifier(session: AsyncSession, identifier: str) -> Merchant | None:
        result = await session.execute(MerchantService.merchant_identifier_query(identifier))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_chat_id(session: AsyncSession, chat_id: int) -> Merchant | None:
        result = await session.execute(select(Merchant).where(Merchant.tg_chat_id == chat_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_chat_id_for_update(session: AsyncSession, chat_id: int) -> Merchant | None:
        result = await session.execute(
            select(Merchant).where(Merchant.tg_chat_id == chat_id).with_for_update()
        )
        return result.scalar_one_or_none()


class LedgerService:
    @staticmethod
    async def settle(
        session: AsyncSession,
        merchant: Merchant,
        gross_amount_cents: int,
    ) -> SettlementResult:
        result = FinanceService.calculate_settlement(gross_amount_cents)
        merchant.balance += result.net_amount_cents
        session.add(
            Transaction(
                merchant_id=merchant.id,
                tx_type="settle",
                amount=result.gross_amount_cents,
                fee=result.fee_cents,
            )
        )
        await session.commit()
        await session.refresh(merchant)
        return result

    @staticmethod
    async def payout(
        session: AsyncSession,
        merchant: Merchant,
        principal_cents: int,
    ) -> PayoutResult:
        result = FinanceService.calculate_payout(principal_cents)
        FinanceService.assert_sufficient_balance(merchant.balance, result.debit_cents)
        merchant.balance -= result.debit_cents
        session.add(
            Transaction(
                merchant_id=merchant.id,
                tx_type="payout",
                amount=result.principal_cents,
                fee=result.fee_cents,
            )
        )
        await session.commit()
        await session.refresh(merchant)
        return result


class ReportService:
    @staticmethod
    async def build_daily_report(
        session: AsyncSession,
        merchant: Merchant,
        now: datetime | None = None,
    ) -> DailyReport:
        current_time = now or datetime.now(timezone.utc)
        day_start = datetime.combine(current_time.date(), time.min, tzinfo=current_time.tzinfo)
        day_end = day_start + timedelta(days=1)

        rows = await session.execute(
            select(
                Transaction.tx_type,
                func.count(Transaction.id),
                func.coalesce(func.sum(Transaction.amount), 0),
                func.coalesce(func.sum(Transaction.fee), 0),
            )
            .where(Transaction.merchant_id == merchant.id)
            .where(Transaction.created_at >= day_start)
            .where(Transaction.created_at < day_end)
            .group_by(Transaction.tx_type)
        )
        summary = {tx_type: (count, amount, fee) for tx_type, count, amount, fee in rows.all()}
        settle_count, settle_amount, settle_fee = summary.get("settle", (0, 0, 0))
        payout_count, payout_amount, payout_fee = summary.get("payout", (0, 0, 0))
        return DailyReport(
            merchant=merchant,
            settle_count=int(settle_count),
            settle_amount_cents=int(settle_amount),
            settle_fee_cents=int(settle_fee),
            payout_count=int(payout_count),
            payout_amount_cents=int(payout_amount),
            payout_fee_cents=int(payout_fee),
        )
