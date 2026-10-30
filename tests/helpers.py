"""Shared test helpers (no real API calls anywhere)."""
import tempfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from config import load_config
from diet_assistant import DietAssistant
from gemini_client import GeminiResult
from storage import UserStore

TZ = ZoneInfo("Asia/Karachi")


def make_config(tmp: Path):
    return load_config(
        {
            "TELEGRAM_BOT_TOKEN": "123456:TEST_TELEGRAM_TOKEN_NOT_REAL",
            "GEMINI_API_KEY": "TEST_GEMINI_KEY_NOT_REAL",
            "GEMINI_MODEL": "test-model",
            "DATA_DIR": str(tmp),
        }
    )


class FakeGemini:
    """Stands in for GeminiClient. `replies` are returned in order (last one repeats)."""

    def __init__(self, replies=None):
        self.replies = list(replies or ["Here is a simple plan: daal, roti and salad."])
        self.calls = []  # (system_instruction, history, user_message)

    async def generate(self, system_instruction, history, user_message):
        self.calls.append((system_instruction, list(history), user_message))
        item = self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]
        if isinstance(item, GeminiResult):
            return item
        return GeminiResult(ok=True, text=item, input_tokens=420, output_tokens=185, total_tokens=605, duration_seconds=2.1)


class Fixture:
    def __init__(self, replies=None, now=None):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "users.json"
        self.config = make_config(Path(self.tmp.name))
        self.store = UserStore(self.path)
        self.gemini = FakeGemini(replies)
        self.now = now or datetime(2026, 10, 29, 10, 0, tzinfo=TZ)
        self.assistant = DietAssistant(self.store, self.gemini, self.config, clock=lambda: self.now)

    def cleanup(self):
        self.tmp.cleanup()
