from __future__ import annotations

from pathlib import Path

from bot.db.session import normalize_database_url


def test_normalize_database_url_resolves_relative_sqlite_path_from_project_root() -> None:
    normalized = normalize_database_url("sqlite+aiosqlite:///./data/app.db")

    expected = Path(__file__).resolve().parents[1] / "data" / "app.db"
    assert normalized == f"sqlite+aiosqlite:///{expected}"


def test_normalize_database_url_keeps_absolute_sqlite_path() -> None:
    absolute = "/tmp/tg-bot-online-test.db"

    normalized = normalize_database_url(f"sqlite+aiosqlite:///{absolute}")

    assert normalized == f"sqlite+aiosqlite:///{absolute}"
