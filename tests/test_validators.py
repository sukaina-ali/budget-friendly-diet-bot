import unittest
from datetime import date

import intents
import meal_framework
import treat_tracker
import validators


class AllergyAndDietTests(unittest.TestCase):
    def test_allergy_detected(self):  # 6
        hits = validators.find_allergen_hits("Try chicken with peanut sauce.", ["peanut"])
        self.assertEqual(hits[0].kind, "allergy")

    def test_allergy_alias_and_family(self):  # 6
        self.assertTrue(validators.find_allergen_hits("Add some almonds on top.", ["nuts"]))
        self.assertTrue(validators.find_allergen_hits("Add groundnuts on top.", ["peanuts"]))
        self.assertTrue(validators.find_allergen_hits("Serve with dahi.", ["dairy"]))

    def test_avoidance_statement_is_allowed(self):  # 6
        self.assertEqual(validators.find_allergen_hits("I left out peanuts. Have daal and roti.", ["peanut"]), [])

    def test_vegetarian_blocks_meat_fish_egg(self):  # 7
        for food in ("grilled chicken", "fish curry", "a vegetable omelette"):
            self.assertTrue(validators.find_diet_hits(f"Lunch: {food} with salad.", "vegetarian"), food)
        self.assertEqual(validators.find_diet_hits("Lunch: moong daal, roti and salad.", "vegetarian"), [])

    def test_vegan_blocks_dairy(self):
        self.assertTrue(validators.find_diet_hits("Have plain dahi.", "vegan"))

    def test_red_meat_excluded_unless_user_asks(self):
        self.assertTrue(validators.check_response("Try mutton karahi.", {"diet": "unknown", "allergies": []}))
        self.assertEqual(validators.check_response("Try mutton karahi.", {"diet": "unknown", "allergies": []}, "I want mutton karahi"), [])

    def test_standard_framework_has_no_red_meat_or_cure_claims(self):
        text = meal_framework.format_schedule()
        self.assertEqual(validators._find_terms(text, validators.RED_MEAT), None)
        self.assertEqual(validators.find_cure_claims(text), [])


class ClaimTests(unittest.TestCase):
    def test_cure_claim_blocked(self):
        self.assertTrue(validators.find_cure_claims("Lemon water cures insulin resistance."))
        self.assertTrue(validators.find_cure_claims("This plan will reverse your insulin resistance!"))

    def test_negated_claim_allowed(self):
        self.assertEqual(validators.find_cure_claims("No food can cure insulin resistance."), [])

    def test_nutrition_numbers_blocked(self):
        self.assertTrue(validators.find_unsupported_claims("This lunch has 450 calories."))
        self.assertTrue(validators.find_unsupported_claims("About 20 g of protein."))
        self.assertEqual(validators.find_unsupported_claims("One roti and a small bowl of daal."), [])

    def test_compensation_blocked(self):
        self.assertTrue(validators.find_compensation_advice("Skip dinner to make up for it."))
        self.assertEqual(validators.find_compensation_advice("Please don't skip dinner."), [])

    def test_unsafe_requests(self):
        self.assertTrue(validators.check_user_request("I want to starve myself for a week"))
        self.assertTrue(validators.check_user_request("give me a 600 calories diet plan"))
        self.assertFalse(validators.check_user_request("Give me today's meal plan"))


class IntentTests(unittest.TestCase):
    def test_allergies(self):
        self.assertEqual(intents.extract_allergies("I'm allergic to peanuts and eggs"), ["peanuts", "eggs"])
        self.assertEqual(intents.extract_allergies("I have a peanut allergy"), ["peanut"])
        self.assertEqual(intents.extract_allergies("I'm not allergic to anything"), [])

    def test_diet(self):
        self.assertEqual(intents.extract_diet("I want vegetarian meals from now on"), "vegetarian")
        self.assertEqual(intents.extract_diet("I'm not vegetarian"), "non-vegetarian")
        self.assertIsNone(intents.extract_diet("Give me a vegetarian plan"))

    def test_reported_meal(self):
        self.assertEqual(intents.extract_reported_meals("I had paratha and chai for breakfast."), [("breakfast", "paratha and chai")])

    def test_health_context_only_self_reported(self):
        self.assertEqual(intents.extract_health_context("I have insulin resistance"), "insulin resistance")
        self.assertIsNone(intents.extract_health_context("Does lemon water cure insulin resistance?"))

    def test_treat_intent(self):
        self.assertEqual(intents.treat_intent("Can I have a treat meal?"), "requested")
        self.assertEqual(intents.treat_intent("I had biryani as my treat meal"), "used")
        self.assertIsNone(intents.treat_intent("Give me a plan"))


class TreatTrackerTests(unittest.TestCase):
    def test_one_per_week(self):  # 10, 11
        treat = {"week": None, "used": False, "used_on": None}
        mon, fri = date(2026, 10, 26), date(2026, 10, 30)
        self.assertTrue(treat_tracker.mark_used(treat, mon))
        self.assertFalse(treat_tracker.mark_used(treat, fri))

    def test_new_week_resets(self):  # 12
        treat = {"week": None, "used": False, "used_on": None}
        treat_tracker.mark_used(treat, date(2026, 10, 30))  # Friday
        self.assertFalse(treat_tracker.is_available(treat, date(2026, 11, 1)))  # Sunday, same week
        self.assertTrue(treat_tracker.is_available(treat, date(2026, 11, 2)))  # next Monday
        self.assertEqual(treat_tracker.next_week_start(date(2026, 10, 30)), date(2026, 11, 2))


if __name__ == "__main__":
    unittest.main()
