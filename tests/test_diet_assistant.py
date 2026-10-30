import unittest
from datetime import datetime, timedelta

from diet_assistant import GREETING, DietAssistant
from gemini_client import GeminiResult
from tests.helpers import TZ, Fixture


class AssistantTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.fx = Fixture()
        self.addCleanup(self.fx.cleanup)

    async def test_start_greeting_exact_and_keeps_data(self):
        self.assertTrue(self.fx.assistant.start(1).startswith("Hi! 👋 Welcome to your budget-friendly AI Diet Buddy! 🥗"))
        self.assertEqual(self.fx.assistant.start(1), GREETING)
        await self.fx.assistant.handle_message(1, "I'm allergic to peanuts")
        self.fx.assistant.start(1)  # /start again must not erase data
        self.assertEqual(self.fx.store.get_user(1)["profile"]["allergies"], ["peanut"])

    async def test_history_saved_and_reset_keeps_profile(self):  # 3, 4
        await self.fx.assistant.handle_message(1, "I'm allergic to peanuts. Give me today's meal plan.")
        self.assertEqual(len(self.fx.store.get_user(1)["history"]), 2)
        self.assertIn("preferences", self.fx.assistant.reset(1))
        user = self.fx.store.get_user(1)
        self.assertEqual(user["history"], [])
        self.assertEqual(user["profile"]["allergies"], ["peanut"])

    async def test_forgetme_deletes_everything(self):  # 5
        await self.fx.assistant.handle_message(1, "I had paratha and chai for breakfast")
        self.assertIn("deleted", self.fx.assistant.forget(1))
        self.assertIsNone(self.fx.store.get_user(1))
        self.assertIn("nothing to delete", self.fx.assistant.forget(1))

    async def test_allergy_saved_and_enforced(self):  # 6
        self.fx.gemini.replies = ["Try chicken with peanut sauce.", "Try daal, roti and salad."]
        reply = await self.fx.assistant.handle_message(1, "I'm allergic to peanuts, what should I eat for lunch?")
        self.assertEqual(len(self.fx.gemini.calls), 2)  # first draft rejected, regenerated
        self.assertIn("CORRECTION", self.fx.gemini.calls[1][0])
        self.assertNotIn("peanut sauce", reply.text)
        self.assertIn("peanut", self.fx.gemini.calls[0][0])  # allergy is in the prompt

    async def test_allergy_fallback_when_model_keeps_violating(self):  # 6
        self.fx.gemini.replies = ["Peanut chutney with roti."]
        reply = await self.fx.assistant.handle_message(1, "I'm allergic to peanuts. Lunch ideas?")
        self.assertEqual(len(self.fx.gemini.calls), 3)  # 1 try + 2 retries (limited)
        self.assertNotIn("Peanut chutney", reply.text)
        self.assertEqual(self.fx.store.get_user(1)["history"], [])  # bad reply not stored

    async def test_vegetarian_respected(self):  # 7
        self.fx.gemini.replies = ["Grilled chicken and salad.", "Moong daal, roti and salad."]
        reply = await self.fx.assistant.handle_message(1, "I want vegetarian meals from now on")
        self.assertEqual(self.fx.store.get_user(1)["profile"]["diet"], "vegetarian")
        self.assertEqual(reply.text, "Moong daal, roti and salad.")

    async def test_reported_meal_recorded_as_eaten_not_suggested(self):  # 8, 9
        await self.fx.assistant.handle_message(1, "Give me today's meal plan")
        state = self.fx.store.get_user(1)["meal_state"]
        self.assertEqual(len(state["suggested"]), 1)
        self.assertEqual(state["eaten"], [])  # suggestion != eaten
        await self.fx.assistant.handle_message(1, "I had paratha and chai for breakfast.")
        state = self.fx.store.get_user(1)["meal_state"]
        self.assertEqual(state["eaten"][0]["description"], "paratha and chai")
        self.assertIn("CONFIRMED eating today: breakfast: paratha and chai", self.fx.gemini.calls[-1][0])

    async def test_next_day_does_not_carry_over(self):  # Scenario G
        await self.fx.assistant.handle_message(1, "Give me today's meal plan. I had roti for breakfast")
        self.fx.now += timedelta(days=1)
        await self.fx.assistant.handle_message(1, "Give me today's meal plan")
        state = self.fx.store.get_user(1)["meal_state"]
        self.assertEqual(state["eaten"], [])
        self.assertEqual(len(state["suggested"]), 1)

    async def test_treat_once_per_week_and_resets(self):  # 10, 11, 12
        a = self.fx.assistant
        r = await a.handle_message(1, "Can I have a treat meal?")  # asking does not use it
        self.assertFalse(self.fx.store.get_user(1)["treat"]["used"])
        await a.handle_message(1, "I had biryani as my treat meal")
        self.assertTrue(self.fx.store.get_user(1)["treat"]["used"])
        calls_before = len(self.fx.gemini.calls)
        r = await a.handle_message(1, "Can I have another treat meal?")
        self.assertIn("already enjoyed", r.text)
        self.assertEqual(len(self.fx.gemini.calls), calls_before)  # answered without AI
        self.assertIn("Monday, 02 November 2026", r.text)
        self.fx.now = datetime(2026, 11, 2, 9, 0, tzinfo=TZ)  # next week
        await a.handle_message(1, "I had pizza as my treat meal")
        self.assertEqual(self.fx.store.get_user(1)["treat"]["week"], "2026-W45")

    async def test_gemini_failure_does_not_crash(self):  # 15
        self.fx.gemini.replies = [GeminiResult(ok=False, error_kind="rate_limit", error_detail="429")]
        reply = await self.fx.assistant.handle_message(1, "Give me today's meal plan")
        self.assertFalse(reply.ok)
        self.assertIn("try again", reply.text.lower())
        self.assertEqual(self.fx.store.get_user(1)["history"], [])

    async def test_token_usage_logged(self):  # 16
        with self.assertLogs("diet_bot.conversation", level="INFO") as logs:
            await self.fx.assistant.handle_message(1, "Hello")
        out = "\n".join(logs.output)
        self.assertIn("Input tokens: 420", out)
        self.assertIn("Output tokens: 185", out)
        self.assertIn("Total tokens: 605", out)
        self.assertIn("Cost estimate unavailable until pricing is configured.", out)

    async def test_missing_usage_logged_as_unavailable(self):  # 16
        self.fx.gemini.replies = [GeminiResult(ok=False, error_kind="network")]
        with self.assertLogs("diet_bot.conversation", level="INFO") as logs:
            await self.fx.assistant.handle_message(1, "Hello")
        self.assertIn("Input tokens: unavailable", "\n".join(logs.output))

    async def test_users_never_share_prompts(self):  # 17
        await self.fx.assistant.handle_message(1, "I'm allergic to sesame. SECRET_USER_ONE_MESSAGE")
        await self.fx.assistant.handle_message(2, "Give me today's meal plan")
        system, history, message = self.fx.gemini.calls[-1]
        blob = system + str(history) + message
        self.assertNotIn("SECRET_USER_ONE_MESSAGE", blob)
        self.assertNotIn("sesame", blob)

    async def test_unsafe_request_refused_without_ai(self):
        reply = await self.fx.assistant.handle_message(1, "I want to starve myself to lose weight fast")
        self.assertEqual(self.fx.gemini.calls, [])
        self.assertIn("can't help with extreme restriction", reply.text)

    async def test_profile_shows_unknown_not_guesses(self):
        self.fx.assistant.start(1)
        text = self.fx.assistant.profile_text(1)
        self.assertIn("Dietary preference: unknown", text)
        self.assertIn("Allergies: unknown", text)

    async def test_history_limit(self):
        for i in range(20):
            await self.fx.assistant.handle_message(1, f"message {i}")
        self.assertLessEqual(len(self.fx.store.get_user(1)["history"]), self.fx.config.max_history_messages)


if __name__ == "__main__":
    unittest.main()
