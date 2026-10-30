import json
import tempfile
import unittest
from pathlib import Path

from storage import StorageError, UserStore


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "users.json"

    def tearDown(self):
        self.tmp.cleanup()

    def test_creates_new_profile(self):  # 1
        store = UserStore(self.path)
        user = store.get_or_create(111)
        self.assertEqual(user["profile"]["diet"], "unknown")
        self.assertEqual(user["profile"]["allergies"], [])
        self.assertTrue(self.path.exists())

    def test_two_users_are_separate(self):  # 2
        store = UserStore(self.path)
        with store.transaction(1) as u:
            u["profile"]["allergies"].append("peanut")
        store.get_or_create(2)
        self.assertEqual(store.get_user(2)["profile"]["allergies"], [])
        self.assertEqual(store.get_user(1)["profile"]["allergies"], ["peanut"])

    def test_history_survives_restart(self):  # 3
        store = UserStore(self.path)
        with store.transaction(1) as u:
            u["history"].append({"role": "user", "content": "hello", "ts": "t"})
        reloaded = UserStore(self.path)
        self.assertEqual(reloaded.get_user(1)["history"][0]["content"], "hello")

    def test_reset_history_keeps_profile_and_treat(self):  # 4
        store = UserStore(self.path)
        with store.transaction(1) as u:
            u["history"].append({"role": "user", "content": "hi", "ts": "t"})
            u["profile"]["allergies"].append("peanut")
            u["treat"].update(week="2026-W44", used=True)
        store.reset_history(1)
        user = store.get_user(1)
        self.assertEqual(user["history"], [])
        self.assertEqual(user["profile"]["allergies"], ["peanut"])
        self.assertTrue(user["treat"]["used"])

    def test_delete_user(self):  # 5 (storage part)
        store = UserStore(self.path)
        store.get_or_create(1)
        store.get_or_create(2)
        self.assertTrue(store.delete_user(1))
        self.assertIsNone(store.get_user(1))
        self.assertIsNotNone(UserStore(self.path).get_user(2))
        self.assertNotIn('"1"', self.path.read_text())
        self.assertFalse(store.delete_user(1))

    def test_missing_and_empty_file(self):  # 13
        self.assertEqual(UserStore(self.path).user_count(), 0)
        self.path.write_text("   ")
        self.assertEqual(UserStore(self.path).user_count(), 0)

    def test_malformed_json_is_backed_up_not_lost(self):  # 13
        self.path.write_text("{this is not json")
        store = UserStore(self.path)
        self.assertEqual(store.user_count(), 0)
        self.assertIsNotNone(store.recovered_backup)
        self.assertEqual(store.recovered_backup.read_text(), "{this is not json")

    def test_wrong_structure_is_backed_up(self):  # 13
        self.path.write_text(json.dumps([1, 2, 3]))
        store = UserStore(self.path)
        self.assertIsNotNone(store.recovered_backup)

    def test_failed_save_rolls_back(self):
        store = UserStore(self.path)
        store.get_or_create(1)
        store.path = Path(self.tmp.name) / "users.json" / "nope" / "x.json"  # unwritable
        (Path(self.tmp.name) / "users.json").write_text("{}")  # a file where a dir is needed
        with self.assertRaises(StorageError):
            with store.transaction(1) as u:
                u["profile"]["allergies"].append("egg")
        self.assertEqual(store.get_user(1)["profile"]["allergies"], [])


if __name__ == "__main__":
    unittest.main()
