"""Weekly treat-meal logic (one per user per week, weeks start on Monday).

A treat meal is counted ONLY when the user confirms they used it, never because
the bot merely suggested one.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict


def week_key(d: date) -> str:
    iso = d.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def next_week_start(d: date) -> date:
    """The Monday that begins the next week."""
    return d + timedelta(days=7 - d.weekday())


def is_available(treat: Dict[str, Any], today: date) -> bool:
    return not (treat.get("used") and treat.get("week") == week_key(today))


def mark_used(treat: Dict[str, Any], today: date) -> bool:
    """Record a confirmed treat meal. Returns False if this week's is already used."""
    if not is_available(treat, today):
        return False
    treat["week"] = week_key(today)
    treat["used"] = True
    treat["used_on"] = today.isoformat()
    return True


def status_text(treat: Dict[str, Any], today: date) -> str:
    if is_available(treat, today):
        return "available this week (not yet used)"
    return f"already used this week (on {treat.get('used_on')}); next one available from {format_date(next_week_start(today))}"


def format_date(d: date) -> str:
    return d.strftime("%A, %d %B %Y")


def already_used_message(today: date) -> str:
    return (
        "You've already enjoyed your treat meal for this week 💚 — no judgment at all! "
        f"Your next one is available from {format_date(next_week_start(today))}. "
        "Meanwhile, I'm happy to suggest tasty, affordable meals you'll enjoy."
    )
