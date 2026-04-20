from __future__ import annotations

from decimal import Decimal

from bot.db.session import create_engine, create_session_factory
from bot.handlers.admin import build_admin_router


def test_admin_u_rate_command_supports_uset_and_setu_aliases() -> None:
    engine = create_engine("sqlite+aiosqlite:///:memory:")
    session_factory = create_session_factory(engine)
    router = build_admin_router(
        session_factory,
        notify_bot=None,
        benefit_bot=None,
        default_u_rate=Decimal("102"),
        default_settle_fee_rate=Decimal("0.065"),
    )

    command_filter = router.observers["message"].handlers[0].filters[0].callback

    assert command_filter.commands == ("uset", "setu")


def test_admin_set_payin_rate_command_is_registered() -> None:
    engine = create_engine("sqlite+aiosqlite:///:memory:")
    session_factory = create_session_factory(engine)
    router = build_admin_router(
        session_factory,
        notify_bot=None,
        benefit_bot=None,
        default_u_rate=Decimal("102"),
        default_settle_fee_rate=Decimal("0.065"),
    )

    command_filter = router.observers["message"].handlers[1].filters[0].callback

    assert command_filter.commands == ("set_payin_rate",)
