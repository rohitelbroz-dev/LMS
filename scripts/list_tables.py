#!/usr/bin/env python3
"""
List database tables for the current configuration (SQLite or Postgres).
Usage: python scripts/list_tables.py
"""
from dotenv import load_dotenv
load_dotenv()
import sys
import os
# Ensure project root is on sys.path so imports like `models` work when running the script directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from models import get_db, USE_POSTGRES


def main():
    conn = get_db()
    cur = conn.cursor()
    try:
        if USE_POSTGRES:
            # RealDictCursor returns dict-like rows
            cur.execute("SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname='public';")
            rows = cur.fetchall()
            # rows may be dict-like
            try:
                tables = [r['tablename'] for r in rows]
            except Exception:
                tables = [r[0] for r in rows]
        else:
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
            rows = cur.fetchall()
            tables = [r[0] for r in rows]

        print("Detected DB type:", "Postgres" if USE_POSTGRES else "SQLite")
        print("Tables:")
        for t in tables:
            print("  -", t)
    finally:
        conn.close()


if __name__ == '__main__':
    main()
