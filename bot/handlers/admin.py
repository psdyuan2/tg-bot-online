from __future__ import annotations

from decimal import Decimal

from aiogram import Bot, Router
from aiogram.exceptions import TelegramForbiddenError
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from bot.handlers.common import parse_decimal_arg, split_command_args
from bot.services.finance import MoneyService
from bot.services.ledger import (
    LedgerService,
    MerchantService,
    ReportService,
    SystemConfigService,
    merchant_display,
)


def build_admin_router(
    session_factory: async_sessionmaker[AsyncSession],
    notify_bot: Bot,
    default_u_rate: Decimal,
) -> Router:
    router = Router(name="admin")

    @router.message(Command(commands=["uset"]))
    async def set_u_rate(message: Message) -> None:
        args = split_command_args(message.text or "")
        if len(args) != 1:
            await message.answer("用法: /uset [汇率]")
            return

        try:
            u_rate = parse_decimal_arg(args[0])
        except ValueError as exc:
            await message.answer(str(exc))
            return

        async with session_factory() as session:
            await SystemConfigService.set_u_rate(session, u_rate)

        await message.answer(f"U 价已更新为: {u_rate}")

    @router.message(Command(commands=["settle"]))
    async def settle(message: Message) -> None:
        args = split_command_args(message.text or "")
        if len(args) != 2:
            await message.answer("用法: /settle [商户标识] [金额]\n商户标识为商户群内 /add_id 生成的短码，或历史商户名 / 数字 id。")
            return

        merchant_identifier, raw_amount = args
        try:
            gross_amount_cents = MoneyService.parse_amount_to_cents(raw_amount)
        except ValueError as exc:
            await message.answer(str(exc))
            return

        async with session_factory() as session:
            merchant = await MerchantService.get_by_identifier(session, merchant_identifier)
            if merchant is None:
                await message.answer("未找到对应商户，请确认商户群内已执行 /add_id 或数据库中已有该商户。")
                return

            result = await LedgerService.settle(session, merchant, gross_amount_cents)

        label = merchant_display(merchant)
        await message.answer(
            "\n".join(
                [
                    f"商户: {label}",
                    f"结算金额: {MoneyService.format_cents(result.gross_amount_cents)}",
                    f"服务佣金: {MoneyService.format_cents(result.fee_cents)}",
                    f"实际入账: {MoneyService.format_cents(result.net_amount_cents)}",
                    f"最新余额: {MoneyService.format_cents(merchant.balance)}",
                ]
            )
        )

        await notify_bot.send_message(
            chat_id=merchant.tg_chat_id,
            text="\n".join(
                [
                    "收到新的结算入账通知。",
                    f"商户: {label}",
                    f"结算金额: {MoneyService.format_cents(result.gross_amount_cents)}",
                    f"服务佣金: {MoneyService.format_cents(result.fee_cents)}",
                    f"实际入账: {MoneyService.format_cents(result.net_amount_cents)}",
                    f"当前可用余额: {MoneyService.format_cents(merchant.balance)}",
                ]
            ),
        )

    @router.message(Command(commands=["report"]))
    async def report(message: Message) -> None:
        args = split_command_args(message.text or "")
        if len(args) != 1:
            await message.answer("用法: /report [商户标识]\n商户标识为商户群内 /add_id 生成的短码，或历史商户名 / 数字 id。")
            return

        async with session_factory() as session:
            merchant = await MerchantService.get_by_identifier(session, args[0])
            if merchant is None:
                await message.answer("未找到对应商户。")
                return
            report_data = await ReportService.build_daily_report(session, merchant)
            u_rate = await SystemConfigService.get_u_rate(session, default_u_rate)

        usdt_estimate = MoneyService.format_decimal(
            value=(MoneyService.cents_to_decimal(merchant.balance) / u_rate),
        )
        label = merchant_display(merchant)
        report_text = "\n".join(
            [
                f"商户对账单: {label}",
                f"今日结算笔数: {report_data.settle_count}",
                f"今日结算金额: {MoneyService.format_cents(report_data.settle_amount_cents)}",
                f"今日结算佣金: {MoneyService.format_cents(report_data.settle_fee_cents)}",
                f"今日代付笔数: {report_data.payout_count}",
                f"今日代付金额: {MoneyService.format_cents(report_data.payout_amount_cents)}",
                f"今日代付手续费: {MoneyService.format_cents(report_data.payout_fee_cents)}",
                f"当前余额: {MoneyService.format_cents(merchant.balance)}",
                f"按当前 U 价预估可回 U: {usdt_estimate}",
            ]
        )
        await message.answer(report_text)
        try:
            await notify_bot.send_message(chat_id=merchant.tg_chat_id, text=report_text)
        except TelegramForbiddenError:
            await message.answer("对账单已生成，但未能发送到商户群（请确认通知机器人已在群内且未被禁言）。")

    return router
