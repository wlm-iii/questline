"""App-configured cost ranges (SPEC §8 budget presets). Estimates, never quotes.

Google's price level is a coarse input; a missing level stays unknown and is never treated as free.
"""

from typing import Literal

BudgetPreset = Literal["shoestring", "comfortable", "treat"]

GOOGLE_PRICE_LEVELS = {
    "PRICE_LEVEL_FREE": 0,
    "PRICE_LEVEL_INEXPENSIVE": 1,
    "PRICE_LEVEL_MODERATE": 2,
    "PRICE_LEVEL_EXPENSIVE": 3,
    "PRICE_LEVEL_VERY_EXPENSIVE": 4,
}

# Per adult, per visit, in USD.
RANGES: dict[str, dict[int, tuple[float, float]]] = {
    "eat": {0: (0, 0), 1: (10, 20), 2: (20, 40), 3: (40, 75), 4: (75, 150)},
    "do": {0: (0, 0), 1: (5, 20), 2: (20, 40), 3: (40, 80), 4: (80, 150)},
}
RANGES["along_the_way"] = RANGES["do"]

PRESET_MAX_LEVEL: dict[str, int] = {"shoestring": 1, "comfortable": 2, "treat": 4}
PRESET_LABELS = {
    "shoestring": "Shoestring",
    "comfortable": "Comfortable",
    "treat": "Treat ourselves",
}


def dollar_signs(level: int) -> str:
    return "Free" if level == 0 else "$" * level


def estimate(category: str, price_level: int | None) -> tuple[float, float, str] | None:
    """Return (low, high, basis) for a known price level, or None when unknown."""
    if price_level is None or category not in RANGES:
        return None
    low, high = RANGES[category][price_level]
    basis = f"App estimate from Google price level {dollar_signs(price_level)}; per adult"
    return low, high, basis


def over_budget(price_level: int | None, preset: str) -> bool:
    return price_level is not None and price_level > PRESET_MAX_LEVEL[preset]
