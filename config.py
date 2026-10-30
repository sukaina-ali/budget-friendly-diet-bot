"""Central configuration. All settings and secrets are read here, and only here."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent


class ConfigError(Exception):
    """Raised when required configuration is missing or invalid."""


@dataclass(frozen=True)
class Config:
    # repr=False so the secrets can never appear if a Config is printed or logged.
    telegram_bot_token: str = field(repr=False)
    gemini_api_key: str = field(repr=False)
    gemini_model: str
    timezone_name: str
    timezone: ZoneInfo
    data_dir: Path
    max_history_messages: int
    gemini_timeout_seconds: float
    gemini_temperature: float
    gemini_max_output_tokens: int
    max_regeneration_retries: int
    input_price_per_million: Optional[float]
    output_price_per_million: Optional[float]
    price_currency: str
    log_level: str


def _is_unset(value: Optional[str]) -> bool:
    """True if a value is empty or still the placeholder text from .env.example."""
    if value is None:
        return True
    v = value.strip()
    return v == "" or v.startswith("PASTE_YOUR") or v.startswith("YOUR_")


def _get_number(env: Mapping[str, str], name: str, default, cast, minimum=None):
    raw = env.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        value = cast(raw.strip())
    except ValueError:
        raise ConfigError(f"{name} must be a number, but it is set to '{raw}'.") from None
    if minimum is not None and value < minimum:
        raise ConfigError(f"{name} must be at least {minimum}.")
    return value


def _optional_price(env: Mapping[str, str], name: str) -> Optional[float]:
    return _get_number(env, name, None, float, minimum=0)


def load_config(env: Optional[Mapping[str, str]] = None) -> Config:
    """Load configuration.

    With env=None the real environment is used, after loading the local .env file.
    Tests pass their own dict so no real keys are needed.
    """
    if env is None:
        load_dotenv(PROJECT_ROOT / ".env")
        env = os.environ

    # API KEY LOCATION:
    # The real Telegram token is read from TELEGRAM_BOT_TOKEN in your local .env file.
    telegram_token = env.get("TELEGRAM_BOT_TOKEN")
    # API KEY LOCATION:
    # The real Gemini API key is read from GEMINI_API_KEY in your local .env file.
    gemini_key = env.get("GEMINI_API_KEY")
    # MODEL LOCATION: the Gemini model name is read from GEMINI_MODEL in .env.
    gemini_model = env.get("GEMINI_MODEL")

    missing = [
        name
        for name, value in (
            ("TELEGRAM_BOT_TOKEN", telegram_token),
            ("GEMINI_API_KEY", gemini_key),
            ("GEMINI_MODEL", gemini_model),
        )
        if _is_unset(value)
    ]
    if missing:
        raise ConfigError(
            "These settings are missing or still contain placeholder text: "
            + ", ".join(missing)
            + ".\nCopy .env.example to .env and fill in your own values "
            "(see the README, sections 'Telegram BotFather setup' and 'Gemini API setup')."
        )

    tz_name = (env.get("TIMEZONE") or "Asia/Karachi").strip()
    try:
        tz = ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, ValueError):
        raise ConfigError(
            f"TIMEZONE '{tz_name}' is not a valid timezone name (example: Asia/Karachi). "
            "If it is valid, run: pip install tzdata"
        ) from None

    data_dir = Path((env.get("DATA_DIR") or "data").strip())
    if not data_dir.is_absolute():
        data_dir = PROJECT_ROOT / data_dir

    return Config(
        telegram_bot_token=telegram_token.strip(),
        gemini_api_key=gemini_key.strip(),
        gemini_model=gemini_model.strip(),
        timezone_name=tz_name,
        timezone=tz,
        data_dir=data_dir,
        max_history_messages=_get_number(env, "MAX_HISTORY_MESSAGES", 12, int, 2),
        gemini_timeout_seconds=_get_number(env, "GEMINI_TIMEOUT_SECONDS", 30.0, float, 1),
        gemini_temperature=_get_number(env, "GEMINI_TEMPERATURE", 0.6, float, 0),
        gemini_max_output_tokens=_get_number(env, "GEMINI_MAX_OUTPUT_TOKENS", 2048, int, 64),
        max_regeneration_retries=_get_number(env, "MAX_REGENERATION_RETRIES", 2, int, 0),
        input_price_per_million=_optional_price(env, "INPUT_PRICE_PER_MILLION"),
        output_price_per_million=_optional_price(env, "OUTPUT_PRICE_PER_MILLION"),
        price_currency=(env.get("PRICE_CURRENCY") or "USD").strip(),
        log_level=(env.get("LOG_LEVEL") or "INFO").strip().upper(),
    )
