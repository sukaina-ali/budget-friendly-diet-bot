"""Independent safety checks. The AI model is NOT the only thing enforcing rules.

IMPORTANT LIMITATION: these are text (keyword) checks. They catch obvious
violations and trigger a regeneration, but they can NOT guarantee allergy safety
(hidden ingredients, spelling variants, other languages, packaged foods, ...).
The bot never tells a user a packaged food is safe.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

# ---------------------------------------------------------------- allergen families
_PEANUT = ["peanut", "peanuts", "peanut butter", "groundnut", "groundnuts", "moongphali", "mungphali"]
_TREE_NUTS = [
    "almond", "almonds", "walnut", "walnuts", "cashew", "cashews", "pistachio", "pistachios",
    "pista", "hazelnut", "hazelnuts", "pecan", "pecans", "badam", "akhrot", "kaju", "chilgoza",
]
_DAIRY = [
    "milk", "dairy", "dahi", "yogurt", "yoghurt", "curd", "paneer", "cheese", "butter", "ghee",
    "lassi", "raita", "cream", "khoya", "lactose",
]
ALLERGEN_FAMILIES: Dict[str, List[str]] = {
    "peanut": _PEANUT,
    "nuts": _PEANUT + _TREE_NUTS,
    "tree nut": _TREE_NUTS,
    "milk": _DAIRY,
    "egg": ["egg", "eggs", "omelette", "omelet", "anda"],
    "fish": ["fish", "machli"],
    "shellfish": ["shellfish", "prawn", "prawns", "shrimp", "crab", "lobster"],
    "wheat": ["wheat", "roti", "chapati", "atta", "paratha", "naan", "bread", "gluten", "daliya", "semolina", "suji"],
    "soy": ["soy", "soya", "soybean", "soybeans", "tofu"],
    "sesame": ["sesame", "til", "tahini"],
}
ALLERGEN_ALIASES: Dict[str, str] = {
    "peanuts": "peanut", "groundnut": "peanut", "groundnuts": "peanut", "moongphali": "peanut",
    "nut": "nuts", "all nuts": "nuts", "tree nuts": "tree nut", "dry fruits": "nuts",
    "dairy": "milk", "lactose": "milk", "milk products": "milk", "eggs": "egg",
    "prawn": "shellfish", "prawns": "shellfish", "shrimp": "shellfish",
    "gluten": "wheat", "soya": "soy", "soybean": "soy", "til": "sesame",
}

_MEAT_AND_FISH = [
    "chicken", "mutton", "beef", "lamb", "goat", "pork", "gosht", "nihari", "paya", "paye",
    "fish", "machli", "prawn", "prawns", "shrimp", "crab",
]
_EGGS = ["egg", "eggs", "omelette", "omelet", "anda"]
_VEGAN_EXTRA = _DAIRY + ["honey"]
DIET_FORBIDDEN: Dict[str, List[str]] = {
    "vegetarian": _MEAT_AND_FISH + _EGGS,  # eggs excluded too: the safe choice for Indian/Pakistani vegetarians
    "vegan": _MEAT_AND_FISH + _EGGS + _VEGAN_EXTRA,
}
RED_MEAT = ["beef", "mutton", "lamb", "goat", "pork", "gosht", "nihari", "paya", "paye", "red meat"]

# A sentence containing one of these is talking about *avoiding* the food, which is fine.
_SAFE_CUES = re.compile(
    r"\b(avoid\w*|exclud\w*|without|free from|free of|instead of|allerg\w*|left out|leave out|omit\w*|"
    r"skip\w*|steer clear|not include|no)\b|n't|\bnot\b",
    re.I,
)
_NEGATION = re.compile(r"\bnot\b|n't\b|\bnever\b|\bno\b|\bcannot\b|\bwithout\b|\bnor\b", re.I)


@dataclass(frozen=True)
class Violation:
    kind: str  # allergy | diet | red_meat | cure_claim | nutrition_claim | compensation | carb_rule
    detail: str


def normalize_allergen(name: str) -> str:
    n = name.strip().lower()
    return ALLERGEN_ALIASES.get(n, n)


def allergen_terms(name: str) -> List[str]:
    n = normalize_allergen(name)
    if n in ALLERGEN_FAMILIES:
        return ALLERGEN_FAMILIES[n]
    terms = {n}
    terms.add(n + "s" if not n.endswith("s") else n.rstrip("s"))
    return sorted(terms)


def _sentences(text: str) -> List[str]:
    return [s for s in re.split(r"(?<=[.!?])\s+|\n+", text) if s.strip()]


def _contains_term(sentence: str, term: str) -> bool:
    return re.search(rf"(?<![a-z]){re.escape(term)}(?![a-z])", sentence.lower()) is not None


def _find_terms(text: str, terms: Iterable[str]) -> Optional[str]:
    for sentence in _sentences(text):
        if _SAFE_CUES.search(sentence):
            continue
        for term in terms:
            if _contains_term(sentence, term):
                return term
    return None


def find_allergen_hits(text: str, allergies: Iterable[str]) -> List[Violation]:
    hits = []
    for allergy in allergies:
        term = _find_terms(text, allergen_terms(allergy))
        if term:
            hits.append(Violation("allergy", f"mentions '{term}' but the user is allergic to {allergy}"))
    return hits


def find_diet_hits(text: str, diet: str) -> List[Violation]:
    forbidden = DIET_FORBIDDEN.get(diet)
    if not forbidden:
        return []
    term = _find_terms(text, forbidden)
    return [Violation("diet", f"mentions '{term}' but the user's saved diet is {diet}")] if term else []


# ---------------------------------------------------------------- medical / unsupported claims
_CURE_VERBS = r"(?:cure|cures|cured|curing|reverse|reverses|reversed|reversing|heal|heals|fix|fixes|treat|treats|eliminate|eliminates|reduce|reduces|lower|lowers|improve|improves)"
_CURE_A = re.compile(rf"\b{_CURE_VERBS}\b[^.!?\n]{{0,50}}\binsulin[\s-]resistance\b", re.I)
_CURE_B = re.compile(rf"\binsulin[\s-]resistance\b[^.!?\n]{{0,40}}\b{_CURE_VERBS}\b", re.I)
_SENSITIVITY = re.compile(r"\b(?:improve|improves|boost|boosts|increase|increases)\b[^.!?\n]{0,30}\binsulin sensitivity\b", re.I)


def find_cure_claims(text: str) -> List[Violation]:
    for sentence in _sentences(text):
        if _NEGATION.search(sentence):
            continue  # e.g. "this cannot cure insulin resistance"
        if _CURE_A.search(sentence) or _CURE_B.search(sentence) or _SENSITIVITY.search(sentence):
            return [Violation("cure_claim", "claims food/plan treats or improves insulin resistance")]
    return []


_NUTRITION_NUMBERS = re.compile(r"\b\d{2,4}\s*(?:kcal|calories|cals?)\b|\b\d+(?:\.\d+)?\s*(?:g|grams?)\b", re.I)
_NO_CARBS_DINNER = re.compile(r"\b(?:no|avoid|eliminate|cut out|skip)\s+(?:all\s+)?(?:carbs|carbohydrates)\b[^.!?\n]{0,25}\b(?:dinner|night|evening)\b", re.I)


def find_unsupported_claims(text: str) -> List[Violation]:
    out = []
    if _NUTRITION_NUMBERS.search(text):
        out.append(Violation("nutrition_claim", "gives exact calories/grams, but no approved nutrition data exists"))
    if _NO_CARBS_DINNER.search(text):
        out.append(Violation("carb_rule", "imposes a universal 'no carbs at dinner' rule"))
    return out


_COMPENSATION = re.compile(
    r"\b(?:skip|miss|fast|starve)\w*\b[^.!?\n]{0,30}\b(?:meal|meals|lunch|dinner|breakfast|tomorrow|today)\b|"
    r"\bburn (?:it|that|this) off\b|\bmake up for (?:it|that|this)\b|\bcompensate\b|\bextra (?:workout|exercise)\b",
    re.I,
)


def find_compensation_advice(text: str) -> List[Violation]:
    for sentence in _sentences(text):
        if _NEGATION.search(sentence):
            continue
        if _COMPENSATION.search(sentence):
            return [Violation("compensation", "suggests skipping meals/fasting/exercise to compensate")]
    return []


def check_response(response: str, profile: Dict, user_message: str = "") -> List[Violation]:
    """All checks for a model reply. An empty list means no violation was found."""
    violations: List[Violation] = []
    violations += find_allergen_hits(response, profile.get("allergies", []))
    violations += find_diet_hits(response, profile.get("diet", "unknown"))
    # Red meat is excluded from the standard framework, unless the user asked for it by name.
    if not any(_contains_term(user_message, t) for t in RED_MEAT):
        term = _find_terms(response, RED_MEAT)
        if term:
            violations.append(Violation("red_meat", f"mentions '{term}'; red meat is excluded from standard plans"))
    violations += find_cure_claims(response)
    violations += find_unsupported_claims(response)
    violations += find_compensation_advice(response)
    return violations


def describe_violations(violations: List[Violation]) -> str:
    return "; ".join(f"[{v.kind}] {v.detail}" for v in violations)


# ---------------------------------------------------------------- unsafe user requests
_UNSAFE = [
    re.compile(r"\bstarv\w*\b|\bcrash diet\b", re.I),
    re.compile(r"\bfast(?:ing)?\s+for\s+\d+\s+days?\b|\bnot\s+eat(?:ing)?\s+for\s+\d+\s+days?\b", re.I),
    re.compile(r"\b(?:one|1)\s+meal\s+(?:a|per)\s+day\b|\bomad\b", re.I),
    re.compile(r"\blose\s+\d+\s*(?:kg|kilos?|lbs?|pounds?)\s+in\s+(?:\d+|a|one|two|three)\s*days?\b", re.I),
]
_LOW_CAL = re.compile(r"\b(\d{3,4})\s*(?:kcal|calories|cals?)\b", re.I)

UNSAFE_REQUEST_REPLY = (
    "I can't help with extreme restriction like starving, very long fasts or very low calorie plans — "
    "they can be harmful. 💚 I'd love to help you eat well in a way that's filling, balanced and affordable "
    "instead. If you're worried about your weight or health, a doctor or registered dietitian can give you "
    "personal guidance. Want me to put together a satisfying plan for today?"
)


def check_user_request(text: str) -> bool:
    """True if the user is asking for a clearly unsafe restrictive plan."""
    if any(p.search(text) for p in _UNSAFE):
        return True
    m = _LOW_CAL.search(text)
    return bool(m and int(m.group(1)) < 1000 and re.search(r"\b(eat|diet|plan|limit|only|under|below|max)\w*", text, re.I))


FALLBACK_REPLY = (
    "Sorry, I couldn't put together a reply that I'm confident respects your saved preferences and allergies. "
    "Could you tell me which foods you'd like or have at home, and I'll try again? "
    "For anything allergy-related, please check ingredients carefully or ask your doctor or dietitian."
)
