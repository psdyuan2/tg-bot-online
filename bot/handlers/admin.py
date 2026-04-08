from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from aiogram import Bot, Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from bot.db.models import Merchant
from bot.handlers.common import (
    parse_decimal_arg,
    parse_fee_rate_arg,
    split_command_args,
)
from bot.services.finance import MoneyService
from bot.services.ledger import (
    BenefitBindingService,
    LedgerService,
    MerchantService,
    ReportService,
    SystemConfigService,
    merchant_display,
)
from bot.services.report_text import format_merchant_report, format_unreconciled_report


def build_admin_router(
    session_factory: async_sessionmaker[AsyncSession],
    notify_bot: Bot,
    benefit_bot: Bot,
    default_u_rate: Decimal,
    default_settle_fee_rate: Decimal,
    default_dividend_rate: Decimal,
) -> Router:
    router = Router(name="admin")

    @router.message(Command(commands=["uset"]))
    async def set_u_rate(message: Message) -> None:
        args = split_command_args(message.text or "")
        if len(args) != 1:
            await message.answer("用法: /uset [实际U价]")
            return

        try:
            u_rate = parse_decimal_arg(args[0])
        except ValueError as exc:
            await message.answer(str(exc))
            return

        async with session_factory() as session:
            await SystemConfigService.set_u_rate(session, u_rate)

        await message.answer(f"实际 U 价已更新为: {u_rate}")

    @router.message(Command(commands=["set_payout_fit"]))
    async def set_settle_fee_rate(message: Message) -> None:
        args = split_command_args(message.text or "")
        if len(args) != 1:
            await message.answer("用法: /set_payout_fit [结算入账服务费率]\n例如 6.5 或 0.065 表示 6.5%。")
            return
        try:
            rate = parse_fee_rate_arg(args[0])
        except ValueError as exc:
            await message.answer(str(exc))
            return
        async with session_factory() as session:
            await SystemConfigService.set_settle_fee_rate(session, rate)
        await message.answer(f"结算入账服务费率已设为: {rate}（{rate * Decimal(100)}%）")

    @router.message(Command(commands=["settle"]))
    async def settle(message: Message) -> None:
        args = split_command_args(message.text or "")
        if len(args) != 2:
            await message.answer(
                "用法: /settle [商户标识] [金额]\n商户标识为商户群内 /add_id 生成的短码，或历史商户名 / 数字 id。"
            )
            return

        merchant_identifier, raw_amount = args
        try:
            gross_amount_cents = MoneyService.parse_amount_to_cents(raw_amount)
        except ValueError as exc:
            await message.answer(str(exc))
            return

        now = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S")

        async with session_factory() as session:
            merchant = await MerchantService.get_by_identifier(session, merchant_identifier)
            if merchant is None:
                await message.answer("未找到对应商户，请确认商户群内已执行 /add_id 或数据库中已有该商户。")
                return

            settle_fee = await SystemConfigService.get_settle_fee_rate(session, default_settle_fee_rate)
            dividend_rate = await SystemConfigService.get_dividend_rate(session, default_dividend_rate)
            result, dividend_usdt = await LedgerService.settle(
                session,
                merchant,
                gross_amount_cents,
                settle_fee_rate=settle_fee,
                dividend_rate=dividend_rate,
                default_u_rate=default_u_rate,
            )

        label = merchant_display(merchant)
        await message.answer(
            "\n".join(
                [
                    f"时间: {now}",
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
                    f"时间: {now}",
                    "收到新的结算入账通知。",
                    f"商户: {label}",
                    f"结算金额: {MoneyService.format_cents(result.gross_amount_cents)}",
                    f"服务佣金: {MoneyService.format_cents(result.fee_cents)}",
                    f"实际入账: {MoneyService.format_cents(result.net_amount_cents)}",
                    f"当前可用余额: {MoneyService.format_cents(merchant.balance)}",
                ]
            ),
        )

        if dividend_usdt is not None and dividend_usdt > 0:
            async with session_factory() as session:
                benefit_chats = await BenefitBindingService.list_chats_for_merchant(session, merchant.id)
            total_bb = MoneyService.format_usdt_balance(Decimal(merchant.benefit_balance))
            div_line = MoneyService.format_usdt_balance(dividend_usdt)
            notice = (
                f"分红通知\n商户: {label}\n本笔净入账: {MoneyService.format_cents(result.net_amount_cents)}\n"
                f"本笔分红: +{div_line} USDT\n该商户分红累计: {total_bb} USDT"
            )
            failed_chats: list[str] = []
            for cid in benefit_chats:
                try:
                    await benefit_bot.send_message(cid, notice)
                except TelegramForbiddenError:
                    failed_chats.append(str(cid))
            if failed_chats:
                await message.answer(
                    "分红通知未能发送到以下群（请确认分红机器人在群内且未被禁言）："
                    + ", ".join(failed_chats)
                )

    @router.message(Command(commands=["report"]))
    async def report(message: Message) -> None:
        args = split_command_args(message.text or "")
        if len(args) != 1:
            await message.answer(
                "用法: /report [商户标识]\n商户标识为商户群内 /add_id 生成的短码，或历史商户名 / 数字 id。"
            )
            return

        async with session_factory() as session:
            merchant = await MerchantService.get_by_identifier(session, args[0])
            if merchant is None:
                await message.answer("未找到对应商户。")
                return
            locked = await session.get(Merchant, merchant.id, with_for_update=True)
            if locked is None:
                await message.answer("未找到对应商户。")
                return
            today = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d")
            snapshot = await ReportService.build_unreconciled_snapshot(session, locked.id)
            await session.refresh(locked)
            balance_before = locked.balance

            actual_u = await SystemConfigService.peek_u_rate(session, default_u_rate)
            settle_fee = await SystemConfigService.peek_settle_fee_rate(session, default_settle_fee_rate)

            report_text = format_unreconciled_report(
                merchant_name=merchant_display(merchant),
                report_date=today,
                settle_count=snapshot.settle_count,
                settle_gross_cents=snapshot.settle_gross_cents,
                settle_fee_cents=snapshot.settle_fee_cents,
                settle_fee_rate=settle_fee,
                settle_net_cents=snapshot.settle_net_cents,
                payout_count=snapshot.payout_count,
                payout_principal_cents=snapshot.payout_principal_cents,
                payout_fee_cents=snapshot.payout_fee_cents,
                closing_balance_cents=balance_before,
                actual_u_rate=actual_u,
            )
            merchant_text = format_merchant_report(
                settle_gross_cents=snapshot.settle_gross_cents,
                settle_fee_cents=snapshot.settle_fee_cents,
                settle_fee_rate=settle_fee,
                settle_net_cents=snapshot.settle_net_cents,
                payout_principal_cents=snapshot.payout_principal_cents,
                payout_fee_cents=snapshot.payout_fee_cents,
                closing_balance_cents=balance_before,
                actual_u_rate=actual_u,
            )
            locked.balance = 0
            await session.commit()

        await message.answer(report_text)
        await message.answer(merchant_text)

    return router
