from __future__ import annotations

from collections.abc import Awaitable, Callable
from time import monotonic

from aiogram import BaseMiddleware
from aiogram.types import Message

from bot.handlers.common import command_matches


class PayoutRateLimitMiddleware(BaseMiddleware):
    def __init__(self, cooldown_seconds: float = 3.0) -> None:
        self.cooldown_seconds = cooldown_seconds
        self._last_seen_by_chat: dict[int, float] = {}

    async def __call__(
        self,
        handler: Callable[[Message, dict], Awaitable[object]],
        event: Message,
        data: dict,
    ) -> object:
        if not command_matches(event.text or "", "payout"):
            return await handler(event, data)

        chat = event.chat
        if chat is None:
            return await handler(event, data)

        now = monotonic()
        last_seen = self._last_seen_by_chat.get(chat.id)
        if last_seen is not None and now - last_seen < self.cooldown_seconds:
            await event.answer("同一商户群 3 秒内不能重复发起 /payout。")
            return None

        self._last_seen_by_chat[chat.id] = now
        return await handler(event, data)
