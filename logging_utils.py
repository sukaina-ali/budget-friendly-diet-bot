"""Readable terminal logging. Secrets are redacted from every log line."""
from __future__ import annotations

import logging
import sys
from typing import Optional

conversation_log = logging.getLogger("diet_bot.conversation")
app_log = logging.getLogger("diet_bot")

_SECRETS: set = set()


def register_secret(value: Optional[str]) -> None:
    """Any registered value is replaced by *** in all log output."""
    if value and len(value) >= 6:
        _SECRETS.add(value)


class RedactingFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        text = super().format(record)  # includes exception tracebacks
        for secret in _SECRETS:
            text = text.replace(secret, "***")
        return text


def setup_logging(level: str = "INFO") -> None:
    """Console logging. Safe to call more than once."""
    if app_log.handlers:
        return
    lvl = getattr(logging, level.upper(), logging.INFO)
    datefmt = "%Y-%m-%d %H:%M:%S"

    tech = logging.StreamHandler(sys.stdout)
    tech.setFormatter(RedactingFormatter("[%(asctime)s] %(levelname)s | %(message)s", datefmt))
    app_log.addHandler(tech)
    app_log.setLevel(lvl)

    conv = logging.StreamHandler(sys.stdout)
    conv.setFormatter(RedactingFormatter("[%(asctime)s] %(message)s", datefmt))
    conversation_log.addHandler(conv)
    conversation_log.setLevel(logging.INFO)
    conversation_log.propagate = False

    # httpx logs full request URLs at INFO level and Telegram URLs contain the bot
    # token, so keep these libraries quiet.
    for noisy in ("httpx", "httpcore", "telegram", "hpack"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def log_incoming(chat_id, text: str) -> None:
    conversation_log.info("INCOMING | Chat: %s\nUser: %s", chat_id, text)


def log_outgoing(chat_id, text: str, part: int = 1, parts: int = 1) -> None:
    suffix = f" (part {part}/{parts})" if parts > 1 else ""
    conversation_log.info("OUTGOING | Chat: %s%s\nBot: %s", chat_id, suffix, text)


def log_processing(chat_id, ok: bool) -> None:
    conversation_log.info("PROCESSING | Chat: %s | Status: %s", chat_id, "SUCCESS" if ok else "FAILED")


def _fmt(value) -> str:
    return "unavailable" if value is None else str(value)


def log_usage(chat_id, result, cost_text: str) -> None:
    status = "SUCCESS" if result.ok else f"FAILED ({result.error_kind})"
    conversation_log.info(
        "GEMINI USAGE | Chat: %s\nInput tokens: %s\nOutput tokens: %s\nTotal tokens: %s\n"
        "Duration: %.1f seconds\nStatus: %s\n%s",
        chat_id,
        _fmt(result.input_tokens),
        _fmt(result.output_tokens),
        _fmt(result.total_tokens),
        result.duration_seconds,
        status,
        cost_text,
    )
