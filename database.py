"""
database.py
Async SQLite data layer for the JLPT Deals Bot.
Uses aiosqlite for non-blocking DB access inside python-telegram-bot's async handlers.
"""

import json
import time
import logging
from typing import Optional, List, Dict, Any

import aiosqlite

logger = logging.getLogger(__name__)

DB_PATH = "jlpt_bot.db"

VALID_JLPT_LEVELS = {"N5", "N4", "N3", "N2", "N1"}
VALID_MATERIAL_TYPES = {"Textbooks", "Anki Decks", "Kanji Workbooks", "Audio Tools"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id         INTEGER PRIMARY KEY,
    username        TEXT,
    jlpt_level      TEXT,
    material_types  TEXT DEFAULT '[]',   -- JSON list
    is_premium      INTEGER DEFAULT 0,
    premium_until   INTEGER,             -- unix timestamp, NULL = lifetime/inactive
    created_at      INTEGER NOT NULL,
    updated_at      INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS products (
    product_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    title           TEXT NOT NULL,
    raw_url         TEXT NOT NULL,
    affiliate_url   TEXT NOT NULL,
    category        TEXT NOT NULL,       -- matches VALID_MATERIAL_TYPES
    jlpt_level      TEXT NOT NULL,       -- matches VALID_JLPT_LEVELS
    source          TEXT NOT NULL,       -- e.g. 'amazon', 'aliexpress'
    current_price   REAL,
    currency        TEXT DEFAULT 'USD',
    is_active       INTEGER DEFAULT 1,
    created_at      INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS price_history (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id      INTEGER NOT NULL,
    price           REAL NOT NULL,
    checked_at      INTEGER NOT NULL,
    FOREIGN KEY (product_id) REFERENCES products(product_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS tracked_items (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL,
    product_id      INTEGER NOT NULL,
    target_price    REAL,                -- NULL = alert on any drop
    created_at      INTEGER NOT NULL,
    UNIQUE(user_id, product_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products(product_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_products_level_category
    ON products(jlpt_level, category);

CREATE INDEX IF NOT EXISTS idx_tracked_user
    ON tracked_items(user_id);
"""


async def init_db(db_path: str = DB_PATH) -> None:
    """Create tables if they don't exist. Call once at startup."""
    async with aiosqlite.connect(db_path) as db:
        await db.execute("PRAGMA foreign_keys = ON;")
        await db.executescript(SCHEMA)
        await db.commit()
    logger.info("Database initialized at %s", db_path)


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

async def upsert_user(user_id: int, username: Optional[str] = None,
                       db_path: str = DB_PATH) -> None:
    """Create a user row on first contact (idempotent)."""
    now = int(time.time())
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            INSERT INTO users (user_id, username, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username = excluded.username,
                updated_at = excluded.updated_at
            """,
            (user_id, username, now, now),
        )
        await db.commit()


async def get_user(user_id: int, db_path: str = DB_PATH) -> Optional[Dict[str, Any]]:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        data = dict(row)
        data["material_types"] = json.loads(data.get("material_types") or "[]")
        return data


async def set_user_level(user_id: int, jlpt_level: str, db_path: str = DB_PATH) -> None:
    if jlpt_level not in VALID_JLPT_LEVELS:
        raise ValueError(f"Invalid JLPT level: {jlpt_level}")
    now = int(time.time())
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "UPDATE users SET jlpt_level = ?, updated_at = ? WHERE user_id = ?",
            (jlpt_level, now, user_id),
        )
        await db.commit()


async def set_user_materials(user_id: int, material_types: List[str],
                              db_path: str = DB_PATH) -> None:
    invalid = set(material_types) - VALID_MATERIAL_TYPES
    if invalid:
        raise ValueError(f"Invalid material types: {invalid}")
    now = int(time.time())
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "UPDATE users SET material_types = ?, updated_at = ? WHERE user_id = ?",
            (json.dumps(material_types), now, user_id),
        )
        await db.commit()


async def set_premium_status(user_id: int, is_premium: bool,
                              premium_until: Optional[int] = None,
                              db_path: str = DB_PATH) -> None:
    now = int(time.time())
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            UPDATE users
            SET is_premium = ?, premium_until = ?, updated_at = ?
            WHERE user_id = ?
            """,
            (int(is_premium), premium_until, now, user_id),
        )
        await db.commit()


async def get_premium_user_ids(db_path: str = DB_PATH) -> List[int]:
    """Used by the price-check scheduler to know who gets real-time alerts."""
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            "SELECT user_id FROM users WHERE is_premium = 1"
        )
        rows = await cursor.fetchall()
        return [r[0] for r in rows]


# ---------------------------------------------------------------------------
# Products / Deals
# ---------------------------------------------------------------------------

async def add_product(title: str, raw_url: str, affiliate_url: str, category: str,
                       jlpt_level: str, source: str, current_price: Optional[float] = None,
                       currency: str = "USD", db_path: str = DB_PATH) -> int:
    if category not in VALID_MATERIAL_TYPES:
        raise ValueError(f"Invalid category: {category}")
    if jlpt_level not in VALID_JLPT_LEVELS:
        raise ValueError(f"Invalid JLPT level: {jlpt_level}")
    now = int(time.time())
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            """
            INSERT INTO products
                (title, raw_url, affiliate_url, category, jlpt_level,
                 source, current_price, currency, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (title, raw_url, affiliate_url, category, jlpt_level,
             source, current_price, currency, now),
        )
        await db.commit()
        return cursor.lastrowid


async def get_deals_for_user(jlpt_level: str, material_types: List[str],
                              limit: int = 10, db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    """
    Fetch active deals matching a user's level + preferred categories.
    Falls back to level-only match if material_types is empty.
    """
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        if material_types:
            placeholders = ",".join("?" for _ in material_types)
            query = f"""
                SELECT * FROM products
                WHERE is_active = 1
                  AND jlpt_level = ?
                  AND category IN ({placeholders})
                ORDER BY created_at DESC
                LIMIT ?
            """
            params = [jlpt_level, *material_types, limit]
        else:
            query = """
                SELECT * FROM products
                WHERE is_active = 1 AND jlpt_level = ?
                ORDER BY created_at DESC
                LIMIT ?
            """
            params = [jlpt_level, limit]

        cursor = await db.execute(query, params)
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def get_product(product_id: int, db_path: str = DB_PATH) -> Optional[Dict[str, Any]]:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM products WHERE product_id = ?", (product_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def get_all_active_products(db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    """Used by the scheduler to re-check prices for every active product."""
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM products WHERE is_active = 1"
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def update_product_price(product_id: int, new_price: float,
                                db_path: str = DB_PATH) -> None:
    now = int(time.time())
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "UPDATE products SET current_price = ? WHERE product_id = ?",
            (new_price, product_id),
        )
        await db.execute(
            """
            INSERT INTO price_history (product_id, price, checked_at)
            VALUES (?, ?, ?)
            """,
            (product_id, new_price, now),
        )
        await db.commit()


# ---------------------------------------------------------------------------
# Tracked items (premium price-drop alerts)
# ---------------------------------------------------------------------------

async def track_item(user_id: int, product_id: int,
                      target_price: Optional[float] = None,
                      db_path: str = DB_PATH) -> None:
    now = int(time.time())
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            INSERT INTO tracked_items (user_id, product_id, target_price, created_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id, product_id) DO UPDATE SET
                target_price = excluded.target_price
            """,
            (user_id, product_id, target_price, now),
        )
        await db.commit()


async def untrack_item(user_id: int, product_id: int, db_path: str = DB_PATH) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "DELETE FROM tracked_items WHERE user_id = ? AND product_id = ?",
            (user_id, product_id),
        )
        await db.commit()


async def get_tracked_items(user_id: int, db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT t.id, t.target_price, p.*
            FROM tracked_items t
            JOIN products p ON p.product_id = t.product_id
            WHERE t.user_id = ?
            """,
            (user_id,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def get_trackers_for_product(product_id: int,
                                    db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    """Used by the scheduler: who to notify when a specific product's price drops."""
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT t.user_id, t.target_price, u.is_premium
            FROM tracked_items t
            JOIN users u ON u.user_id = t.user_id
            WHERE t.product_id = ?
            """,
            (product_id,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
