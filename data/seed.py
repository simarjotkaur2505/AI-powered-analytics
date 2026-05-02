"""
Generates synthetic e-commerce data and seeds analytics.db.

Run:  python data/seed.py
Re-running drops and recreates all tables cleanly.
"""

import os
import random
import sqlite3
from datetime import date, timedelta
from pathlib import Path

from faker import Faker

# ── Config ───────────────────────────────────────────────────────────────────

SEED = 42
NUM_CUSTOMERS = 1_000
NUM_PRODUCTS = 80
NUM_ORDERS = 5_000
NUM_ORDER_ITEMS_MIN = 1
NUM_ORDER_ITEMS_MAX = 5

DB_PATH = Path(__file__).parent / "analytics.db"

SEGMENTS = ["Enterprise", "SMB", "Consumer"]
SEGMENT_WEIGHTS = [0.15, 0.30, 0.55]

CATEGORIES = ["Electronics", "Apparel", "Home", "Books", "Sports", "Beauty"]
CATEGORY_WEIGHTS = [0.25, 0.20, 0.20, 0.15, 0.10, 0.10]

STATUSES = ["Completed", "Returned", "Pending"]
STATUS_WEIGHTS = [0.80, 0.12, 0.08]

COUNTRIES = [
    "United States", "United Kingdom", "Canada", "Germany", "France",
    "India", "Australia", "Brazil", "Japan", "Mexico",
]
COUNTRY_WEIGHTS = [0.35, 0.12, 0.10, 0.08, 0.07, 0.08, 0.05, 0.05, 0.05, 0.05]

START_DATE = date(2023, 1, 1)
END_DATE = date(2025, 12, 31)

# ── Helpers ───────────────────────────────────────────────────────────────────

fake = Faker()
Faker.seed(SEED)
random.seed(SEED)


def rand_date(start: date = START_DATE, end: date = END_DATE) -> date:
    delta = (end - start).days
    return start + timedelta(days=random.randint(0, delta))


def weighted_choice(population, weights):
    return random.choices(population, weights=weights, k=1)[0]


# ── DDL ───────────────────────────────────────────────────────────────────────

DDL = """
PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS order_items;
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS customers;

CREATE TABLE customers (
    customer_id  INTEGER PRIMARY KEY,
    name         TEXT    NOT NULL,
    email        TEXT    NOT NULL UNIQUE,
    country      TEXT    NOT NULL,
    signup_date  DATE    NOT NULL,
    segment      TEXT    NOT NULL
);

CREATE TABLE products (
    product_id  INTEGER PRIMARY KEY,
    name        TEXT    NOT NULL,
    category    TEXT    NOT NULL,
    unit_price  REAL    NOT NULL
);

CREATE TABLE orders (
    order_id    INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(customer_id),
    order_date  DATE    NOT NULL,
    status      TEXT    NOT NULL
);

CREATE TABLE order_items (
    item_id     INTEGER PRIMARY KEY,
    order_id    INTEGER NOT NULL REFERENCES orders(order_id),
    product_id  INTEGER NOT NULL REFERENCES products(product_id),
    quantity    INTEGER NOT NULL,
    unit_price  REAL    NOT NULL
);
"""

# ── Seed functions ────────────────────────────────────────────────────────────

def seed_customers(cur) -> list[int]:
    rows = []
    emails_seen = set()
    for i in range(1, NUM_CUSTOMERS + 1):
        email = fake.email()
        while email in emails_seen:
            email = fake.email()
        emails_seen.add(email)
        rows.append((
            i,
            fake.name(),
            email,
            weighted_choice(COUNTRIES, COUNTRY_WEIGHTS),
            rand_date(START_DATE, date(2024, 12, 31)).isoformat(),
            weighted_choice(SEGMENTS, SEGMENT_WEIGHTS),
        ))
    cur.executemany(
        "INSERT INTO customers VALUES (?,?,?,?,?,?)", rows
    )
    return [r[0] for r in rows]


def seed_products(cur) -> list[tuple]:
    price_ranges = {
        "Electronics": (50.0, 1200.0),
        "Apparel":     (15.0, 150.0),
        "Home":        (10.0, 400.0),
        "Books":       (5.0, 40.0),
        "Sports":      (20.0, 300.0),
        "Beauty":      (8.0, 80.0),
    }
    rows = []
    for i in range(1, NUM_PRODUCTS + 1):
        category = weighted_choice(CATEGORIES, CATEGORY_WEIGHTS)
        lo, hi = price_ranges[category]
        price = round(random.uniform(lo, hi), 2)
        rows.append((i, fake.catch_phrase(), category, price))
    cur.executemany(
        "INSERT INTO products VALUES (?,?,?,?)", rows
    )
    return rows  # [(product_id, name, category, unit_price), ...]


def seed_orders_and_items(cur, customer_ids, products):
    order_rows = []
    item_rows = []
    item_id = 1

    for order_id in range(1, NUM_ORDERS + 1):
        customer_id = random.choice(customer_ids)
        order_date = rand_date().isoformat()
        status = weighted_choice(STATUSES, STATUS_WEIGHTS)
        order_rows.append((order_id, customer_id, order_date, status))

        num_items = random.randint(NUM_ORDER_ITEMS_MIN, NUM_ORDER_ITEMS_MAX)
        chosen_products = random.sample(products, min(num_items, len(products)))
        for prod in chosen_products:
            product_id, _, _, base_price = prod
            quantity = random.randint(1, 5)
            # slight price variance (±10%) to simulate discounts/markups
            unit_price = round(base_price * random.uniform(0.90, 1.10), 2)
            item_rows.append((item_id, order_id, product_id, quantity, unit_price))
            item_id += 1

    cur.executemany("INSERT INTO orders VALUES (?,?,?,?)", order_rows)
    cur.executemany("INSERT INTO order_items VALUES (?,?,?,?,?)", item_rows)
    print(f"  orders:      {len(order_rows):,}")
    print(f"  order_items: {len(item_rows):,}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print(f"Seeding database → {DB_PATH}")

    if DB_PATH.exists():
        DB_PATH.unlink()
        print("  Removed existing database.")

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    cur.executescript(DDL)

    print(f"  customers:   {NUM_CUSTOMERS:,}")
    customer_ids = seed_customers(cur)

    print(f"  products:    {NUM_PRODUCTS:,}")
    products = seed_products(cur)

    seed_orders_and_items(cur, customer_ids, products)

    con.commit()
    con.close()
    print("Done. analytics.db is ready.")


if __name__ == "__main__":
    main()
