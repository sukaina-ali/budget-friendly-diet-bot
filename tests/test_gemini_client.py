import asyncio
import unittest
from types import SimpleNamespace

from gemini_client import GeminiClient, GeminiResult, classify_exception, estimate_cost, extract_usage


class FailingModels:
    def __init__(self, exc):
        self.exc = exc

    async def generate_content(self, **kwargs):
        raise self.exc


class OkModels:
    async def generate_content(self, **kwargs):
        usage = SimpleNamespace(prompt_token_count=10, candidates_token_count=5, total_token_count=15)
        return SimpleNamespace(text="hello", usage_metadata=usage)


class EmptyModels:
    async def generate_content(self, **kwargs):
        return SimpleNamespace(text=None, usage_metadata=SimpleNamespace(prompt_token_count=7, candidates_token_count=0, total_token_count=7), candidates=[])


def client_with(models):
    fake = SimpleNamespace(aio=SimpleNamespace(models=models))
    return GeminiClient("SECRET_KEY_123", "m", timeout_seconds=1, client=fake)


class GeminiClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_success_records_usage(self):  # 16
        res = await client_with(OkModels()).generate("sys", [], "hi")
        self.assertTrue(res.ok)
        self.assertEqual((res.input_tokens, res.output_tokens, res.total_tokens), (10, 5, 15))

    async def test_failure_returns_result_not_exception(self):  # 15
        res = await client_with(FailingModels(ConnectionError("boom SECRET_KEY_123"))).generate("s", [], "hi")
        self.assertFalse(res.ok)
        self.assertEqual(res.error_kind, "network")
        self.assertNotIn("SECRET_KEY_123", res.error_detail)
        self.assertIsNone(res.input_tokens)

    async def test_timeout(self):  # 15
        res = await client_with(FailingModels(asyncio.TimeoutError())).generate("s", [], "hi")
        self.assertEqual(res.error_kind, "timeout")

    async def test_empty_response_keeps_available_usage(self):  # 15, 16
        res = await client_with(EmptyModels()).generate("s", [], "hi")
        self.assertFalse(res.ok)
        self.assertEqual(res.error_kind, "empty_response")
        self.assertEqual(res.input_tokens, 7)


class HelperTests(unittest.TestCase):
    def test_extract_usage_missing(self):
        self.assertEqual(extract_usage(SimpleNamespace(usage_metadata=None)), (None, None, None))

    def test_extract_usage_computes_total(self):
        meta = SimpleNamespace(prompt_token_count=3, candidates_token_count=4, total_token_count=None)
        self.assertEqual(extract_usage(SimpleNamespace(usage_metadata=meta)), (3, 4, 7))

    def test_classify_generic(self):
        self.assertEqual(classify_exception(ValueError("x"))[0], "unknown")

    def test_cost_unavailable_without_prices(self):
        res = GeminiResult(ok=True, input_tokens=100, output_tokens=50, total_tokens=150)
        self.assertIn("unavailable until pricing is configured", estimate_cost(res, None, None, "USD"))

    def test_cost_with_prices(self):
        res = GeminiResult(ok=True, input_tokens=1_000_000, output_tokens=0, total_tokens=2_000_000)
        self.assertIn("3.000000 USD", estimate_cost(res, 1.0, 2.0, "USD"))


if __name__ == "__main__":
    unittest.main()
