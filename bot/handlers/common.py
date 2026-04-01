from __future__ import annotations

from decimal import Decimal, InvalidOperation


def extract_command_name(text: str) -> str | None:
    stripped = text.strip()
    if not stripped.startswith("/"):
        return None
    command = stripped.split(maxsplit=1)[0]
    return command[1:].split("@", maxsplit=1)[0]


def command_matches(text: str, command_name: str) -> bool:
    return extract_command_name(text) == command_name


def split_command_args(text: str) -> list[str]:
    parts = text.strip().split()
    return parts[1:]


def parse_decimal_arg(raw_value: str) -> Decimal:
    try:
        value = Decimal(raw_value.strip())
    except InvalidOperation as exc:
        raise ValueError("参数格式不正确。") from exc
    if value <= 0:
        raise ValueError("参数必须大于 0。")
    return value


def parse_fee_rate_arg(raw_value: str) -> Decimal:
    try:
        value = Decimal(raw_value.strip())
    except InvalidOperation as exc:
        raise ValueError("参数格式不正确。") from exc
    if value < 0:
        raise ValueError("费率不能为负。")
    if value > 1:
        value = value / Decimal(100)
    if value >= 1:
        raise ValueError("费率必须小于 100%。")
    return value


def parse_dividend_rate_arg(raw_value: str) -> Decimal:
    try:
        value = Decimal(raw_value.strip())
    except InvalidOperation as exc:
        raise ValueError("参数格式不正确。") from exc
    if value < 0:
        raise ValueError("分红率不能为负。")
    if value >= 1:
        value = value / Decimal(100)
    if value > 1:
        raise ValueError("分红率不能大于 100%。")
    return value
