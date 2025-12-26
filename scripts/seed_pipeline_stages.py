#!/usr/bin/env python3
"""
Insert default pipeline stages if they are missing. Safe to run multiple times.
"""
from dotenv import load_dotenv
load_dotenv()
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from models import get_db, USE_POSTGRES

STAGES = [
    (56, 'New Lead', 1, '#6366f1', 0, 78, '2025-11-09 16:56:04', '', 0),
    (57, 'Contacted', 2, '#8b5cf6', 0, 78, '2025-11-09 16:56:04', '', 0),
    (58, 'Qualified', 3, '#06b6d4', 0, 78, '2025-11-09 16:56:04', '', 0),
    (59, 'Proposal Sent', 4, '#f59e0b', 0, 78, '2025-11-09 16:56:04', '', 0),
    (60, 'Negotiation', 5, '#f97316', 0, 78, '2025-11-09 16:56:04', '', 0),
    (61, 'Won', 6, '#10b981', 1, 78, '2025-11-09 16:56:04', '', 0),
    (62, 'Lost', 7, '#ef4444', 0, 78, '2025-11-09 16:56:04', '', 0),
]


def main():
    conn = get_db()
    cur = conn.cursor()

    try:
        # Get existing IDs
        cur.execute("SELECT id FROM pipeline_stages")
        rows = cur.fetchall()
        try:
            existing_ids = set(r['id'] for r in rows)
        except Exception:
            existing_ids = set(r[0] for r in rows)

        # Determine an existing admin user to use as created_by_id; create one if missing
        created_by_id = None
        try:
            if USE_POSTGRES:
                cur.execute("SELECT id FROM users WHERE role='admin' ORDER BY id LIMIT 1")
                row = cur.fetchone()
                if row:
                    created_by_id = row['id']
            else:
                cur.execute("SELECT id FROM users WHERE role=? ORDER BY id LIMIT 1", ('admin',))
                row = cur.fetchone()
                if row:
                    # sqlite returns Row-like or tuple
                    try:
                        created_by_id = row['id']
                    except Exception:
                        created_by_id = row[0]
        except Exception:
            created_by_id = None

        if not created_by_id:
            print('No admin user found, creating a temporary seeder admin...')
            from werkzeug.security import generate_password_hash
            pw_hash = generate_password_hash('change_me_admin_password')
            if USE_POSTGRES:
                cur.execute(
                    """
                    INSERT INTO users (name, email, password_hash, role, created_at, is_protected)
                    VALUES (%s, %s, %s, %s, NOW(), %s)
                    RETURNING id
                    """,
                    ('Seeder Admin', 'seeder@example.com', pw_hash, 'admin', 1)
                )
                created_by_id = cur.fetchone()['id']
            else:
                cur.execute(
                    "INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, ?)",
                    ('Seeder Admin', 'seeder@example.com', pw_hash, 'admin')
                )
                created_by_id = cur.lastrowid
            conn.commit()
            print(f'Created admin user with id={created_by_id}')

        # Replace provided created_by_id (78) with actual created_by_id so script is portable
        stages_with_creator = [
            (s[0], s[1], s[2], s[3], s[4], created_by_id, s[6], s[7], s[8]) for s in STAGES
        ]

        to_insert = [s for s in stages_with_creator if s[0] not in existing_ids]

        if not to_insert:
            print("All provided stages already exist. No changes made.")
            return

        print(f"Inserting {len(to_insert)} missing pipeline stages...")

        if USE_POSTGRES:
            insert_sql = ("INSERT INTO pipeline_stages "
                          "(id, name, position, color, is_default, created_by_id, created_at, description, is_protected) "
                          "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) "
                          "ON CONFLICT (id) DO NOTHING")
            for row in to_insert:
                cur.execute(insert_sql, row)

            # Ensure sequence set to at least max id
            max_id = max(s[0] for s in STAGES)
            cur.execute(f"SELECT setval('pipeline_stages_id_seq', {max_id}, true)")

        else:
            # SQLite: use INSERT OR IGNORE
            insert_sql = ("INSERT OR IGNORE INTO pipeline_stages "
                          "(id, name, position, color, is_default, created_by_id, created_at, description, is_protected) "
                          "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)")
            for row in to_insert:
                cur.execute(insert_sql, row)

        conn.commit()
        print("Insertion complete.")

    except Exception as e:
        print("Error inserting stages:", e)
        conn.rollback()
    finally:
        conn.close()


if __name__ == '__main__':
    main()
