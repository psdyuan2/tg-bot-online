from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from bot.services.finance import PAYOUT_SERVICE_RATE, SKY_GATEWAY_RATE, MoneyService


def format_unreconciled_report(
    *,
    merchant_name: str,
    report_date: str,
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
    payout_service_cents = int(
        (Decimal(payout_principal_cents) * PAYOUT_SERVICE_RATE).quantize(Decimal("1"))
    )
    gateway_comm_cents = int(
        (Decimal(settle_gross_cents) * SKY_GATEWAY_RATE).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    )
    net_after_gateway = settle_gross_cents - gateway_comm_cents
    usdt_cents = net_after_gateway - int(
        (Decimal(payout_principal_cents) * (Decimal(1) + PAYOUT_SERVICE_RATE)).quantize(Decimal("1"))
    )
    usdt = (
        MoneyService.cents_to_decimal(usdt_cents) / actual_u_rate
        if actual_u_rate > 0
        else Decimal(0)
    )
    payout_formula = f"{MoneyService.format_cents(payout_principal_cents)}*(1+{int(PAYOUT_SERVICE_RATE * 100)}%)"
    payout_total = int(
        (Decimal(payout_principal_cents) * (Decimal(1) + PAYOUT_SERVICE_RATE)).quantize(Decimal("1"))
    )
    lines = [
        f"{report_date} settlement information：",
        "",
        f"Total settlement for {merchant_name}",
        f"{MoneyService.format_cents(settle_gross_cents)} = {MoneyService.format_cents(settle_gross_cents)}",
        "",
        f"Less 4% fee: {MoneyService.format_cents(settle_gross_cents)}* (1 - 4%) ={MoneyService.format_cents(gateway_comm_cents)} ",
        "",
        f"payout：",
        f"{merchant_name}：{MoneyService.format_cents(payout_principal_cents)}",
        f"ur payout profit：{MoneyService.format_cents(payout_principal_cents)}*{int(PAYOUT_SERVICE_RATE * 100)}%={MoneyService.format_cents(payout_service_cents)}.",
        "",
        f"USD:",
        (
            f"({MoneyService.format_cents(settle_gross_cents)}-{MoneyService.format_cents(gateway_comm_cents)}"
            f"-{payout_formula}={MoneyService.format_cents(payout_total)}="
            f"{MoneyService.format_cents(usdt_cents)}/{actual_u_rate}={MoneyService.format_decimal(usdt)}."
        ),
    ]
    return "\n".join(lines)
