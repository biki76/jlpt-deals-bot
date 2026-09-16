"""
config.py
Loads environment variables from .env. Import this before anything else in main.py.
"""

import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
DB_PATH = os.getenv("DB_PATH", "jlpt_bot.db")
PRICE_CHECK_INTERVAL_MINUTES = int(os.getenv("PRICE_CHECK_INTERVAL_MINUTES", "60"))

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set. Add it to your .env file (see .env.example).")
