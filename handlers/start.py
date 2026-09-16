"""
handlers/start.py
/start onboarding: asks for JLPT level, then preferred material types,
and saves both to the users table.
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler

import database as db

logger = logging.getLogger(__name__)

LEVELS = ["N5", "N4", "N3", "N2", "N1"]
MATERIALS = ["Textbooks", "Anki Decks", "Kanji Workbooks", "Audio Tools"]


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await db.upsert_user(user.id, user.username)

    keyboard = [[InlineKeyboardButton(lvl, callback_data=f"level:{lvl}")] for lvl in LEVELS]
    await update.message.reply_text(
        "Welcome! 👋 What's your target JLPT level?",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def level_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    level = query.data.split(":", 1)[1]
    await db.set_user_level(query.from_user.id, level)
    context.user_data["selected_materials"] = set()

    await query.edit_message_text(f"Level set to {level}. ✅")
    await _send_materials_prompt(query.message.chat_id, context)


def _materials_keyboard(selected: set) -> InlineKeyboardMarkup:
    keyboard = []
    for m in MATERIALS:
        label = f"✅ {m}" if m in selected else m
        keyboard.append([InlineKeyboardButton(label, callback_data=f"material:{m}")])
    keyboard.append([InlineKeyboardButton("Done ✔️", callback_data="materials_done")])
    return InlineKeyboardMarkup(keyboard)


async def _send_materials_prompt(chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
    selected = context.user_data.get("selected_materials", set())
    await context.bot.send_message(
        chat_id,
        "Now pick the material types you're interested in (tap to toggle, then Done):",
        reply_markup=_materials_keyboard(selected),
    )


async def material_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    material = query.data.split(":", 1)[1]
    selected = context.user_data.setdefault("selected_materials", set())
    if material in selected:
        selected.discard(material)
    else:
        selected.add(material)

    await query.edit_message_reply_markup(_materials_keyboard(selected))


async def materials_done_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    selected = list(context.user_data.get("selected_materials", set()))
    await db.set_user_materials(query.from_user.id, selected)

    summary = ", ".join(selected) if selected else "None selected"
    await query.edit_message_text(
        f"You're all set! Materials: {summary}.\n\nRun /deals to see recommendations for your level."
    )
    context.user_data.pop("selected_materials", None)


def register(application) -> None:
    """Wire this module's handlers into the Application (called from main.py)."""
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CallbackQueryHandler(level_callback, pattern=r"^level:"))
    application.add_handler(CallbackQueryHandler(material_callback, pattern=r"^material:"))
    application.add_handler(CallbackQueryHandler(materials_done_callback, pattern=r"^materials_done$"))
  
