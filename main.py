from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher

from bot.config import load_settings
from bot.db.session import create_engine, create_session_factory
from bot.handlers.admin import build_admin_router
from bot.handlers.notify import build_notify_router
from bot.middlewares.rate_limit import PayoutRateLimitMiddleware


async def run() -> None:
    settings = load_settings()
    engine = create_engine(settings.database_url)
    session_factory = create_session_factory(engine)

    admin_bot = Bot(token=settings.admin_bot_token)
    notify_bot = Bot(token=settings.notify_bot_token)

    admin_dispatcher = Dispatcher()
    admin_dispatcher.include_router(
        build_admin_router(session_factory, notify_bot, settings.default_u_rate)
    )

    notify_dispatcher = Dispatcher()
    notify_router = build_notify_router(session_factory, settings.default_u_rate)
    notify_router.message.middleware(PayoutRateLimitMiddleware())
    notify_dispatcher.include_router(notify_router)

    try:
        await asyncio.gather(
            admin_dispatcher.start_polling(admin_bot),
            notify_dispatcher.start_polling(notify_bot),
        )
    finally:
        await admin_bot.session.close()
        await notify_bot.session.close()
        await engine.dispose()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run())
