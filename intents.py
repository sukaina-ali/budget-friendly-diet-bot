"""Simple, transparent text parsing: pull facts the user actually stated.

Nothing is guessed. A fact is saved only when the user's own words state it.
"""
from __future__ import annotations

import re
from typing import List, Optional, Tuple

_MEALS = r"(breakfast|lunch|dinner|snack|supper|iftar|sehri|suhoor)"
_SPLIT_LIST = re.compile(r"\s*(?:,|&|\band\b|\bor\b|/)\s*", re.I)
_TRAILING = re.compile(r"\b(?:but|so|because|please|though|since|thanks|thank you)\b.*$", re.I)
_LEADING = re.compile(r"^(?:the|any|all|a|an|some|to|of)\s+", re.I)


def _items(chunk: str, max_words: int = 3) -> List[str]:
    chunk = _TRAILING.sub("", chunk).strip(" .!?")
    out = []
    for part in _SPLIT_LIST.split(chunk):
        part = _LEADING.sub("", part.strip().lower())
        part = re.sub(r"\b(too|also|now|as well|really|very)\b", "", part).strip(" .!?-")
        if part and len(part.split()) <= max_words and len(part) <= 30:
            out.append(part)
    return out


# ---------------------------------------------------------------- allergies
_ALLERGY_A = re.compile(r"\ballerg(?:ic|y)\s+(?:to|of)\s+([^.;!?\n]+)", re.I)
_ALLERGY_B = re.compile(r"\bi\s+(?:have|got|'ve got)\s+(?:an?\s+)?([a-z][a-z\s-]{1,30}?)\s+allergy\b", re.I)
_NOT_ALLERGEN = {"anything", "nothing", "everything", "any food", "food", "foods"}


def extract_allergies(text: str) -> List[str]:
    found: List[str] = []
    for m in _ALLERGY_A.finditer(text):
        prefix = text[max(0, m.start() - 14): m.start()].lower()
        if re.search(r"\bnot\s+$|n't\s+$|\bno\s+$|\bnever\s+$", prefix):
            continue
        found.extend(_items(m.group(1)))
    for m in _ALLERGY_B.finditer(text):
        found.extend(_items(m.group(1)))
    seen, out = set(), []
    for item in found:
        if item not in _NOT_ALLERGEN and item not in seen:
            seen.add(item)
            out.append(item)
    return out


# ---------------------------------------------------------------- diet
_DIET_INTENT = re.compile(
    r"\b(i am|i'm|im|i want|i prefer|i eat|i only eat|from now on|going forward|"
    r"switch|switched|become|became|only|make it|make my)\b",
    re.I,
)


def extract_diet(text: str) -> Optional[str]:
    t = text.lower()
    if not _DIET_INTENT.search(t):
        return None
    if re.search(r"\bnon[\s-]?veg(?:etarian)?\b|\bnot\s+(?:a\s+)?(?:strict\s+)?veg(?:etarian)?\b", t):
        return "non-vegetarian"
    if re.search(r"\bvegan\b", t):
        return "vegan"
    if re.search(r"\bvegetarian\b|\bveg\b", t):
        return "vegetarian"
    return None


# ---------------------------------------------------------------- other preferences
_DISLIKE = re.compile(
    r"\bi\s+(?:really\s+)?(?:don't|do not|dont)\s+like\s+([^.;!?\n]+)|"
    r"\bi\s+(?:really\s+)?(?:hate|dislike)\s+([^.;!?\n]+)|\bi\s+can(?:'t|not)\s+stand\s+([^.;!?\n]+)",
    re.I,
)


def extract_dislikes(text: str) -> List[str]:
    out: List[str] = []
    for m in _DISLIKE.finditer(text):
        out.extend(_items(next(g for g in m.groups() if g)))
    return out


_BUDGET_NUM = re.compile(
    r"\bbudget\s*(?:is|of|:|=)?\s*(?:around|about|approx\w*|under|below|max\w*)?\s*"
    r"((?:rs\.?|pkr|inr|₹)?\s*\d[\d,]*\s*(?:rs|rupees|pkr|inr)?(?:\s*(?:per|a|/)\s*(?:day|week|month))?)",
    re.I,
)
_BUDGET_WORD = re.compile(r"\b((?:very\s+)?(?:tight|low|limited|small)\s+budget)\b", re.I)


def extract_budget(text: str) -> Optional[str]:
    m = _BUDGET_NUM.search(text)
    if m and m.group(1).strip():
        return " ".join(m.group(1).split())
    m = _BUDGET_WORD.search(text)
    return m.group(1).lower() if m else None


_HEALTH = re.compile(
    r"\b(?:i\s+(?:have|got|am|was|'ve)|i'm|my)\b[^.;!?\n]{0,40}?"
    r"\b(insulin[\s-]resist\w*|pcos|pcod|prediabetes|diabetes|hypothyroid\w*|thyroid)\b",
    re.I,
)


def extract_health_context(text: str) -> Optional[str]:
    """Only self-reported (first person) context is saved."""
    m = _HEALTH.search(text)
    if not m:
        return None
    word = m.group(1).lower()
    return "insulin resistance" if word.startswith("insulin") else word


# ---------------------------------------------------------------- meals
_REPORT_A = re.compile(
    r"\bi(?:'m|'ve|\s+am|\s+have)?\s+(?:just\s+|already\s+)?(?:had|ate|eaten|having)\s+(.+?)\s+"
    r"(?:for|as)\s+(?:my\s+)?" + _MEALS,
    re.I,
)
_REPORT_B = re.compile(
    r"\bfor\s+(?:my\s+)?" + _MEALS + r",?\s+i\s+(?:just\s+)?(?:had|ate|have had|am having|'m having)\s+([^.!?\n]+)",
    re.I,
)


def extract_reported_meals(text: str) -> List[Tuple[str, str]]:
    """[(meal_type, description)] for meals the user says they ate."""
    out: List[Tuple[str, str]] = []
    for m in _REPORT_A.finditer(text):
        out.append((m.group(2).lower(), m.group(1).strip(" ,.")))
    for m in _REPORT_B.finditer(text):
        out.append((m.group(1).lower(), m.group(2).strip(" ,.")))
    return [("dinner" if meal == "supper" else meal, desc) for meal, desc in out if desc]


_TREAT = re.compile(r"\btreat(?:\s+meal)?\b", re.I)
_TREAT_REQUEST = re.compile(r"\?|\b(can i|may i|could i|should i|want|crav\w*|allowed|going to|planning|will|if i|wanna)\b", re.I)
_TREAT_USED = re.compile(
    r"\b(?:had|ate|eaten|used|using|took|taken|having|did|enjoyed)\b[^.!?\n]{0,60}\btreat\b|"
    r"\btreat\b[^.!?\n]{0,40}\b(?:was|is|done|used|finished)\b",
    re.I,
)


def treat_intent(text: str) -> Optional[str]:
    """'used' if the user says they had their treat meal, 'requested' if they ask, else None."""
    if not _TREAT.search(text):
        return None
    if _TREAT_REQUEST.search(text):
        return "requested"
    if _TREAT_USED.search(text):
        return "used"
    return "requested"


_PLAN = re.compile(
    r"\b(meal plan|plan for today|today'?s (?:meal|plan|menu)|what (?:should|can) i eat|what to eat|"
    r"menu|suggest (?:a |some )?(?:meal|lunch|dinner|breakfast)|diet plan)\b",
    re.I,
)


def wants_plan(text: str) -> bool:
    return bool(_PLAN.search(text))


_MISSING = re.compile(r"\bi\s+(?:don't|do not|dont)\s+have\s+(?:any\s+)?([^.,;!?\n]+)|\bran out of\s+([^.,;!?\n]+)", re.I)


def extract_missing_ingredients(text: str) -> List[str]:
    out: List[str] = []
    for m in _MISSING.finditer(text):
        out.extend(_items(next(g for g in m.groups() if g), max_words=4))
    return out


_SUBST = re.compile(r"\b(?:i'll|i will|i used|i'm using|using)\s+(.+?)\s+instead of\s+([^.,;!?\n]+)", re.I)


def extract_substitutions(text: str) -> List[Tuple[str, str]]:
    return [(m.group(1).strip(), m.group(2).strip()) for m in _SUBST.finditer(text)]
