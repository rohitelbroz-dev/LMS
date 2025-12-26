#!/usr/bin/env python3
"""
Migration script to add bd_sales role to users table
"""
import sqlite3
from models import get_db

def migrate_users_table():
    """Migrate users table to support bd_sales role"""
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute("PRAGMA table_info(users)")
        print("📋 Current users table schema:")
        for col in cursor.fetchall():
            print(f"  - {col[1]} ({col[2]})")
        
        cursor.execute("BEGIN TRANSACTION")
        
        print("\n🔄 Creating temporary users table...")
        cursor.execute('''
            CREATE TABLE users_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('admin', 'manager', 'marketer', 'bd_sales')),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        print("📦 Copying existing user data...")
        cursor.execute('''
            INSERT INTO users_new (id, name, email, password_hash, role, created_at)
            SELECT id, name, email, password_hash, role, created_at
            FROM users
        ''')
        
        copied_count = cursor.rowcount
        print(f"✅ Copied {copied_count} users")
        
        print("🗑️  Dropping old users table...")
        cursor.execute('DROP TABLE users')
        
        print("♻️  Renaming new table to users...")
        cursor.execute('ALTER TABLE users_new RENAME TO users')
        
        cursor.execute("COMMIT")
        print("✅ Users table migration completed successfully!")
        
    except Exception as e:
        cursor.execute("ROLLBACK")
        print(f"❌ Migration failed: {e}")
        raise
    finally:
        conn.close()

if __name__ == '__main__':
    migrate_users_table()
