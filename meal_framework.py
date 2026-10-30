"""The starting seven-day example schedule.

This is a set of EXAMPLES, not a clinically validated prescription. No portion
sizes or medical targets are included. A qualified professional can edit
SCHEDULE below (or replace it) and the whole bot will use the new version.
"""
from __future__ import annotations

from datetime import date
from typing import Dict, List, Tuple

SCHEDULE: Dict[int, List[Tuple[str, str]]] = {
    1: [
        ("Breakfast", "Vegetable omelette and one roti"),
        ("Lunch", "Grilled chicken, salad, and one roti"),
        ("Drink", "Lemon water"),
        ("Dinner", "Chicken yakhni soup and sautéed vegetables"),
        ("Optional drink", "Low-fat milk with a pinch of turmeric"),
        ("Snack", "Five almonds and two walnuts"),
    ],
    2: [
        ("Breakfast", "Savoury oats with vegetables and lemon"),
        ("Drink", "Ginger tea without sugar"),
        ("Lunch", "Moong daal, one roti, and salad"),
        ("Drink", "Mint water"),
        ("Dinner", "Grilled fish and steamed vegetables"),
        ("Snack", "Apple or guava"),
    ],
    3: [
        ("Breakfast", "Plain low-fat dahi with chia seeds and nuts"),
        ("Lunch", "Chicken with vegetables cooked using less oil, one roti, and salad"),
        ("Drink", "Zeera water"),
        ("Dinner", "Masoor or moong daal soup"),
        ("Optional drink", "Turmeric milk"),
        ("Snack", "Roasted chana"),
    ],
    4: [
        ("Breakfast", "One boiled egg, one omelette, and one small roti"),
        ("Drink", "Lemon-ginger water"),
        ("Lunch", "Grilled chicken wrap using a whole-wheat roti and vegetables"),
        ("Drink", "Unsweetened coconut water"),
        ("Dinner", "Lauki or tori sabzi with daal"),
        ("Snack", "Five almonds"),
    ],
    5: [
        ("Breakfast", "Oats with cinnamon and a few nuts"),
        ("Lunch", "Lightly cooked fish curry, one roti, and salad"),
        ("Drink", "Lemon water"),
        ("Dinner", "Chicken and vegetable soup"),
    ],
    6: [
        ("Breakfast", "Vegetable omelette and one roti"),
        ("Drink", "Ginger tea"),
        ("Lunch", "Masoor daal, sabzi, and one roti"),
        ("Drink", "Mint water"),
        ("Dinner", "Grilled chicken and sautéed vegetables"),
        ("Optional drink", "Turmeric milk"),
        ("Snack", "Roasted chana"),
    ],
    7: [
        ("Breakfast", "Dahi with flaxseed and nuts"),
        ("Lunch", "Chicken pulao made with brown rice, served with salad"),
        ("Drink", "Lemon water"),
        ("Dinner", "Vegetable soup and daal"),
        ("Snack", "Apple"),
    ],
}


def framework_day_for(d: date) -> int:
    """Monday = Day 1 ... Sunday = Day 7 (just a starting point, never forced)."""
    return d.weekday() + 1


def format_schedule() -> str:
    lines = []
    for day, items in SCHEDULE.items():
        lines.append(f"Day {day}:")
        lines.extend(f"  - {label}: {text}" for label, text in items)
    return "\n".join(lines)
