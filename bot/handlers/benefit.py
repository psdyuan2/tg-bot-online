from __future__ import annotations

from decimal import Decimal

from aiogram import Router
from aiogram.enums import ChatType
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.db.models import Merchant
from bot.handlers.common import parse_dividend_rate_arg, split_command_args
from bot.services.finance import MoneyService
from bot.services.ledger import BenefitBindingService, MerchantService, SystemConfigService, merchant_display


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

    @router.message(Command(commands=["add_id"]))
    async def benefit_bind_merchant(message: Message) -> None:
        if message.chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
            await message.answer("请在群组内使用此命令。")
            return
        args = split_command_args(message.text or "")
        if len(args) != 1:
            await message.answer("用法: /add_id <商户短码或商户标识>")
            return
        async with session_factory() as session:
            merchant = await MerchantService.get_by_identifier(session, args[0])
            if merchant is None:
                await message.answer("未找到该商户，请确认短码或商户名正确。")
                return
            created = await BenefitBindingService.bind(session, message.chat.id, merchant.id)
        label = merchant_display(merchant)
        if created:
            await message.answer(f"已绑定商户 {label}。该商户每笔结算产生的分红将按本群 /set_fit 推送至本群。")
        else:
            await message.answer(f"商户 {label} 已绑定到本群。")

    @router.message(Command(commands=["see_id"]))
    async def benefit_list_bindings(message: Message) -> None:
        if message.chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
            await message.answer("请在群组内使用此命令。")
            return
        async with session_factory() as session:
            merchants = await BenefitBindingService.list_merchants_for_benefit_chat(session, message.chat.id)
        if not merchants:
            await message.answer("本群尚未绑定任何商户，请使用 /add_id <商户短码>")
            return
        lines = [f"- {merchant_display(m)} (id={m.id})" for m in merchants]
        await message.answer("本群已绑定商户：\n" + "\n".join(lines))

    @router.message(Command(commands=["balance"]))
    async def show_benefit_balance(message: Message) -> None:
        if message.chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
            await message.answer("请在群组内使用此命令。")
            return
        async with session_factory() as session:
            merchants = await BenefitBindingService.list_merchants_for_benefit_chat(session, message.chat.id)
        if not merchants:
            await message.answer("本群未绑定商户，请先 /add_id。")
            return
        parts: list[str] = []
        total = Decimal("0")
        for m in merchants:
            bb = Decimal(m.benefit_balance)
            total += bb
            parts.append(f"{merchant_display(m)}: {MoneyService.format_usdt_balance(bb)} USDT")
        await message.answer(
            "分红余额（按商户，USDT）：\n" + "\n".join(parts) + f"\n合计: {MoneyService.format_usdt_balance(total)} USDT"
        )

    @router.message(Command(commands=["clear"]))
    async def clear_benefit_balance(message: Message) -> None:
        if message.chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
            await message.answer("请在群组内使用此命令。")
            return
        async with session_factory() as session:
            merchants = await BenefitBindingService.list_merchants_for_benefit_chat(session, message.chat.id)
            if not merchants:
                await message.answer("本群未绑定商户，请先 /add_id。")
                return
            for m in merchants:
                row = await session.get(Merchant, m.id, with_for_update=True)
                if row is not None:
                    row.benefit_balance = Decimal("0")
            await session.commit()
        await message.answer("已结清本群所绑定商户的分红余额。")

    return router
