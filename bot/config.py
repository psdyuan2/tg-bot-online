from __future__ import annotations

import os
from dataclasses import dataclass
from decimal import Decimal

from dotenv import load_dotenv


@dataclass(frozen=True, slots=True)
class Settings:
    admin_bot_token: str
    notify_bot_token: str
    benefit_bot_token: str
    database_url: str
    default_u_rate: Decimal
    default_settle_fee_rate: Decimal


def _load_env() -> None:
    load_dotenv()


def load_database_url() -> str:
    _load_env()
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        raise ValueError("DATABASE_URL is required.")
    return database_url


def load_settings() -> Settings:
    _load_env()

    admin_bot_token = os.getenv("ADMIN_BOT_TOKEN", "").strip()
    notify_bot_token = os.getenv("NOTIFY_BOT_TOKEN", "").strip()
    benefit_bot_token = os.getenv("BENEFIT_BOT_TOKEN", "").strip()
    database_url = load_database_url()

    if not admin_bot_token or not notify_bot_token or not benefit_bot_token:
        raise ValueError("ADMIN_BOT_TOKEN, NOTIFY_BOT_TOKEN and BENEFIT_BOT_TOKEN are required.")

    return Settings(
        admin_bot_token=admin_bot_token,
        notify_bot_token=notify_bot_token,
        benefit_bot_token=benefit_bot_token,
        database_url=database_url,
        default_u_rate=Decimal(os.getenv("DEFAULT_U_RATE", "7.20")),
        default_settle_fee_rate=Decimal(os.getenv("DEFAULT_SETTLE_FEE_RATE", "0.065")),
    )
