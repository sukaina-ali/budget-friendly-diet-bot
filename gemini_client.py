"""Thin wrapper around the official google-genai SDK.

* Uses the SDK's native async client (client.aio), so Telegram's event loop is
  never blocked.
* Never fabricates a reply: on any failure it returns GeminiResult(ok=False).
* Never puts the API key in results or logs.
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import httpx
from google import genai
from google.genai import errors, types

log = logging.getLogger("diet_bot.gemini")


@dataclass
class GeminiResult:
    ok: bool
    text: str = ""
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    duration_seconds: float = 0.0
    error_kind: Optional[str] = None
    error_detail: str = ""  # technical detail: for logs only, never shown to users


def extract_usage(response: Any) -> Tuple[Optional[int], Optional[int], Optional[int]]:
    """(input, output, total) from response.usage_metadata; None where unavailable."""
    meta = getattr(response, "usage_metadata", None)
    if meta is None:
        return None, None, None
    input_tokens = getattr(meta, "prompt_token_count", None)
    output_tokens = getattr(meta, "candidates_token_count", None)
    total = getattr(meta, "total_token_count", None)
    if total is None and input_tokens is not None and output_tokens is not None:
        total = input_tokens + output_tokens
    return input_tokens, output_tokens, total


def classify_exception(exc: BaseException) -> Tuple[str, str]:
    """Map an exception to a short error kind (see DietAssistant for user messages)."""
    detail = f"{type(exc).__name__}: {exc}"
    low = str(exc).lower()
    if isinstance(exc, (asyncio.TimeoutError, TimeoutError, httpx.TimeoutException)):
        return "timeout", detail
    if isinstance(exc, errors.APIError):
        code = getattr(exc, "code", None)
        if "api key" in low or code in (401, 403):
            return "invalid_key", detail
        if code == 429 or "resource_exhausted" in low or "quota" in low:
            return "rate_limit", detail
        if code == 404 or "is not found" in low or "not supported for" in low:
            return "model_unavailable", detail
        if isinstance(code, int) and 500 <= code < 600:
            return "server", detail
        return "api_error", detail
    if isinstance(exc, (httpx.TransportError, ConnectionError, OSError)):
        return "network", detail
    return "unknown", detail


def estimate_cost(
    result: GeminiResult,
    input_price_per_million: Optional[float],
    output_price_per_million: Optional[float],
    currency: str,
) -> str:
    """Optional, approximate cost line for the logs. Prices come only from config."""
    if input_price_per_million is None or output_price_per_million is None:
        return "Cost estimate unavailable until pricing is configured."
    if result.input_tokens is None or (result.output_tokens is None and result.total_tokens is None):
        return "Cost estimate unavailable (token usage not reported)."
    # Output side = everything after the prompt (also covers any "thinking" tokens).
    if result.total_tokens is not None:
        out_tokens = max(result.total_tokens - result.input_tokens, 0)
    else:
        out_tokens = result.output_tokens or 0
    cost = (
        result.input_tokens * input_price_per_million + out_tokens * output_price_per_million
    ) / 1_000_000
    return f"Estimated cost: {cost:.6f} {currency} (estimate only; may differ from your actual bill)"


class GeminiClient:
    def __init__(
        self,
        api_key: str,
        model: str,
        timeout_seconds: float = 30.0,
        temperature: float = 0.6,
        max_output_tokens: int = 2048,
        client: Any = None,
    ):
        self._api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens
        # `client` can be injected in tests; otherwise build the real SDK client.
        self._client = client or genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=int(timeout_seconds * 1000)),  # milliseconds
        )

    @staticmethod
    def _build_contents(history: List[Dict[str, str]], user_message: str) -> list:
        contents = []
        for item in history:
            role = "model" if item.get("role") == "assistant" else "user"
            if not contents and role == "model":
                continue  # conversation must start with a user turn
            contents.append(types.Content(role=role, parts=[types.Part(text=item["content"])]))
        contents.append(types.Content(role="user", parts=[types.Part(text=user_message)]))
        return contents

    async def generate(
        self, system_instruction: str, history: List[Dict[str, str]], user_message: str
    ) -> GeminiResult:
        start = time.monotonic()
        response = None
        try:
            response = await asyncio.wait_for(
                self._client.aio.models.generate_content(
                    model=self.model,
                    contents=self._build_contents(history, user_message),
                    config=types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        temperature=self.temperature,
                        max_output_tokens=self.max_output_tokens,
                    ),
                ),
                timeout=self.timeout_seconds + 5,
            )
        except Exception as exc:  # noqa: BLE001 - we classify everything, never crash the bot
            kind, detail = classify_exception(exc)
            detail = detail.replace(self._api_key, "***")
            log.error("Gemini request failed (%s): %s", kind, detail)
            return GeminiResult(
                ok=False,
                duration_seconds=time.monotonic() - start,
                error_kind=kind,
                error_detail=detail,
            )

        duration = time.monotonic() - start
        in_tok, out_tok, total = extract_usage(response)
        try:
            text = (response.text or "").strip()
        except Exception:  # noqa: BLE001
            text = ""
        if not text:
            finish = None
            try:
                finish = response.candidates[0].finish_reason
            except Exception:  # noqa: BLE001
                pass
            log.error("Gemini returned no text (finish_reason=%s)", finish)
            return GeminiResult(
                ok=False,
                input_tokens=in_tok,
                output_tokens=out_tok,
                total_tokens=total,
                duration_seconds=duration,
                error_kind="empty_response",
                error_detail=f"empty response, finish_reason={finish}",
            )
        return GeminiResult(
            ok=True,
            text=text,
            input_tokens=in_tok,
            output_tokens=out_tok,
            total_tokens=total,
            duration_seconds=duration,
        )
