from __future__ import annotations

import secrets
import string
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import Boolean, Select, and_, desc, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import BenefitGroupBinding, Merchant, SystemConfig, Transaction
from bot.services.finance import FinanceService, MoneyService, PayoutResult, SettlementResult


U_RATE_KEY = "U_RATE"
SETTLE_FEE_RATE_KEY = "SETTLE_FEE_RATE"
DIVIDEND_RATE_KEY = "DIVIDEND_RATE"


def merchant_display(merchant: Merchant) -> str:
    return merchant.merchant_code or merchant.merchant_name


@dataclass(frozen=True, slots=True)
class LastTxnReportSnapshot:
    """最近一笔结算；代付为与该笔结算同一批次（该 settle 之后至下一笔 settle 之前）的代付合计。"""

    settle_gross_cents: int
    settle_fee_cents: int
    settle_net_cents: int
    payout_principal_cents: int
    payout_fee_cents: int


@dataclass(frozen=True, slots=True)
class UnreconciledReportSnapshot:
    """所有流水汇总（不含代付，代付单独汇总）。"""

    settle_count: int
    settle_gross_cents: int
    settle_fee_cents: int
    settle_net_cents: int
    payout_count: int
    payout_principal_cents: int
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

    @staticmethod
    async def get_settle_fee_rate(session: AsyncSession, default_rate: Decimal) -> Decimal:
        record = await session.get(SystemConfig, SETTLE_FEE_RATE_KEY)
        if record is None:
            record = SystemConfig(key=SETTLE_FEE_RATE_KEY, value=str(default_rate))
            session.add(record)
            await session.commit()
            return default_rate
        return Decimal(record.value)

    @staticmethod
    async def set_settle_fee_rate(session: AsyncSession, rate: Decimal) -> Decimal:
        record = await session.get(SystemConfig, SETTLE_FEE_RATE_KEY)
        if record is None:
            record = SystemConfig(key=SETTLE_FEE_RATE_KEY, value=str(rate))
            session.add(record)
        else:
            record.value = str(rate)
        await session.commit()
        return rate

    @staticmethod
    async def get_dividend_rate(session: AsyncSession, default_rate: Decimal) -> Decimal:
        record = await session.get(SystemConfig, DIVIDEND_RATE_KEY)
        if record is None:
            record = SystemConfig(key=DIVIDEND_RATE_KEY, value=str(default_rate))
            session.add(record)
            await session.commit()
            return default_rate
        return Decimal(record.value)

    @staticmethod
    async def set_dividend_rate(session: AsyncSession, rate: Decimal) -> Decimal:
        record = await session.get(SystemConfig, DIVIDEND_RATE_KEY)
        if record is None:
            record = SystemConfig(key=DIVIDEND_RATE_KEY, value=str(rate))
            session.add(record)
        else:
            record.value = str(rate)
        await session.commit()
        return rate

    @staticmethod
    async def peek_u_rate(session: AsyncSession, default_rate: Decimal) -> Decimal:
        record = await session.get(SystemConfig, U_RATE_KEY)
        if record is None:
            return default_rate
        return Decimal(record.value)

    @staticmethod
    async def peek_settle_fee_rate(session: AsyncSession, default_rate: Decimal) -> Decimal:
        record = await session.get(SystemConfig, SETTLE_FEE_RATE_KEY)
        if record is None:
            return default_rate
        return Decimal(record.value)


class BenefitBindingService:
    @staticmethod
    async def bind(session: AsyncSession, benefit_chat_id: int, merchant_id: int) -> bool:
        existing = await session.execute(
            select(BenefitGroupBinding.id).where(
                BenefitGroupBinding.benefit_chat_id == benefit_chat_id,
                BenefitGroupBinding.merchant_id == merchant_id,
            )
        )
        if existing.scalar_one_or_none() is not None:
            return False
        session.add(BenefitGroupBinding(benefit_chat_id=benefit_chat_id, merchant_id=merchant_id))
        await session.commit()
        return True

    @staticmethod
    async def list_chats_for_merchant(session: AsyncSession, merchant_id: int) -> list[int]:
        rows = await session.execute(
            select(BenefitGroupBinding.benefit_chat_id).where(
                BenefitGroupBinding.merchant_id == merchant_id
            )
        )
        return [int(r[0]) for r in rows.all()]

    @staticmethod
    async def list_merchants_for_benefit_chat(
        session: AsyncSession,
        benefit_chat_id: int,
    ) -> list[Merchant]:
        result = await session.execute(
            select(Merchant)
            .join(BenefitGroupBinding, BenefitGroupBinding.merchant_id == Merchant.id)
            .where(BenefitGroupBinding.benefit_chat_id == benefit_chat_id)
        )
        return list(result.scalars().all())


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
                benefit_balance=Decimal("0"),
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

    @staticmethod
    async def reset_merchant_code(session: AsyncSession, chat_id: int, new_code: str) -> tuple[bool, str]:
        merchant = await MerchantService.get_by_chat_id(session, chat_id)
        if merchant is None:
            return False, "本群未注册商户，请先使用 /add_id 创建商户。"
        if merchant.merchant_code == new_code:
            return False, f"本群商户标识已是 {new_code}，无需修改。"
        existing = await session.execute(
            select(Merchant.id).where(Merchant.merchant_code == new_code).limit(1)
        )
        if existing.scalar_one_or_none() is not None:
            return False, f"商户标识 {new_code} 已被其他群使用，请换一个。"
        merchant.merchant_code = new_code
        await session.commit()
        return True, f"商户标识已更新为: {new_code}"


class LedgerService:
    @staticmethod
    async def settle(
        session: AsyncSession,
        merchant: Merchant,
        gross_amount_cents: int,
        *,
        settle_fee_rate: Decimal,
        dividend_rate: Decimal,
        default_u_rate: Decimal,
    ) -> tuple[SettlementResult, Decimal | None]:
        actual_u = await SystemConfigService.get_u_rate(session, default_u_rate)
        result = FinanceService.calculate_settlement(gross_amount_cents, settle_fee_rate)
        merchant.balance += result.net_amount_cents
        dividend_usdt_added: Decimal | None = None
        if dividend_rate > 0:
            div_cents = int(
                (Decimal(result.net_amount_cents) * dividend_rate).quantize(
                    Decimal("1"),
                    rounding=ROUND_HALF_UP,
                )
            )
            if div_cents > 0:
                m_u = FinanceService.merchant_u_rate(actual_u)
                delta_usdt = MoneyService.cents_to_decimal(div_cents) / m_u
                merchant.benefit_balance = Decimal(merchant.benefit_balance) + delta_usdt
                dividend_usdt_added = delta_usdt
        session.add(
            Transaction(
                merchant_id=merchant.id,
                tx_type="settle",
                amount=result.gross_amount_cents,
                fee=result.fee_cents,
                is_reported=False,
            )
        )
        await session.commit()
        await session.refresh(merchant)
        return result, dividend_usdt_added

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
                fee=result.gateway_fee_cents,
                is_reported=False,
            )
        )
        await session.commit()
        await session.refresh(merchant)
        return result


class ReportService:
    @staticmethod
    async def build_unreconciled_snapshot(
        session: AsyncSession,
        merchant_id: int,
    ) -> UnreconciledReportSnapshot:
        unreported = and_(
            Transaction.merchant_id == merchant_id,
            Transaction.is_reported == False,
        )
        rows = await session.execute(
            select(
                Transaction.tx_type,
                func.count(Transaction.id),
                func.coalesce(func.sum(Transaction.amount), 0),
                func.coalesce(func.sum(Transaction.fee), 0),
            )
            .where(unreported)
            .group_by(Transaction.tx_type)
        )
        summary = {tx_type: (int(count), int(amount), int(fee)) for tx_type, count, amount, fee in rows.all()}
        sc, sg, sf = summary.get("settle", (0, 0, 0))
        pc, pp, pf = summary.get("payout", (0, 0, 0))
        await session.execute(
            update(Transaction).where(unreported).values(is_reported=True)
        )
        return UnreconciledReportSnapshot(
            settle_count=sc,
            settle_gross_cents=sg,
            settle_fee_cents=sf,
            settle_net_cents=sg - sf,
            payout_count=pc,
            payout_principal_cents=pp,
            payout_fee_cents=pf,
        )

    @staticmethod
    async def build_last_txn_snapshot(
        session: AsyncSession,
        merchant_id: int,
    ) -> LastTxnReportSnapshot:
        r_settle = await session.execute(
            select(Transaction)
            .where(Transaction.merchant_id == merchant_id, Transaction.tx_type == "settle")
            .order_by(desc(Transaction.created_at))
            .limit(1)
        )
        st = r_settle.scalar_one_or_none()
        sg, sf, sn = 0, 0, 0
        if st is not None:
            sg = int(st.amount)
            sf = int(st.fee)
            sn = sg - sf

        pp, pf = 0, 0
        if st is not None:
            r_next_settle = await session.execute(
                select(Transaction)
                .where(
                    Transaction.merchant_id == merchant_id,
                    Transaction.tx_type == "settle",
                    Transaction.created_at > st.created_at,
                )
                .order_by(Transaction.created_at.asc())
                .limit(1)
            )
            next_st = r_next_settle.scalar_one_or_none()
            payout_filters = [
                Transaction.merchant_id == merchant_id,
                Transaction.tx_type == "payout",
                Transaction.created_at > st.created_at,
            ]
            if next_st is not None:
                payout_filters.append(Transaction.created_at < next_st.created_at)
            agg = await session.execute(
                select(
                    func.coalesce(func.sum(Transaction.amount), 0),
                    func.coalesce(func.sum(Transaction.fee), 0),
                ).where(and_(*payout_filters))
            )
            row = agg.one()
            pp = int(row[0])
            pf = int(row[1])
        return LastTxnReportSnapshot(
            settle_gross_cents=sg,
            settle_fee_cents=sf,
            settle_net_cents=sn,
            payout_principal_cents=pp,
            payout_fee_cents=pf,
        )
