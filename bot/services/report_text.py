from __future__ import annotations

from decimal import Decimal

from bot.services.finance import SKY_GATEWAY_RATE, FinanceService, MoneyService


def format_merchant_group_report(
    *,
    settle_gross_cents: int,
    settle_fee_cents: int,
    settle_fee_rate: Decimal,
    settle_net_cents: int,
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
        f"到账金额（本笔结算）：{MoneyService.format_cents(settle_gross_cents)}",
        f"服务佣金 ({fee_pct:g}%): -{MoneyService.format_cents(settle_fee_cents)}",
        f"本笔结算净入账：{MoneyService.format_cents(settle_net_cents)}",
        "",
        "🚩 代付记录（本结算批次）",
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


def format_unreconciled_report(
    *,
    settle_count: int,
    settle_gross_cents: int,
    settle_fee_cents: int,
    settle_fee_rate: Decimal,
    settle_net_cents: int,
    payout_count: int,
    payout_principal_cents: int,
    payout_fee_cents: int,
    closing_balance_cents: int,
    actual_u_rate: Decimal,
) -> str:
    fee_pct = (settle_fee_rate * Decimal(100)).quantize(Decimal("0.01"))
    gateway_comm_cents = int(
        (Decimal(settle_gross_cents) * SKY_GATEWAY_RATE).quantize(Decimal("1"))
    )
    net_after_gateway = settle_gross_cents - gateway_comm_cents - payout_principal_cents - payout_fee_cents
    usdt = (
        MoneyService.cents_to_decimal(net_after_gateway) / actual_u_rate
        if actual_u_rate > 0
        else Decimal(0)
    )
    lines = [
        "━━━━━━━━ 对账单（全部未对账流水）━━━━━━━━",
        f"商户结算是笔数：{settle_count} 笔",
        f"合计到账：{MoneyService.format_cents(settle_gross_cents)}",
        f"服务佣金（{fee_pct:g}%）：-{MoneyService.format_cents(settle_fee_cents)}",
        f"净入账合计：{MoneyService.format_cents(settle_net_cents)}",
        "",
        f"代付是笔数：{payout_count} 笔",
        f"合计代付本金：{MoneyService.format_cents(payout_principal_cents)}",
        f"代付服务佣金（1%）：{MoneyService.format_cents(payout_fee_cents)}",
        "",
        "━━━━━━━━ 结余换汇（日结前）━━━━━━━━",
        f"对账前可用余额：{MoneyService.format_cents(closing_balance_cents)}",
        (
            f"下发金额：{MoneyService.format_cents(closing_balance_cents)}/{actual_u_rate}="
            f"{MoneyService.format_decimal(usdt)} USDT"
        ),
        "",
        "━━━━━━━━ 运营台账（网关口径）━━━━━━━━",
        f"网关佣金（4%）：-{MoneyService.format_cents(gateway_comm_cents)}",
        (
            f"净额：({MoneyService.format_cents(settle_gross_cents)}"
            f"-{MoneyService.format_cents(gateway_comm_cents)}"
            f"-{MoneyService.format_cents(payout_principal_cents)}"
            f"-{MoneyService.format_cents(payout_fee_cents)})"
            f"={MoneyService.format_cents(net_after_gateway)}"
        ),
        f"折合 USDT：{MoneyService.format_decimal(usdt)}（汇率 {actual_u_rate}）",
        "",
        "⚠️ 本次对账后结算余额已清零。",
    ]
    return "\n".join(lines)
