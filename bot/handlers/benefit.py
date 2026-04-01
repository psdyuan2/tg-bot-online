from __future__ import annotations

from decimal import Decimal

from aiogram import Router
from aiogram.enums import ChatType
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.handlers.common import parse_dividend_rate_arg, split_command_args
from bot.services.finance import MoneyService
from bot.services.ledger import MerchantService, SystemConfigService


def build_benefit_router(
    session_factory: async_sessionmaker[AsyncSession],
) -> Router:
    router = Router(name="benefit")

    @router.message(Command(commands=["set_fit"]))
    async def set_dividend_rate(message: Message) -> None:
        args = split_command_args(message.text or "")
        if len(args) != 1:
            await message.answer("用法: /set_fit [分红率]\n例如 1 表示 1%，或 0.01。")
            return
        try:
            rate = parse_dividend_rate_arg(args[0])
        except ValueError as exc:
            await message.answer(str(exc))
            return
        async with session_factory() as session:
            await SystemConfigService.set_dividend_rate(session, rate)
        await message.answer(f"分红率已设为: {rate}（{rate * Decimal(100)}%）")

    @router.message(Command(commands=["balance"]))
    async def show_benefit_balance(message: Message) -> None:
        if message.chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
            await message.answer("请在群组内使用此命令。")
            return
        async with session_factory() as session:
            merchant = await MerchantService.get_by_chat_id(session, message.chat.id)
        if merchant is None:
            await message.answer("当前群未绑定商户，请先 /add_id。")
            return
        await message.answer(f"当前分红余额（USDT）: {MoneyService.format_usdt_balance(Decimal(merchant.benefit_balance))}")

    @router.message(Command(commands=["clear"]))
    async def clear_benefit_balance(message: Message) -> None:
        if message.chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
            await message.answer("请在群组内使用此命令。")
            return
        async with session_factory() as session:
            merchant = await MerchantService.get_by_chat_id_for_update(session, message.chat.id)
            if merchant is None:
                await message.answer("当前群未绑定商户，请先 /add_id。")
                return
            merchant.benefit_balance = Decimal("0")
            await session.commit()
        await message.answer("分红余额已结清为零。")

    return router
