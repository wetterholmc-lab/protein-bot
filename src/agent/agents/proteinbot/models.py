"""Shared Pydantic models for the protein tracking bot."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel


class Sex(StrEnum):
    female = "female"
    male = "male"
    other = "other"


class ActivityLevel(StrEnum):
    sedentary = "sedentary"
    moderate = "moderate"
    regular = "regular"
    hard = "hard"


class FitnessGoal(StrEnum):
    maintain = "maintain"
    lose_weight = "lose_weight"
    build_muscle = "build_muscle"


class DietStyle(StrEnum):
    omnivore = "omnivore"
    vegetarian = "vegetarian"
    vegan = "vegan"


class UserProfile(BaseModel):
    telegram_id: int
    age: int
    weight_kg: float
    height_cm: float
    sex: Sex
    activity_level: ActivityLevel
    goal: FitnessGoal
    diet_style: DietStyle
    pregnant_or_breastfeeding: bool | None
    perimenopausal: bool | None  # asked for females aged 40+
    protein_goal_g: int


class FoodEstimate(BaseModel):
    is_food: bool
    is_identifiable: bool
    is_home_cooked: bool
    description: str
    protein_min_g: int
    protein_max_g: int


class MealEntry(BaseModel):
    id: int
    telegram_id: int
    logged_at: datetime
    description: str
    protein_min_g: int
    protein_max_g: int
    protein_actual_g: int | None
    recipe_id: int | None

    @property
    def effective_protein_g(self) -> int:
        """Actual if corrected, otherwise midpoint of the estimated range."""
        if self.protein_actual_g is not None:
            return self.protein_actual_g
        return (self.protein_min_g + self.protein_max_g) // 2


class DailySummary(BaseModel):
    total_g: int
    goal_g: int
    deficit_g: int  # positive = still needed, negative = surplus
    meals: list[MealEntry]


class Intent(StrEnum):
    status = "status"
    correction = "correction"
    meal_suggestion = "meal_suggestion"
    off_topic = "off_topic"


class IntentResult(BaseModel):
    intent: Intent
    correction_g: int | None = None  # parsed grams if intent is correction
    meal_type: str | None = None  # e.g. "lunch", "dinner" if intent is meal_suggestion
