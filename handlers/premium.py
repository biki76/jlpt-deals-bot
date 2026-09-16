"""
handlers/premium.py
/upgrade: sends a Telegram Stars invoice. On successful payment, flips the
user's is_premium flag so handlers/deals.py's track_callback unlocks alerts.
"""

import logging
import time

from telegram import Update, LabeledPrice
from telegram.ext import (
    ContextTypes,
    CommandHandler,
    PreCheckoutQueryHandler,
    MessageHandler,
    filters,
)

import database as db

logger = logging.getLogger(__name__)

STARS_PRICE = 150            # Telegram Stars amount — adjust to your pricing
PREMIUM_DURATION_DAYS = 30
PAYLOAD = "premium_30d"


async def upgrade_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    await context.bot.send_invoice(
        chat_id=chat_id,
        title="JLPT Deals Premium (30 days)",
        description="Real-time price-drop alerts for every item you track.",
        payload=PAYLOAD,
        provider_token="",   # must be empty string for Telegram Stars payments
        currency="XTR",
        prices=[LabeledPrice("Premium (30 days)", STARS_PRICE)],
    )


async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Telegram requires an answer within 10s or the payment is cancelled."""
    query = update.pre_checkout_query
    if query.invoice_payload != PAYLOAD:
        await query.answer(ok=False, error_message="Something went wrong — please try /upgrade again.")
    else:
        await query.answer(ok=True)


async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    premium_until = int(time.time()) + PREMIUM_DURATION_DAYS * 86400
    await db.set_premium_status(user_id, True, premium_until)

    await update.message.reply_text(
        "🎉 Premium activated! You'll now get real-time price-drop alerts for tracked items.\n"
        "Thanks for the support!"
    )
    logger.info("User %s upgraded to premium until %s", user_id, premium_until)


def register(application) -> None:
    """Wire this module's handlers into the Application (called from main.py)."""
    application.add_handler(CommandHandler("upgrade", upgrade_command))
    application.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    application.add_handler(
        MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback)
    )
