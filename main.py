"""
main.py
Bootstraps the bot: initializes the DB, registers all handlers, and starts
the apscheduler job that will re-check tracked product prices.
"""

import logging

from telegram.ext import Application
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import config
import database as db
from handlers import start, deals, premium

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def check_prices_job(application) -> None:
    """
    Re-check every active product's price and notify premium trackers on a drop.
    Currently a stub — plug in your real scraper/price-lookup per `source`
    (e.g. Amazon PA-API, or a lightweight scrape) where marked below.
    """
    products = await db.get_all_active_products()
    for product in products:
        # new_price = await fetch_current_price(product)  # TODO: implement
        # if new_price is None or new_price >= product["current_price"]:
        #     continue
        # await db.update_product_price(product["product_id"], new_price)
        # trackers = await db.get_trackers_for_product(product["product_id"])
        # for t in trackers:
        #     if not t["is_premium"]:
        #         continue
        #     if t["target_price"] and new_price > t["target_price"]:
        #         continue
        #     await application.bot.send_message(
        #         t["user_id"],
        #         f"📉 Price drop! {product['title']} is now {new_price} {product['currency']}",
        #     )
        continue


async def post_init(application) -> None:
    await db.init_db(config.DB_PATH)
    logger.info("Database ready.")


def main() -> None:
    application = (
        Application.builder()
        .token(config.BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    start.register(application)
    deals.register(application)
    premium.register(application)

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        check_prices_job,
        "interval",
        minutes=config.PRICE_CHECK_INTERVAL_MINUTES,
        args=[application],
    )
    scheduler.start()

    logger.info("Starting bot polling...")
    application.run_polling(allowed_updates=["message", "callback_query", "pre_checkout_query"])


if __name__ == "__main__":
    main()
