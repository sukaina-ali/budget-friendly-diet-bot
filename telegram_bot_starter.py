"""Entry point:  python telegram_bot_starter.py

Telegram handlers only. All diet logic lives in diet_assistant.py.
"""
from __future__ import annotations

import asyncio
import logging
import sys
from typing import List

from telegram import Update
from telegram.constants import ChatAction
from telegram.error import InvalidToken, NetworkError, TimedOut
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from config import ConfigError, load_config
from diet_assistant import DEFAULT_ERROR, DietAssistant
from gemini_client import GeminiClient
from logging_utils import app_log, log_incoming, log_outgoing, log_processing, register_secret, setup_logging
from storage import StorageError, UserStore

TELEGRAM_LIMIT = 4096
_chat_locks: dict = {}


def split_message(text: str, limit: int = 4000) -> List[str]:
    """Split on paragraph/line/space boundaries so each chunk fits Telegram's limit."""
    text = text.strip() or "…"
    chunks: List[str] = []
    while len(text) > limit:
        cut = max(text.rfind("\n\n", 0, limit), text.rfind("\n", 0, limit), text.rfind(" ", 0, limit))
        if cut < limit // 2:
            cut = limit
        chunks.append(text[:cut].rstrip())
        text = text[cut:].lstrip()
    chunks.append(text)
    return chunks


async def _send(update: Update, chat_id, text: str) -> None:
    parts = split_message(text)
    for i, part in enumerate(parts, 1):
        await update.effective_message.reply_text(part)
        log_outgoing(chat_id, part, i, len(parts))  # logged only after it was really sent


async def _keep_typing(bot, chat_id, stop: asyncio.Event) -> None:
    while not stop.is_set():
        try:
            await bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        except Exception:  # noqa: BLE001 - typing indicator is cosmetic
            pass
        try:
            await asyncio.wait_for(stop.wait(), timeout=4)
        except asyncio.TimeoutError:
            pass


def _assistant(context: ContextTypes.DEFAULT_TYPE) -> DietAssistant:
    return context.application.bot_data["assistant"]


async def _command(update: Update, context: ContextTypes.DEFAULT_TYPE, make_reply) -> None:
    chat_id = update.effective_chat.id
    log_incoming(chat_id, update.effective_message.text or "")
    try:
        await _send(update, chat_id, make_reply(_assistant(context), chat_id))
        log_processing(chat_id, True)
    except Exception:  # noqa: BLE001
        app_log.exception("Command failed")
        log_processing(chat_id, False)


async def start_cmd(update, context):
    await _command(update, context, lambda a, c: a.start(c))


async def help_cmd(update, context):
    await _command(update, context, lambda a, c: a.help_text())


async def reset_cmd(update, context):
    await _command(update, context, lambda a, c: a.reset(c))


async def profile_cmd(update, context):
    await _command(update, context, lambda a, c: a.profile_text(c))


async def forgetme_cmd(update, context):
    await _command(update, context, lambda a, c: a.forget(c))


async def unknown_cmd(update, context):
    await _command(update, context, lambda a, c: "Sorry, I don't know that command 🙈 Try /help to see what I can do.")


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    text = update.effective_message.text or ""
    log_incoming(chat_id, text)
    lock = _chat_locks.setdefault(chat_id, asyncio.Lock())  # one message at a time per chat
    async with lock:
        stop = asyncio.Event()
        typing = asyncio.create_task(_keep_typing(context.bot, chat_id, stop))
        ok = True
        try:
            reply = await _assistant(context).handle_message(chat_id, text)
            ok, out = reply.ok, reply.text
        except Exception:  # noqa: BLE001
            app_log.exception("Unexpected error while handling a message")
            ok, out = False, DEFAULT_ERROR
        finally:
            stop.set()
            await typing
        try:
            await _send(update, chat_id, out)
        except Exception:  # noqa: BLE001
            app_log.exception("Could not send reply")
            ok = False
        log_processing(chat_id, ok)


async def on_error(update, context: ContextTypes.DEFAULT_TYPE) -> None:
    app_log.error("Unhandled Telegram error: %s", context.error, exc_info=context.error)


def main() -> None:
    try:
        config = load_config()
    except ConfigError as exc:
        print(f"\nConfiguration problem:\n{exc}\n", file=sys.stderr)
        sys.exit(1)

    register_secret(config.telegram_bot_token)
    register_secret(config.gemini_api_key)
    setup_logging(config.log_level)

    try:
        store = UserStore(config.data_dir / "users.json")
    except StorageError as exc:
        app_log.error("Storage problem: %s", exc)
        sys.exit(1)
    if store.recovered_backup:
        app_log.warning("users.json was damaged; a backup was saved as %s", store.recovered_backup)

    gemini = GeminiClient(
        api_key=config.gemini_api_key,
        model=config.gemini_model,
        timeout_seconds=config.gemini_timeout_seconds,
        temperature=config.gemini_temperature,
        max_output_tokens=config.gemini_max_output_tokens,
    )
    assistant = DietAssistant(store, gemini, config)

    app = Application.builder().token(config.telegram_bot_token).build()
    app.bot_data["assistant"] = assistant
    private = filters.ChatType.PRIVATE
    for name, fn in (("start", start_cmd), ("help", help_cmd), ("reset", reset_cmd), ("profile", profile_cmd), ("forgetme", forgetme_cmd)):
        app.add_handler(CommandHandler(name, fn, filters=private))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.UpdateType.MESSAGE & private, on_text))
    app.add_handler(MessageHandler(filters.COMMAND & private, unknown_cmd))  # registered last
    app.add_error_handler(on_error)

    app_log.info("Bot starting with Gemini model '%s'. Press Ctrl+C to stop.", config.gemini_model)
    try:
        # drop_pending_updates: ignore messages sent while the bot was offline.
        app.run_polling(drop_pending_updates=True)
    except InvalidToken:
        app_log.error("Telegram rejected the bot token. Check TELEGRAM_BOT_TOKEN in your .env file.")
        sys.exit(1)
    except (NetworkError, TimedOut):
        app_log.error("Could not reach Telegram. Check your internet connection and try again.")
        sys.exit(1)
    except KeyboardInterrupt:
        pass
    app_log.info("Bot stopped.")


if __name__ == "__main__":
    main()
