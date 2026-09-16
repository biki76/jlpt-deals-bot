"""
handlers/deals.py
/deals command: fetch recommendations filtered by the user's JLPT level
and preferred material types, render as messages with inline buttons.
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler

import database as db
from utils.affiliate import tag_affiliate_link

logger = logging.getLogger(__name__)

DEALS_PER_PAGE = 5


def _format_deal(product: dict) -> str:
    price = product.get("current_price")
    price_str = f"{price:.2f} {product.get('currency', 'USD')}" if price else "Price varies"
    return (
        f"📘 *{product['title']}*\n"
        f"Level: {product['jlpt_level']} | Category: {product['category']}\n"
        f"💰 {price_str}\n"
    )


def _build_keyboard(product: dict) -> InlineKeyboardMarkup:
    affiliate_url = product.get("affiliate_url") or tag_affiliate_link(
        product["raw_url"], product["source"]
    )
    buttons = [
        [InlineKeyboardButton("🛒 View Deal", url=affiliate_url)],
        [InlineKeyboardButton(
            "🔔 Track Price",
            callback_data=f"track:{product['product_id']}",
        )],
    ]
    return InlineKeyboardMarkup(buttons)


async def deals_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /deals — show recommendations for the user's saved level + materials."""
    user_id = update.effective_user.id
    user = await db.get_user(user_id)

    if not user or not user.get("jlpt_level"):
        await update.message.reply_text(
            "You haven't set your JLPT level yet. Run /start to set it up first."
        )
        return

    jlpt_level = user["jlpt_level"]
    material_types = user.get("material_types") or []

    deals = await db.get_deals_for_user(
        jlpt_level=jlpt_level,
        material_types=material_types,
        limit=DEALS_PER_PAGE,
    )

    if not deals:
        await update.message.reply_text(
            f"No deals found right now for {jlpt_level} in your selected categories. "
            "Check back soon — new deals get added regularly!"
        )
        return

    await update.message.reply_text(
        f"Here are the latest picks for *{jlpt_level}*:",
        parse_mode="Markdown",
    )

    for product in deals:
        await update.message.reply_text(
            _format_deal(product),
            parse_mode="Markdown",
            reply_markup=_build_keyboard(product),
            disable_web_page_preview=False,
        )


async def track_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the '🔔 Track Price' inline button. Free users are upsold to premium."""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    user = await db.get_user(user_id)
    product_id = int(query.data.split(":", 1)[1])

    if not user or not user.get("is_premium"):
        await query.message.reply_text(
            "🔒 Real-time price-drop alerts are a Premium feature.\n"
            "Run /upgrade to unlock tracking with Telegram Stars."
        )
        return

    product = await db.get_product(product_id)
    if not product:
        await query.message.reply_text("This item is no longer available.")
        return

    await db.track_item(user_id=user_id, product_id=product_id)
    await query.message.reply_text(
        f"✅ Tracking *{product['title']}*. You'll get a Telegram alert if the price drops.",
        parse_mode="Markdown",
    )


def register(application) -> None:
    """Wire this module's handlers into the Application (called from main.py)."""
    application.add_handler(CommandHandler("deals", deals_command))
    application.add_handler(CallbackQueryHandler(track_callback, pattern=r"^track:\d+$"))
