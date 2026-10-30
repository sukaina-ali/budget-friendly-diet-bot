"""Local JSON persistence with one isolated record per Telegram chat.

Limitations of this approach (fine for a class project / small bot):
  * Everything is kept in memory and written to one file (data/users.json).
  * Only ONE bot process should use the file at a time.
  * Data is stored as plain text on your computer (not encrypted).
  * It is not meant for thousands of users; use a real database for that.
"""
from __future__ import annotations

import copy
import json
import logging
import os
import shutil
import tempfile
import threading
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterator, Optional

log = logging.getLogger("diet_bot.storage")

SCHEMA_VERSION = 1


class StorageError(Exception):
    """Raised when records cannot be read or written."""


def new_user_record(now_iso: str = "") -> Dict[str, Any]:
    """A fresh record. Four separate categories: profile, history, meal_state, treat."""
    return {
        "created_at": now_iso,
        "profile": {
            "diet": "unknown",  # vegetarian | non-vegetarian | vegan | unknown
            "allergies": [],
            "dislikes": [],
            "budget": None,
            "preferred_foods": [],
            "health_context": [],  # only what the user said about themselves
        },
        "history": [],  # [{"role": "user"|"assistant", "content": str, "ts": str}]
        "meal_state": {
            "date": None,
            "suggested": [],  # what the BOT suggested (NOT confirmed eaten)
            "eaten": [],  # what the USER said they ate
            "substitutions": [],
            "unavailable_ingredients": [],
        },
        "treat": {"week": None, "used": False, "used_on": None},
    }


def _ensure_schema(user: Dict[str, Any]) -> Dict[str, Any]:
    """Fill in any missing keys (e.g. records written by an older version)."""
    template = new_user_record()
    for key, default in template.items():
        if key not in user or not isinstance(user[key], type(default)) and default is not None:
            user[key] = copy.deepcopy(default)
    for section in ("profile", "meal_state", "treat"):
        for key, default in template[section].items():
            if key not in user[section]:
                user[section][key] = copy.deepcopy(default)
    return user


class UserStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self._lock = threading.RLock()
        self.recovered_backup: Optional[Path] = None
        self._users: Dict[str, Dict[str, Any]] = self._load()

    # ------------------------------------------------------------------ loading
    def _load(self) -> Dict[str, Dict[str, Any]]:
        if not self.path.exists():
            return {}
        try:
            raw = self.path.read_text(encoding="utf-8")
        except OSError as exc:
            raise StorageError(f"Cannot read {self.path}: {exc}") from exc
        if not raw.strip():
            return {}
        try:
            data = json.loads(raw)
            users = data["users"]
            if not isinstance(users, dict):
                raise ValueError("'users' is not an object")
        except (ValueError, KeyError, TypeError) as exc:
            # Do NOT silently overwrite: keep a copy of the damaged file first.
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            backup = self.path.with_name(f"{self.path.name}.corrupt-{stamp}")
            try:
                shutil.copy2(self.path, backup)
            except OSError as copy_exc:
                raise StorageError(
                    f"{self.path} is damaged and could not be backed up: {copy_exc}"
                ) from copy_exc
            self.recovered_backup = backup
            log.error("Storage file was damaged (%s). Backup saved to %s. Starting empty.", exc, backup)
            return {}
        return {str(k): _ensure_schema(v) for k, v in users.items() if isinstance(v, dict)}

    # ------------------------------------------------------------------ saving
    def _write(self) -> None:
        """Atomic write: temp file in the same folder, then os.replace()."""
        payload = {"version": SCHEMA_VERSION, "users": self._users}
        tmp_name = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", dir=self.path.parent, delete=False, suffix=".tmp"
            ) as tmp:
                tmp_name = tmp.name
                json.dump(payload, tmp, ensure_ascii=False, indent=2)
                tmp.flush()
                os.fsync(tmp.fileno())
            os.replace(tmp_name, self.path)
        except (OSError, TypeError, ValueError) as exc:
            if tmp_name and os.path.exists(tmp_name):
                try:
                    os.remove(tmp_name)
                except OSError:
                    pass
            raise StorageError(f"Could not save data to {self.path}: {exc}") from exc

    # ------------------------------------------------------------------ API
    @staticmethod
    def _key(chat_id: Any) -> str:
        return str(chat_id)

    def get_user(self, chat_id: Any) -> Optional[Dict[str, Any]]:
        """Read-only copy of a user's record, or None."""
        with self._lock:
            user = self._users.get(self._key(chat_id))
            return copy.deepcopy(user) if user is not None else None

    @contextmanager
    def transaction(self, chat_id: Any, now_iso: str = "") -> Iterator[Dict[str, Any]]:
        """Edit one user's record; it is saved when the block ends.

        If the block raises or saving fails, the in-memory record is rolled back.
        """
        key = self._key(chat_id)
        with self._lock:
            existed = key in self._users
            snapshot = copy.deepcopy(self._users.get(key))
            user = self._users.setdefault(key, new_user_record(now_iso))
            try:
                yield user
                self._write()
            except BaseException:
                if existed:
                    self._users[key] = snapshot
                else:
                    self._users.pop(key, None)
                raise

    def get_or_create(self, chat_id: Any, now_iso: str = "") -> Dict[str, Any]:
        with self.transaction(chat_id, now_iso):
            pass
        return self.get_user(chat_id)  # type: ignore[return-value]

    def reset_history(self, chat_id: Any) -> None:
        """Clear conversation history ONLY. Profile, meals and treat record are kept."""
        with self.transaction(chat_id) as user:
            user["history"] = []

    def delete_user(self, chat_id: Any) -> bool:
        """Delete everything stored for this user. True only if data existed and the
        deletion was saved. Raises StorageError if saving fails."""
        key = self._key(chat_id)
        with self._lock:
            if key not in self._users:
                return False
            removed = self._users.pop(key)
            try:
                self._write()
            except StorageError:
                self._users[key] = removed
                raise
            return True

    def user_count(self) -> int:
        with self._lock:
            return len(self._users)
