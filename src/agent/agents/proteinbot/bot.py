"""Telegram bot — entry point and message routing for the protein tracker."""

import re
from datetime import UTC, time
from typing import Any

from loguru import logger
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from agent.config import get_settings
from agent.logging_setup import setup_logging
from agent.services import db

from . import correction_handler, daily_tracker, meal_logger, recipe_store, suggestion_engine
from .food_analyzer import analyze_food_photo
from .goal_calculator import calculate_goal
from .ingredient_calculator import calculate_from_ingredients
from .intent_classifier import classify, is_status_request
from .models import (
    ActivityLevel,
    DietStyle,
    FitnessGoal,
    Intent,
    Sex,
    UserProfile,
)

MIGRATIONS_DIR = "migrations"

# ---------------------------------------------------------------------------
# Onboarding conversation states
# ---------------------------------------------------------------------------
(
    OB_AGE,
    OB_WEIGHT,
    OB_HEIGHT,
    OB_SEX,
    OB_ACTIVITY,
    OB_GOAL,
    OB_DIET,
    OB_PREGNANT,
    OB_MENOPAUSE,
    OB_CONFIRM_GOAL,
    OB_CUSTOM_GOAL,
) = range(11)

# user_data keys
KEY_PROFILE_DRAFT = "profile_draft"
KEY_LAST_MEAL_ID = "last_meal_id"
KEY_PENDING_CORRECTION_G = "pending_correction_g"
KEY_PENDING_HOMECOOK = "pending_homecook"
KEY_PENDING_RECIPE = "pending_recipe"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ud(context: ContextTypes.DEFAULT_TYPE) -> dict[str, Any]:
    """Return context.user_data, asserting it is not None."""
    assert context.user_data is not None
    return context.user_data  # type: ignore[return-value]


async def _get_profile(telegram_id: int) -> UserProfile | None:
    row = await db.fetchrow("SELECT * FROM proteinbot_users WHERE telegram_id = $1", telegram_id)
    if row is None:
        return None
    return UserProfile(**dict(row))


async def _save_profile(profile: UserProfile) -> None:
    await db.execute(
        """
        INSERT INTO proteinbot_users
            (telegram_id, age, weight_kg, height_cm, sex, activity_level, goal,
             diet_style, pregnant_or_breastfeeding, perimenopausal, protein_goal_g)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
        ON CONFLICT (telegram_id) DO UPDATE SET
            age=$2, weight_kg=$3, height_cm=$4, sex=$5, activity_level=$6,
            goal=$7, diet_style=$8, pregnant_or_breastfeeding=$9,
            perimenopausal=$10, protein_goal_g=$11
        """,
        profile.telegram_id,
        profile.age,
        profile.weight_kg,
        profile.height_cm,
        profile.sex.value,
        profile.activity_level.value,
        profile.goal.value,
        profile.diet_style.value,
        profile.pregnant_or_breastfeeding,
        profile.perimenopausal,
        profile.protein_goal_g,
    )


async def cmd_reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.effective_user and update.message
    telegram_id = update.effective_user.id
    await db.execute("DELETE FROM proteinbot_meals WHERE telegram_id = $1", telegram_id)
    await db.execute("DELETE FROM proteinbot_recipes WHERE telegram_id = $1", telegram_id)
    await db.execute("DELETE FROM proteinbot_users WHERE telegram_id = $1", telegram_id)
    _ud(context).clear()
    await update.message.reply_text(
        "Profile and all logged meals deleted. Send /start to set up a new profile."
    )


def _keyboard(*rows: tuple[str, str]) -> InlineKeyboardMarkup:
    """All buttons in a single row."""
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(label, callback_data=data) for label, data in rows]]
    )


def _keyboard_rows(*rows: tuple[tuple[str, str], ...]) -> InlineKeyboardMarkup:
    """Each argument becomes its own row of buttons."""
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(label, callback_data=data) for label, data in row] for row in rows]
    )


# ---------------------------------------------------------------------------
# Onboarding
# ---------------------------------------------------------------------------


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    assert update.effective_user and update.message
    profile = await _get_profile(update.effective_user.id)
    if profile:
        await update.message.reply_text(
            f"Welcome back! Your daily protein goal is *{profile.protein_goal_g}g*.\n"
            "Send me a food photo to log a meal, or type *status* to see today's total.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return ConversationHandler.END

    await update.message.reply_text(
        "Hi! I'm your protein tracking bot.\n\n"
        "I'll help you hit your daily protein goal by estimating protein from food photos "
        "and sending you a check-in at 15:00.\n\n"
        "Let's set up your profile. How old are you? (type a number)"
    )
    _ud(context)[KEY_PROFILE_DRAFT] = {}
    return OB_AGE


async def ob_age(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    assert update.message and update.message.text
    try:
        age = int(update.message.text.strip())
        if not (10 <= age <= 120):
            raise ValueError
    except ValueError:
        await update.message.reply_text("Please enter a valid age (e.g. 35).")
        return OB_AGE
    _ud(context)[KEY_PROFILE_DRAFT]["age"] = age
    await update.message.reply_text("What's your weight in kg? (e.g. 68)")
    return OB_WEIGHT


async def ob_weight(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    assert update.message and update.message.text
    try:
        weight = float(update.message.text.strip().replace(",", "."))
        if not (20 <= weight <= 400):
            raise ValueError
    except ValueError:
        await update.message.reply_text("Please enter a valid weight in kg (e.g. 68).")
        return OB_WEIGHT
    _ud(context)[KEY_PROFILE_DRAFT]["weight_kg"] = weight
    await update.message.reply_text("And your height in cm? (e.g. 170)")
    return OB_HEIGHT


async def ob_height(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    assert update.message and update.message.text
    try:
        height = float(update.message.text.strip().replace(",", "."))
        if not (100 <= height <= 250):
            raise ValueError
    except ValueError:
        await update.message.reply_text("Please enter a valid height in cm (e.g. 170).")
        return OB_HEIGHT
    _ud(context)[KEY_PROFILE_DRAFT]["height_cm"] = height
    await update.message.reply_text(
        "What's your sex?",
        reply_markup=_keyboard(
            ("Female", "female"), ("Male", "male"), ("Prefer not to say", "other")
        ),
    )
    return OB_SEX


async def ob_sex(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    assert update.callback_query
    await update.callback_query.answer()
    _ud(context)[KEY_PROFILE_DRAFT]["sex"] = update.callback_query.data
    await update.callback_query.edit_message_text(
        "How active are you?\n\n"
        "Sedentary = desk job, little movement\n"
        "Moderate = walks, light activity most days\n"
        "Active = gym or sport 3–5×/week\n"
        "Intense = daily hard training",
        reply_markup=_keyboard_rows(
            (("Sedentary", "sedentary"), ("Moderate", "moderate")),
            (("Active", "regular"), ("Intense", "hard")),
        ),
    )
    return OB_ACTIVITY


async def ob_activity(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    assert update.callback_query
    await update.callback_query.answer()
    _ud(context)[KEY_PROFILE_DRAFT]["activity_level"] = update.callback_query.data
    await update.callback_query.edit_message_text(
        "What's your main goal?",
        reply_markup=_keyboard(
            ("Maintain muscle", "maintain"),
            ("Lose weight", "lose_weight"),
            ("Build muscle", "build_muscle"),
        ),
    )
    return OB_GOAL


async def ob_goal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    assert update.callback_query
    await update.callback_query.answer()
    _ud(context)[KEY_PROFILE_DRAFT]["goal"] = update.callback_query.data
    await update.callback_query.edit_message_text(
        "What's your diet style?",
        reply_markup=_keyboard(
            ("Omnivore", "omnivore"), ("Vegetarian", "vegetarian"), ("Vegan", "vegan")
        ),
    )
    return OB_DIET


async def ob_diet(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    assert update.callback_query
    await update.callback_query.answer()
    ud = _ud(context)
    ud[KEY_PROFILE_DRAFT]["diet_style"] = update.callback_query.data
    sex = ud[KEY_PROFILE_DRAFT].get("sex", "male")
    if sex in ("female", "other"):
        await update.callback_query.edit_message_text(
            "Are you currently pregnant or breastfeeding?",
            reply_markup=_keyboard(("Yes", "yes"), ("No", "no")),
        )
        return OB_PREGNANT
    ud[KEY_PROFILE_DRAFT]["pregnant_or_breastfeeding"] = False
    ud[KEY_PROFILE_DRAFT]["perimenopausal"] = None
    return await _finish_onboarding(update, context)


async def ob_pregnant(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    assert update.callback_query
    await update.callback_query.answer()
    ud = _ud(context)
    pregnant = update.callback_query.data == "yes"
    ud[KEY_PROFILE_DRAFT]["pregnant_or_breastfeeding"] = pregnant

    # Ask about perimenopause/menopause for females aged 40+ who are not pregnant.
    sex = ud[KEY_PROFILE_DRAFT].get("sex", "male")
    age = int(ud[KEY_PROFILE_DRAFT].get("age", 0))
    logger.debug(f"ob_pregnant: pregnant={pregnant} sex={sex!r} age={age}")
    if not pregnant and sex == "female" and age >= 40:
        await update.callback_query.edit_message_text(
            "One more question — are you in perimenopause or menopause?\n\n"
            "This affects protein needs, as oestrogen changes accelerate muscle loss.",
            reply_markup=_keyboard(
                ("Yes, perimenopause", "meno_yes"),
                ("Yes, menopause", "meno_yes"),
                ("No", "meno_no"),
            ),
        )
        return OB_MENOPAUSE

    ud[KEY_PROFILE_DRAFT]["perimenopausal"] = None
    return await _finish_onboarding(update, context)


async def ob_menopause(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    assert update.callback_query
    await update.callback_query.answer()
    _ud(context)[KEY_PROFILE_DRAFT]["perimenopausal"] = update.callback_query.data == "meno_yes"
    return await _finish_onboarding(update, context)


async def _finish_onboarding(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Calculate the suggested goal and ask the user to confirm or override it."""
    assert update.effective_user
    draft = _ud(context)[KEY_PROFILE_DRAFT]
    profile = UserProfile(
        telegram_id=update.effective_user.id,
        age=draft["age"],
        weight_kg=draft["weight_kg"],
        height_cm=draft["height_cm"],
        sex=Sex(draft["sex"]),
        activity_level=ActivityLevel(draft["activity_level"]),
        goal=FitnessGoal(draft["goal"]),
        diet_style=DietStyle(draft["diet_style"]),
        pregnant_or_breastfeeding=draft.get("pregnant_or_breastfeeding", False),
        perimenopausal=draft.get("perimenopausal"),
        protein_goal_g=0,
    )
    suggested_g = calculate_goal(profile)
    profile = profile.model_copy(update={"protein_goal_g": suggested_g})
    _ud(context)[KEY_PROFILE_DRAFT]["_profile_json"] = profile.model_dump()

    msg = (
        f"Based on your profile, I suggest *{suggested_g}g* of protein per day.\n\n"
        "Would you like to use this, or set your own goal?"
    )
    markup = _keyboard((f"Use {suggested_g}g", "goal_accept"), ("Set my own", "goal_custom"))
    if update.callback_query:
        await update.callback_query.edit_message_text(
            msg, parse_mode=ParseMode.MARKDOWN, reply_markup=markup
        )
    elif update.message:
        await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=markup)
    return OB_CONFIRM_GOAL


async def ob_confirm_goal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    assert update.callback_query
    await update.callback_query.answer()
    data = update.callback_query.data

    if data == "goal_custom":
        await update.callback_query.edit_message_text(
            "What daily protein goal would you like? (type a number in grams, e.g. 120)"
        )
        return OB_CUSTOM_GOAL

    # User accepted the suggested goal — save and finish.
    profile_data = _ud(context)[KEY_PROFILE_DRAFT]["_profile_json"]
    profile = UserProfile(**profile_data)
    await _save_profile(profile)
    await update.callback_query.edit_message_text(
        f"All set! Your daily protein goal is *{profile.protein_goal_g}g*.\n\n"
        "Send me a food photo to log your first meal. I'll also check in at 15:00 each day.",
        parse_mode=ParseMode.MARKDOWN,
    )
    return ConversationHandler.END


async def ob_custom_goal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    assert update.message and update.message.text
    try:
        goal_g = int(update.message.text.strip())
        if not (10 <= goal_g <= 500):
            raise ValueError
    except ValueError:
        await update.message.reply_text("Please enter a number between 10 and 500 (e.g. 120).")
        return OB_CUSTOM_GOAL

    profile_data = _ud(context)[KEY_PROFILE_DRAFT]["_profile_json"]
    profile = UserProfile(**{**profile_data, "protein_goal_g": goal_g})
    await _save_profile(profile)
    await update.message.reply_text(
        f"Got it — your daily protein goal is set to *{goal_g}g*.\n\n"
        "Send me a food photo to log your first meal. I'll also check in at 15:00 each day.",
        parse_mode=ParseMode.MARKDOWN,
    )
    return ConversationHandler.END


# ---------------------------------------------------------------------------
# Photo handler
# ---------------------------------------------------------------------------


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.effective_user and update.message and update.message.photo
    telegram_id = update.effective_user.id
    profile = await _get_profile(telegram_id)
    if not profile:
        await update.message.reply_text("Let's set up your profile first. Type /start to begin.")
        return

    await update.message.reply_text("Analysing your photo...")

    photo = update.message.photo[-1]
    file = await photo.get_file()
    photo_bytes = await file.download_as_bytearray()

    try:
        estimate = await analyze_food_photo(bytes(photo_bytes))
    except Exception:
        logger.exception("food_analyzer failed")
        await update.message.reply_text(
            "I'm having trouble processing that right now — try again in a moment."
        )
        return

    if not estimate.is_food:
        await update.message.reply_text(
            "That doesn't look like food — did you mean to send a different photo?"
        )
        return

    if not estimate.is_identifiable:
        await update.message.reply_text(
            "I can't make out the food clearly enough to give a reliable estimate. "
            "Could you send another photo or describe what you ate?"
        )
        return

    if estimate.is_home_cooked:
        _ud(context)[KEY_PENDING_HOMECOOK] = estimate
        await update.message.reply_text(
            f"Looks like home-cooked food — {estimate.description}.\n"
            "Could you tell me roughly what went into it and how many portions? "
            '(e.g. "chicken breast 300g, rice 200g, 2 portions")'
        )
        return

    meal_id = await meal_logger.log_meal(
        telegram_id=telegram_id,
        description=estimate.description,
        protein_min_g=estimate.protein_min_g,
        protein_max_g=estimate.protein_max_g,
    )
    _ud(context)[KEY_LAST_MEAL_ID] = meal_id

    summary = await daily_tracker.get_daily_summary(profile)
    feedback = await suggestion_engine.feedback_after_meal(
        meal_description=estimate.description,
        meal_protein_min=estimate.protein_min_g,
        meal_protein_max=estimate.protein_max_g,
        total_today_g=summary.total_g,
        goal_g=summary.goal_g,
        diet_style=profile.diet_style,
    )
    await update.message.reply_text(
        f"Logged: *{estimate.description}* — about "
        f"*{estimate.protein_min_g}–{estimate.protein_max_g}g* protein.\n"
        + daily_tracker.format_summary(summary)
        + f"\n\n{feedback}",
        parse_mode=ParseMode.MARKDOWN,
    )


# ---------------------------------------------------------------------------
# Ingredient follow-up (after home-cooked photo)
# ---------------------------------------------------------------------------


async def _handle_ingredients(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.effective_user and update.message and update.message.text
    telegram_id = update.effective_user.id
    profile = await _get_profile(telegram_id)
    ud = _ud(context)
    pending = ud.pop(KEY_PENDING_HOMECOOK, None)
    if not profile or pending is None:
        return

    text = update.message.text.strip()
    portions = 1
    m = re.search(r"(\d+)\s*portion", text, re.IGNORECASE)
    if m:
        portions = int(m.group(1))

    try:
        result = await calculate_from_ingredients(text, portions)
    except Exception:
        logger.exception("ingredient_calculator failed")
        await update.message.reply_text(
            "I couldn't calculate that — try again or tell me the rough protein total directly."
        )
        return

    meal_id = await meal_logger.log_meal(
        telegram_id=telegram_id,
        description=result.description,
        protein_min_g=result.protein_per_portion_min_g,
        protein_max_g=result.protein_per_portion_max_g,
    )
    ud[KEY_LAST_MEAL_ID] = meal_id
    ud[KEY_PENDING_RECIPE] = {
        "name": result.description,
        "portions": portions,
        "min": result.protein_per_portion_min_g,
        "max": result.protein_per_portion_max_g,
        "ingredients_text": text,
    }

    summary = await daily_tracker.get_daily_summary(profile)
    feedback = await suggestion_engine.feedback_after_meal(
        meal_description=result.description,
        meal_protein_min=result.protein_per_portion_min_g,
        meal_protein_max=result.protein_per_portion_max_g,
        total_today_g=summary.total_g,
        goal_g=summary.goal_g,
        diet_style=profile.diet_style,
    )
    await update.message.reply_text(
        f"Logged: *{result.description}* — about "
        f"*{result.protein_per_portion_min_g}–{result.protein_per_portion_max_g}g* per portion.\n"
        + daily_tracker.format_summary(summary)
        + f"\n\n{feedback}"
        + "\n\nWant me to save this recipe for next time? Reply *yes* or *no*.",
        parse_mode=ParseMode.MARKDOWN,
    )


# ---------------------------------------------------------------------------
# Text message handler
# ---------------------------------------------------------------------------


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.effective_user and update.message and update.message.text
    telegram_id = update.effective_user.id
    text = update.message.text.strip()
    ud = _ud(context)

    if ud.get(KEY_PENDING_HOMECOOK):
        await _handle_ingredients(update, context)
        return

    pending_recipe = ud.get(KEY_PENDING_RECIPE)
    if pending_recipe is not None:
        if text.lower() in ("yes", "ja", "oui", "si", "sí", "da", "tak", "y", "yep", "sure", "ok"):
            ud.pop(KEY_PENDING_RECIPE, None)
            profile = await _get_profile(telegram_id)
            if profile:
                await recipe_store.save_recipe(
                    telegram_id=telegram_id,
                    name=str(pending_recipe["name"]),
                    ingredients=[{"text": str(pending_recipe["ingredients_text"])}],
                    portions=int(pending_recipe["portions"]),
                    protein_per_portion_min_g=int(pending_recipe["min"]),
                    protein_per_portion_max_g=int(pending_recipe["max"]),
                )
                await update.message.reply_text("Recipe saved! I'll remember it for next time.")
        elif text.lower() in ("no", "nej", "non", "nein", "nie", "n", "nope", "cancel"):
            ud.pop(KEY_PENDING_RECIPE, None)
            await update.message.reply_text("No problem, not saved.")
        return

    pending_g = ud.get(KEY_PENDING_CORRECTION_G)
    if pending_g is not None:
        if text.lower() in ("yes", "ja", "oui", "si", "sí", "da", "tak", "y", "yep", "sure", "ok"):
            ud.pop(KEY_PENDING_CORRECTION_G, None)
            meal_id = ud.get(KEY_LAST_MEAL_ID)
            if meal_id:
                await correction_handler.apply_correction(int(meal_id), int(pending_g))
                profile = await _get_profile(telegram_id)
                if profile:
                    summary = await daily_tracker.get_daily_summary(profile)
                    await update.message.reply_text(
                        f"Updated to *{pending_g}g*. " + daily_tracker.format_summary(summary),
                        parse_mode=ParseMode.MARKDOWN,
                    )
        elif text.lower() in ("no", "nej", "non", "nein", "nie", "n", "nope", "cancel"):
            ud.pop(KEY_PENDING_CORRECTION_G, None)
            await update.message.reply_text("OK, keeping the original estimate.")
        return

    profile = await _get_profile(telegram_id)
    if not profile:
        await update.message.reply_text("Type /start to set up your profile first.")
        return

    if is_status_request(text):
        summary = await daily_tracker.get_daily_summary(profile)
        await update.message.reply_text(
            daily_tracker.format_summary(summary), parse_mode=ParseMode.MARKDOWN
        )
        return

    intent_result = await classify(text)

    if intent_result.intent == Intent.status:
        summary = await daily_tracker.get_daily_summary(profile)
        await update.message.reply_text(
            daily_tracker.format_summary(summary), parse_mode=ParseMode.MARKDOWN
        )

    elif intent_result.intent == Intent.correction and intent_result.correction_g is not None:
        g = intent_result.correction_g
        meal_id = ud.get(KEY_LAST_MEAL_ID)
        if not meal_id:
            await update.message.reply_text(
                "I'm not sure which meal you're correcting. "
                "Log a meal first, then send me the correction."
            )
            return
        if g > 200:
            await update.message.reply_text(
                f"That's quite high ({g}g) — are you sure? Reply *yes* to save or *no* to cancel.",
                parse_mode=ParseMode.MARKDOWN,
            )
        else:
            await update.message.reply_text(
                f"I'll update that to *{g}g* — shall I save it? Reply *yes* or *no*.",
                parse_mode=ParseMode.MARKDOWN,
            )
        ud[KEY_PENDING_CORRECTION_G] = g

    elif intent_result.intent == Intent.meal_suggestion:
        meal_type = intent_result.meal_type or "your next meal"
        summary = await daily_tracker.get_daily_summary(profile)
        suggestions = await suggestion_engine.suggest_for_meal(
            meal_name=meal_type,
            remaining_g=max(summary.deficit_g, 0),
            diet_style=profile.diet_style,
        )
        remaining_note = (
            f"You have *{summary.deficit_g}g* left to hit your goal today."
            if summary.deficit_g > 0
            else "You've already hit your goal today — these are just ideas!"
        )
        await update.message.reply_text(
            f"{remaining_note}\n\nSuggestions for {meal_type}:\n{suggestions}",
            parse_mode=ParseMode.MARKDOWN,
        )

    else:
        await update.message.reply_text(
            "I'm set up to help with protein tracking. Send me a food photo to log a meal, "
            "or type *status* to see today's total.",
            parse_mode=ParseMode.MARKDOWN,
        )


# ---------------------------------------------------------------------------
# 15:00 daily reminder job
# ---------------------------------------------------------------------------


async def daily_reminder(context: ContextTypes.DEFAULT_TYPE) -> None:
    rows = await db.fetch("SELECT telegram_id FROM proteinbot_users")
    for row in rows:
        telegram_id = int(row["telegram_id"])
        profile = await _get_profile(telegram_id)
        if not profile:
            continue
        try:
            summary = await daily_tracker.get_daily_summary(profile)
            if summary.deficit_g <= 0:
                await context.bot.send_message(
                    chat_id=telegram_id,
                    text=(
                        f"Afternoon check-in — you've already hit your goal today! "
                        f"{summary.total_g}g logged. Nothing more needed."
                    ),
                )
            else:
                await context.bot.send_message(
                    chat_id=telegram_id,
                    text=(
                        f"Afternoon check-in — you're at *{summary.total_g}g* of your "
                        f"*{summary.goal_g}g* goal. About *{summary.deficit_g}g* to go.\n\n"
                        "Are you planning dinner tonight?"
                    ),
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=_keyboard(("Yes", "dinner_yes"), ("No", "dinner_no")),
                )
        except Exception:
            logger.exception(f"reminder failed for {telegram_id}")


async def handle_dinner_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.callback_query and update.effective_user
    await update.callback_query.answer()
    telegram_id = update.effective_user.id
    profile = await _get_profile(telegram_id)
    if not profile:
        return

    summary = await daily_tracker.get_daily_summary(profile)
    data = update.callback_query.data

    if data == "dinner_yes":
        suggestions = await suggestion_engine.suggest_dinner(summary.deficit_g, profile.diet_style)
        extra = ""
        if summary.deficit_g > 40:
            snacks = await suggestion_engine.suggest_snacks(
                summary.deficit_g - 35, profile.diet_style
            )
            extra = f"\n\nIf dinner doesn't fully cover it, a snack could help:\n{snacks}"
        await update.callback_query.edit_message_text(
            f"Here are some dinner ideas that should get you close:\n{suggestions}{extra}"
        )
    else:
        snacks = await suggestion_engine.suggest_snacks(summary.deficit_g, profile.diet_style)
        await update.callback_query.edit_message_text(
            f"Here are some high-protein snack ideas:\n{snacks}"
        )


# ---------------------------------------------------------------------------
# App setup and run
# ---------------------------------------------------------------------------


async def _post_init(app: Application) -> None:  # type: ignore[type-arg]
    await db.apply_migrations(MIGRATIONS_DIR)
    logger.info("Migrations applied")


def build_app() -> Application:  # type: ignore[type-arg]
    token = get_settings().telegram_bot_token
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set in .env")

    app = Application.builder().token(token).post_init(_post_init).build()

    onboarding = ConversationHandler(
        entry_points=[CommandHandler("start", cmd_start)],
        states={
            OB_AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ob_age)],
            OB_WEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, ob_weight)],
            OB_HEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, ob_height)],
            OB_SEX: [CallbackQueryHandler(ob_sex, pattern="^(female|male|other)$")],
            OB_ACTIVITY: [
                CallbackQueryHandler(ob_activity, pattern="^(sedentary|moderate|regular|hard)$")
            ],
            OB_GOAL: [
                CallbackQueryHandler(ob_goal, pattern="^(maintain|lose_weight|build_muscle)$")
            ],
            OB_DIET: [CallbackQueryHandler(ob_diet, pattern="^(omnivore|vegetarian|vegan)$")],
            OB_PREGNANT: [CallbackQueryHandler(ob_pregnant, pattern="^(yes|no)$")],
            OB_MENOPAUSE: [CallbackQueryHandler(ob_menopause, pattern="^meno_(yes|no)$")],
            OB_CONFIRM_GOAL: [
                CallbackQueryHandler(ob_confirm_goal, pattern="^goal_(accept|custom)$")
            ],
            OB_CUSTOM_GOAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, ob_custom_goal)],
        },
        fallbacks=[CommandHandler("start", cmd_start)],
    )

    app.add_handler(onboarding)
    app.add_handler(CommandHandler("reset", cmd_reset))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(CallbackQueryHandler(handle_dinner_callback, pattern="^dinner_(yes|no)$"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    assert app.job_queue is not None
    app.job_queue.run_daily(
        daily_reminder,
        time=time(hour=13, minute=0, tzinfo=UTC),  # 15:00 CET (UTC+2 in summer)
    )

    return app


def main() -> None:
    setup_logging()
    app = build_app()
    logger.info("Starting protein tracker bot")
    app.run_polling()
