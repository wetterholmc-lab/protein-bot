"""Calculate a personalised daily protein goal from a user profile."""

from .models import ActivityLevel, DietStyle, FitnessGoal, Sex, UserProfile

# Base grams of protein per kg of bodyweight, by activity level.
_BASE_G_PER_KG: dict[ActivityLevel, float] = {
    ActivityLevel.sedentary: 1.0,
    ActivityLevel.moderate: 1.2,
    ActivityLevel.regular: 1.4,
    ActivityLevel.hard: 1.8,
}

# Multiplier on top of the base, by fitness goal.
_GOAL_MULTIPLIER: dict[FitnessGoal, float] = {
    FitnessGoal.maintain: 1.0,
    FitnessGoal.lose_weight: 1.1,
    FitnessGoal.build_muscle: 1.2,
}

# Sex adjustment — females have slightly lower lean mass on average.
_SEX_MULTIPLIER: dict[Sex, float] = {
    Sex.female: 0.90,
    Sex.male: 1.00,
    Sex.other: 0.95,
}

# Plant protein is less bioavailable; a small buffer covers this.
_VEGAN_BUFFER_G = 10


def calculate_goal(profile: UserProfile) -> int:
    """Return a daily protein goal in grams."""
    base = _BASE_G_PER_KG[profile.activity_level]

    # Older adults need more protein to maintain muscle mass.
    if profile.age >= 50:
        base += 0.15
    elif profile.age >= 40:
        base += 0.05

    goal_g = (
        profile.weight_kg * base * _GOAL_MULTIPLIER[profile.goal] * _SEX_MULTIPLIER[profile.sex]
    )

    if profile.pregnant_or_breastfeeding:
        goal_g += 25  # NHS / WHO recommendation during pregnancy/breastfeeding

    if profile.perimenopausal:
        goal_g += 15  # oestrogen drop accelerates muscle loss; extra protein counters this

    if profile.diet_style == DietStyle.vegan:
        goal_g += _VEGAN_BUFFER_G

    return round(goal_g)
