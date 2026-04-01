from __future__ import annotations

from decimal import Decimal

import pytest

from bot.services.finance import (
    AmountParseError,
    FinanceService,
    InsufficientBalanceError,
    MoneyService,
)


def test_parse_amount_to_cents_supports_commas() -> None:
    assert MoneyService.parse_amount_to_cents("500,000.50") == 50_000_050


def test_parse_amount_to_cents_rejects_invalid_format() -> None:
    with pytest.raises(AmountParseError):
        MoneyService.parse_amount_to_cents("50,00")


def test_calculate_settlement_uses_configurable_fee() -> None:
    result = FinanceService.calculate_settlement(100_000, Decimal("0.065"))

    assert result.gross_amount_cents == 100_000
    assert result.net_amount_cents == 93_500
    assert result.fee_cents == 6_500


def test_calculate_payout_bank_and_service_and_debit() -> None:
    result = FinanceService.calculate_payout(100_000)

    assert result.principal_cents == 100_000
    assert result.bank_fee_cents == 1_500
    assert result.service_commission_cents == 1_000
    assert result.actual_arrival_cents == 98_500
    assert result.fee_cents == 1_000
    assert result.debit_cents == 101_000


def test_merchant_u_rate() -> None:
    assert FinanceService.merchant_u_rate(Decimal("101")) == Decimal("101.5")


def test_calculate_usdt_uses_current_rate() -> None:
    usdt_amount = FinanceService.calculate_usdt(93_500, Decimal("7"))

    # 93_500 分 = 935.00 元，除以汇率 7
    assert usdt_amount == Decimal("935.00") / Decimal("7")


def test_assert_sufficient_balance_raises_when_insufficient() -> None:
    with pytest.raises(InsufficientBalanceError):
        FinanceService.assert_sufficient_balance(100_000, 101_000)
