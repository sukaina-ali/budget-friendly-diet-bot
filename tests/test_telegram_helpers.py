import unittest

from telegram_bot_starter import split_message


class SplitMessageTests(unittest.TestCase):
    def test_short_message_unchanged(self):
        self.assertEqual(split_message("hello"), ["hello"])

    def test_long_message_split_within_limit(self):
        text = ("word " * 3000).strip()
        parts = split_message(text, limit=4000)
        self.assertGreater(len(parts), 1)
        self.assertTrue(all(len(p) <= 4000 for p in parts))
        self.assertEqual(" ".join(parts).split(), text.split())


if __name__ == "__main__":
    unittest.main()
