from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP


CENT_FACTOR = Decimal("100")
BANK_FEE_RATE = Decimal("0.015")
PAYOUT_SERVICE_RATE = Decimal("0.01")
ACTUAL_ARRIVAL_FACTOR = Decimal("0.985")
DEBIT_FACTOR = Decimal("1.01")
MERCHANT_U_MARKUP = Decimal("0.5")
SKY_GATEWAY_RATE = Decimal("0.04")
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
    bank_fee_cents: int
    service_commission_cents: int
    actual_arrival_cents: int
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

    @staticmethod
    def format_usdt_balance(value: Decimal) -> str:
        return f"{value.quantize(Decimal('0.00000001'), rounding=ROUND_HALF_UP):,.8f}"


class FinanceService:
    @staticmethod
    def merchant_u_rate(actual_u_rate: Decimal) -> Decimal:
        return actual_u_rate + MERCHANT_U_MARKUP

    @staticmethod
    def calculate_settlement(gross_amount_cents: int, settle_fee_rate: Decimal) -> SettlementResult:
        if settle_fee_rate < 0 or settle_fee_rate >= 1:
            raise ValueError("结算服务费率必须在 [0, 1) 内。")
        net_amount = (
            Decimal(gross_amount_cents) * (Decimal(1) - settle_fee_rate)
        ).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        net_amount_cents = int(net_amount)
        fee_cents = gross_amount_cents - net_amount_cents
        return SettlementResult(
            gross_amount_cents=gross_amount_cents,
            fee_cents=fee_cents,
            net_amount_cents=net_amount_cents,
        )

    @staticmethod
    def calculate_payout(principal_cents: int) -> PayoutResult:
        p = Decimal(principal_cents)
        bank_fee_cents = int((p * BANK_FEE_RATE).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        service_commission_cents = int((p * PAYOUT_SERVICE_RATE).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        actual_arrival_cents = int((p * ACTUAL_ARRIVAL_FACTOR).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        debit_cents = int((p * DEBIT_FACTOR).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        return PayoutResult(
            principal_cents=principal_cents,
            bank_fee_cents=bank_fee_cents,
            service_commission_cents=service_commission_cents,
            actual_arrival_cents=actual_arrival_cents,
            fee_cents=service_commission_cents,
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
