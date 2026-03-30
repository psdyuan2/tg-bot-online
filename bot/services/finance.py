from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP


CENT_FACTOR = Decimal("100")
SETTLEMENT_RATE = Decimal("0.935")
PAYOUT_RATE = Decimal("1.01")
TWO_PLACES = Decimal("0.01")


class AmountParseError(ValueError):
    pass


class InsufficientBalanceError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class SettlementResult:
    gross_amount_cents: int
    fee_cents: int
    net_amount_cents: int


@dataclass(frozen=True, slots=True)
class PayoutResult:
    principal_cents: int
    fee_cents: int
    debit_cents: int


class MoneyService:
    amount_pattern = re.compile(r"^\d{1,3}(,\d{3})*(\.\d+)?$|^\d+(\.\d+)?$")

    @classmethod
    def parse_amount_to_cents(cls, raw_amount: str) -> int:
        normalized = raw_amount.strip()
        if not normalized:
            raise AmountParseError("金额不能为空。")
        if not cls.amount_pattern.fullmatch(normalized):
            raise AmountParseError("金额格式不正确，请使用纯数字或带千分位的数字。")

        value = Decimal(normalized.replace(",", ""))
        cents = (value * CENT_FACTOR).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        if cents <= 0:
            raise AmountParseError("金额必须大于 0。")
        return int(cents)

    @staticmethod
    def cents_to_decimal(cents: int) -> Decimal:
        return (Decimal(cents) / CENT_FACTOR).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

    @classmethod
    def format_cents(cls, cents: int) -> str:
        return f"{cls.cents_to_decimal(cents):,.2f}"

    @staticmethod
    def format_decimal(value: Decimal, places: str = "0.000000") -> str:
        return f"{value.quantize(Decimal(places), rounding=ROUND_HALF_UP):,}"


class FinanceService:
    @staticmethod
    def calculate_settlement(gross_amount_cents: int) -> SettlementResult:
        net_amount = (Decimal(gross_amount_cents) * SETTLEMENT_RATE).quantize(
            Decimal("1"),
            rounding=ROUND_HALF_UP,
        )
        net_amount_cents = int(net_amount)
        fee_cents = gross_amount_cents - net_amount_cents
        return SettlementResult(
            gross_amount_cents=gross_amount_cents,
            fee_cents=fee_cents,
            net_amount_cents=net_amount_cents,
        )

    @staticmethod
    def calculate_payout(principal_cents: int) -> PayoutResult:
        debit_amount = (Decimal(principal_cents) * PAYOUT_RATE).quantize(
            Decimal("1"),
            rounding=ROUND_HALF_UP,
        )
        debit_cents = int(debit_amount)
        fee_cents = debit_cents - principal_cents
        return PayoutResult(
            principal_cents=principal_cents,
            fee_cents=fee_cents,
            debit_cents=debit_cents,
        )

    @staticmethod
    def calculate_usdt(balance_cents: int, u_rate: Decimal) -> Decimal:
        if u_rate <= 0:
            raise ValueError("U 价必须大于 0。")
        return MoneyService.cents_to_decimal(balance_cents) / u_rate

    @staticmethod
    def assert_sufficient_balance(balance_cents: int, required_cents: int) -> None:
        if balance_cents < required_cents:
            raise InsufficientBalanceError("商户余额不足，无法完成代付。")
