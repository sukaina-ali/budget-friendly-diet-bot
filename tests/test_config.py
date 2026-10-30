import unittest

from config import ConfigError, load_config

GOOD = {"TELEGRAM_BOT_TOKEN": "123:abc_token", "GEMINI_API_KEY": "key-abcdef", "GEMINI_MODEL": "some-model"}


class ConfigTests(unittest.TestCase):
    def test_loads_valid_config(self):
        cfg = load_config(dict(GOOD))
        self.assertEqual(cfg.gemini_model, "some-model")
        self.assertEqual(cfg.timezone_name, "Asia/Karachi")
        self.assertNotIn("key-abcdef", repr(cfg))  # secrets never appear in repr

    def test_missing_keys_raise_helpful_error(self):  # 14
        with self.assertRaises(ConfigError) as ctx:
            load_config({})
        self.assertIn("TELEGRAM_BOT_TOKEN", str(ctx.exception))
        self.assertIn("GEMINI_API_KEY", str(ctx.exception))

    def test_placeholder_values_count_as_missing(self):  # 14
        env = dict(GOOD, GEMINI_API_KEY="PASTE_YOUR_GEMINI_API_KEY_HERE", GEMINI_MODEL="YOUR_AVAILABLE_GEMINI_MODEL")
        with self.assertRaises(ConfigError) as ctx:
            load_config(env)
        self.assertIn("GEMINI_MODEL", str(ctx.exception))

    def test_bad_timezone_and_number(self):
        with self.assertRaises(ConfigError):
            load_config(dict(GOOD, TIMEZONE="Not/AZone"))
        with self.assertRaises(ConfigError):
            load_config(dict(GOOD, MAX_HISTORY_MESSAGES="abc"))

    def test_pricing_optional(self):
        self.assertIsNone(load_config(dict(GOOD)).input_price_per_million)


if __name__ == "__main__":
    unittest.main()
