from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from aiogram import Router
from aiogram.enums import ChatType
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.handlers.common import split_command_args
from bot.services.finance import FinanceService, InsufficientBalanceError, MoneyService
from bot.services.ledger import LedgerService, MerchantService, SystemConfigService


def build_notify_router(
    session_factory: async_sessionmaker[AsyncSession],
    default_u_rate: Decimal,
) -> Router:
    router = Router(name="notify")

    @router.message(Command(commands=["add_id"]))
    async def add_merchant_id(message: Message) -> None:
        if message.chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
            await message.answer("请在商户群组内使用此命令。")
            return
        async with session_factory() as session:
            text = await MerchantService.register_merchant_code_for_chat(session, message.chat.id)
        await message.answer(text)

    @router.message(Command(commands=["see_id"]))
    async def see_merchant_id(message: Message) -> None:
        if message.chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
            await message.answer("请在商户群组内使用此命令。")
            return
        async with session_factory() as session:
            merchant = await MerchantService.get_by_chat_id(session, message.chat.id)
        if merchant is None or merchant.merchant_code is None:
            await message.answer("本群尚未设置商户标识，请使用 /add_id 创建。")
            return
        await message.answer(f"本群商户标识: {merchant.merchant_code}")

    @router.message(Command(commands=["u"]))
    async def show_u_rate(message: Message) -> None:
        async with session_factory() as session:
            actual_u = await SystemConfigService.get_u_rate(session, default_u_rate)
        merchant_u = FinanceService.merchant_u_rate(actual_u)
        await message.answer(f"今日u价 {merchant_u}")

    @router.message(Command(commands=["payout"]))
    async def payout(message: Message) -> None:
        args = split_command_args(message.text or "")
        if len(args) != 1:
            await message.answer("用法: /payout [金额]")
            return

        try:
            principal_cents = MoneyService.parse_amount_to_cents(args[0])
        except ValueError as exc:
            await message.answer(str(exc))
            return

        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        chat = message.chat
        async with session_factory() as session:
            merchant = await MerchantService.get_by_chat_id_for_update(session, chat.id)
            if merchant is None:
                await message.answer("当前群组未绑定商户，请先在群内使用 /add_id 创建商户标识。")
                return

            actual_u = await SystemConfigService.get_u_rate(session, default_u_rate)
            merchant_u = FinanceService.merchant_u_rate(actual_u)

            try:
                result = await LedgerService.payout(session, merchant, principal_cents)
            except InsufficientBalanceError as exc:
                await session.rollback()
                await message.answer(str(exc))
                return

        usdt = FinanceService.calculate_usdt(merchant.balance, merchant_u)

        await message.answer(
            "\n".join(
                [
                    f"当前时间: {now}",
                    f"申请代付金额: {MoneyService.format_cents(result.principal_cents)}",
                    f"银行手续费（1.5%）: {MoneyService.format_cents(result.bank_fee_cents)}",
                    f"服务佣金（1%）: {MoneyService.format_cents(result.service_commission_cents)}",
                    f"实际代付到账: {MoneyService.format_cents(result.actual_arrival_cents)}",
                    f"当前可用余额: {MoneyService.format_cents(merchant.balance)}",
                    f"可回U: {MoneyService.format_decimal(usdt)} USDT（商户U价 {merchant_u}）",
                ]
            )
        )

    @router.message(Command(commands=["quote"]))
    async def estimate_usdt(message: Message) -> None:
        args = split_command_args(message.text or "")
        if len(args) != 1:
            await message.answer("用法: /quote [金额]")
            return

        try:
            balance_cents = MoneyService.parse_amount_to_cents(args[0])
        except ValueError as exc:
            await message.answer(str(exc))
            return

        async with session_factory() as session:
            actual_u = await SystemConfigService.get_u_rate(session, default_u_rate)
        merchant_u = FinanceService.merchant_u_rate(actual_u)

        usdt_amount = FinanceService.calculate_usdt(balance_cents, merchant_u)
        await message.answer(
            "\n".join(
                [
                    f"输入金额: {MoneyService.format_cents(balance_cents)}",
                    f"商户 U 价: {merchant_u}",
                    f"预估下发 USDT: {MoneyService.format_decimal(usdt_amount)}",
                ]
            )
        )

    return router
