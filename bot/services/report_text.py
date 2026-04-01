from __future__ import annotations

from decimal import Decimal

from bot.services.finance import SKY_GATEWAY_RATE, FinanceService, MoneyService


def format_merchant_group_report(
    *,
    settle_gross_cents: int,
    settle_fee_cents: int,
    settle_fee_rate: Decimal,
    settle_net_today_cents: int,
    payout_principal_cents: int,
    closing_balance_cents: int,
    merchant_u_rate: Decimal,
) -> str:
    fee_pct = (settle_fee_rate * Decimal(100)).quantize(Decimal("0.01"))
    bank_fee_cents = int(
        (Decimal(payout_principal_cents) * Decimal("0.015")).quantize(Decimal("1"))
    )
    actual_arrival_cents = int(
        (Decimal(payout_principal_cents) * Decimal("0.985")).quantize(Decimal("1"))
    )
    usdt = FinanceService.calculate_usdt(closing_balance_cents, merchant_u_rate)
    lines = [
        "商户群结算消息模版",
        "",
        " 结算对账单 (INR)",
        f"到账金额（今日合计）：{MoneyService.format_cents(settle_gross_cents)}",
        f"服务佣金 ({fee_pct:g}%): -{MoneyService.format_cents(settle_fee_cents)}",
        f"今日结算净入账：{MoneyService.format_cents(settle_net_today_cents)}",
        "",
        "🚩 代付记录（今日）",
        f"💰 申请金额：{MoneyService.format_cents(payout_principal_cents)}",
        f"银行手续费（1.5%）：{MoneyService.format_cents(bank_fee_cents)}",
        f"实际到账：{MoneyService.format_cents(actual_arrival_cents)}",
        "",
        "🚩 结余换汇（日结前）",
        f"🚀 剩余金额（可用余额）：{MoneyService.format_cents(closing_balance_cents)}",
        (
            f"🚀 下发金额：{MoneyService.format_cents(closing_balance_cents)}/{merchant_u_rate}="
            f"{MoneyService.format_decimal(usdt)} USDT (汇率 {merchant_u_rate})"
        ),
        "",
        "本次对账后结算余额已清零。",
    ]
    return "\n".join(lines)


def format_admin_group_report(
    *,
    settle_gross_cents: int,
    payout_principal_cents: int,
    payout_fee_cents: int,
    actual_u_rate: Decimal,
) -> str:
    gateway_comm_cents = int(
        (Decimal(settle_gross_cents) * SKY_GATEWAY_RATE).quantize(Decimal("1"))
    )
    numerator_cents = settle_gross_cents - gateway_comm_cents - payout_principal_cents - payout_fee_cents
    usdt = (
        MoneyService.cents_to_decimal(numerator_cents) / actual_u_rate
        if actual_u_rate > 0
        else Decimal(0)
    )
    lines = [
        f"Settlement Total: {MoneyService.format_cents(settle_gross_cents)}",
        f"Less Your Comm (4%): -{MoneyService.format_cents(gateway_comm_cents)}",
        "",
        f"🚩 ACTION 1: payout sent: {MoneyService.format_cents(payout_principal_cents)}",
        f"Your Payout Comm (1%): {MoneyService.format_cents(payout_fee_cents)}",
        "",
        f"🚩 ACTION 2: USDT sent：{MoneyService.format_decimal(usdt)}",
        (
            f"（{MoneyService.format_cents(settle_gross_cents)}-{MoneyService.format_cents(gateway_comm_cents)}"
            f"-{MoneyService.format_cents(payout_principal_cents)}-{MoneyService.format_cents(payout_fee_cents)}）"
            f"/{actual_u_rate}={MoneyService.format_decimal(usdt)}."
        ),
        "",
        "本次对账后结算余额已清零。",
    ]
    return "\n".join(lines)
