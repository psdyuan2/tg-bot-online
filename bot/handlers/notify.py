from __future__ import annotations

from datetime import datetime, timedelta, timezone
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

    @router.message(Command(commands=["set_id"]))
    async def reset_merchant_id(message: Message) -> None:
        args = split_command_args(message.text or "")
        if len(args) != 1:
            await message.answer("用法: /set_id [新短码]")
            return
        new_code = args[0].strip().lower()
        if not new_code:
            await message.answer("短码不能为空。")
            return
        if message.chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
            await message.answer("请在商户群组内使用此命令。")
            return
        async with session_factory() as session:
            ok, text = await MerchantService.reset_merchant_code(session, message.chat.id, new_code)
        await message.answer(text)

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

        now = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S")

        chat = message.chat
        async with session_factory() as session:
            merchant = await MerchantService.get_by_chat_id_for_update(session, chat.id)
            if merchant is None:
                await message.answer("当前群组未绑定商户，请先在群内使用 /add_id 创建商户标识。")
                return

            if principal_cents > merchant.balance:
                await message.answer(f"申请金额 {MoneyService.format_cents(principal_cents)} 超过当前余额 {MoneyService.format_cents(merchant.balance)}，无法完成代付。")
                return

            try:
                result = await LedgerService.payout(session, merchant, principal_cents)
            except InsufficientBalanceError as exc:
                await session.rollback()
                await message.answer(str(exc))
                return

        await message.answer(
            "\n".join(
                [
                    f"当前时间: {now}",
                    f"申请金额: {MoneyService.format_cents(result.principal_cents)}",
                    f"2.5%网关手续费: {MoneyService.format_cents(result.gateway_fee_cents)}",
                    f"实际到账: {MoneyService.format_cents(result.actual_arrival_cents)}",
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

    @router.message(Command(commands=["balance"]))
    async def show_balance(message: Message) -> None:
        if message.chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
            await message.answer("请在商户群组内使用此命令。")
            return
        async with session_factory() as session:
            merchant = await MerchantService.get_by_chat_id(session, message.chat.id)
        if merchant is None:
            await message.answer("当前群组未绑定商户，请先在群内使用 /add_id 创建商户标识。")
            return
        await message.answer(f"当前余额: {MoneyService.format_cents(merchant.balance)}")

    @router.message(Command(commands=["exchange"]))
    async def exchange(message: Message) -> None:
        args = split_command_args(message.text or "")
        if len(args) != 1:
            await message.answer("用法: /exchange [金额]")
            return

        try:
            amount_cents = MoneyService.parse_amount_to_cents(args[0])
        except ValueError as exc:
            await message.answer(str(exc))
            return

        if amount_cents <= 0:
            await message.answer("金额必须大于 0。")
            return

        now = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S")

        async with session_factory() as session:
            merchant = await MerchantService.get_by_chat_id_for_update(session, message.chat.id)
            if merchant is None:
                await message.answer("当前群组未绑定商户，请先在群内使用 /add_id 创建商户标识。")
                return

            if amount_cents > merchant.balance:
                await message.answer(
                    f"申请打款金额 {MoneyService.format_cents(amount_cents)} "
                    f"超过当前余额 {MoneyService.format_cents(merchant.balance)}，无法完成。"
                )
                return

            merchant.balance -= amount_cents
            remaining = merchant.balance
            await session.commit()

            actual_u = await SystemConfigService.get_u_rate(session, default_u_rate)
            merchant_u = FinanceService.merchant_u_rate(actual_u)

        amount_decimal = MoneyService.cents_to_decimal(amount_cents)
        usd = amount_decimal / merchant_u

        await message.answer(
            "\n".join(
                [
                    f"时间: {now}",
                    f"商户: {merchant.merchant_code or merchant.name}",
                    f"申请打款金额: {MoneyService.format_cents(amount_cents)}",
                    f"今日u价: {merchant_u}",
                    f"usd: {MoneyService.format_cents(amount_cents)}/{merchant_u}={MoneyService.format_decimal(usd)}",
                ]
            )
        )

    return router
