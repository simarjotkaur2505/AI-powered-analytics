"""
Database layer: connection management, query execution, schema introspection.
"""

import logging
import os
import re
import sqlite3
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

DB_PATH = Path(os.getenv("DB_PATH", "data/analytics.db"))

# ── Schema description injected into the LLM system prompt ───────────────────

SCHEMA_DESCRIPTION = """
Database: SQLite — e-commerce analytics

TABLE customers
  customer_id  INTEGER  PRIMARY KEY
  name         TEXT     customer full name
  email        TEXT     unique email address
  country      TEXT     country of residence (e.g. 'United States', 'India')
  signup_date  DATE     account creation date (YYYY-MM-DD)
  segment      TEXT     one of: 'Enterprise', 'SMB', 'Consumer'

TABLE products
  product_id  INTEGER  PRIMARY KEY
  name        TEXT     product name
  category    TEXT     one of: 'Electronics', 'Apparel', 'Home', 'Books', 'Sports', 'Beauty'
  unit_price  REAL     listed price per unit

TABLE orders
  order_id    INTEGER  PRIMARY KEY
  customer_id INTEGER  FK → customers.customer_id
  order_date  DATE     date order was placed (YYYY-MM-DD)
  status      TEXT     one of: 'Completed', 'Returned', 'Pending'

TABLE order_items
  item_id     INTEGER  PRIMARY KEY
  order_id    INTEGER  FK → orders.order_id
  product_id  INTEGER  FK → products.product_id
  quantity    INTEGER  units purchased
  unit_price  REAL     price paid per unit (may differ from products.unit_price)

USEFUL RELATIONSHIPS
  Revenue = SUM(order_items.quantity * order_items.unit_price)
  Filter to completed orders with: orders.status = 'Completed'
  Monthly grouping: strftime('%Y-%m', orders.order_date)
  Year grouping:    strftime('%Y', orders.order_date)
""".strip()


# ── Connection ────────────────────────────────────────────────────────────────

def get_connection() -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"Database not found at '{DB_PATH}'. "
            "Run `python data/seed.py` first."
        )
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


# ── Query execution ───────────────────────────────────────────────────────────

_SELECT_RE = re.compile(r"^\s*SELECT\b", re.IGNORECASE)


def execute_query(sql: str) -> pd.DataFrame:
    """
    Runs a SELECT query and returns a DataFrame.
    Raises ValueError for non-SELECT statements.
    Raises sqlite3.Error for malformed SQL.
    """
    sql = sql.strip()

    if not _SELECT_RE.match(sql):
        raise ValueError(
            "Only SELECT queries are allowed. "
            f"Received statement starting with: {sql[:40]!r}"
        )

    logger.info("execute_query | sql=%s", sql[:120].replace("\n", " "))

    with get_connection() as con:
        try:
            df = pd.read_sql_query(sql, con)
        except Exception as exc:
            logger.error("execute_query failed | error=%s | sql=%s", exc, sql)
            raise

    logger.info("execute_query | rows_returned=%d", len(df))
    return df


# ── Schema helper ─────────────────────────────────────────────────────────────

def get_schema_description() -> str:
    """Returns the schema string injected into LLM prompts."""
    return SCHEMA_DESCRIPTION
