"""Dummy company database for customer_lookup. Every record here is made up."""
import sqlite3
from contextlib import closing

from harness.context import ROOT

DB_PATH = ROOT / "data" / "company.db"  # data/ is git-ignored, so this file is rebuilt when needed

CUSTOMERS = [
    # (id, name, product, monthly_spend, status)
    ("C-101", "Acme Retail", "DemoCo Dash", 1250, "active"),
    ("C-102", "Beacon Stores", "DemoCo Sync", 800, "active"),
    ("C-103", "Cedar Mart", "DemoCo Dash", 2100, "paused"),
]

REVENUE = [
    # (quarter, amount_usd): finance-only data
    ("2026-Q2", 410000),
    ("2026-Q3", 480000),
]


def connect():
    """Open the database, creating the customers table and dummy rows if they're missing."""
    DB_PATH.parent.mkdir(exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row  # lets each row be turned into a dict
    connection.execute(
        "CREATE TABLE IF NOT EXISTS customers "
        "(id TEXT PRIMARY KEY, name TEXT, product TEXT, monthly_spend INTEGER, status TEXT)"
    )
    connection.executemany("INSERT OR IGNORE INTO customers VALUES (?, ?, ?, ?, ?)", CUSTOMERS)
    connection.execute("CREATE TABLE IF NOT EXISTS revenue (quarter TEXT PRIMARY KEY, amount_usd INTEGER)")
    connection.executemany("INSERT OR IGNORE INTO revenue VALUES (?, ?)", REVENUE)
    # The outbox: send_proposal "sends" by adding a row here. Nothing leaves this machine.
    connection.execute(
        "CREATE TABLE IF NOT EXISTS outbox "
        "(id INTEGER PRIMARY KEY AUTOINCREMENT, customer TEXT, summary TEXT, created_at TEXT)"
    )
    connection.commit()
    return connection


def unsafe_lookup_demo(name):
    """DEMO ONLY, never registered as a tool. Shows why building SQL from text is dangerous."""
    with closing(connect()) as connection:
        # The name is pasted straight into the SQL text. Never do this with input you don't control.
        rows = connection.execute(f"SELECT * FROM customers WHERE name = '{name}'").fetchall()
    return [dict(row) for row in rows]


if __name__ == "__main__":
    attack = "x' OR '1'='1"
    print("Unsafe lookup with the attack:", unsafe_lookup_demo(attack))
