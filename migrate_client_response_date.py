"""
Migration to add client_response_date field to leads table
Adds: client_response_date column for tracking when client is expected to respond
"""

import os
from datetime import datetime
from app import app
from models import get_db, USE_POSTGRES, execute_query

def migrate_client_response_date():
    """Add client_response_date column to leads table"""
    with app.app_context():
        conn = get_db()
        cursor = conn.cursor()
        
        print("Starting client_response_date migration for leads...")
        
        if USE_POSTGRES:
            # PostgreSQL migration
            print("Migrating PostgreSQL...")
            
            try:
                # Check if column already exists
                cursor.execute("""
                    SELECT column_name FROM information_schema.columns
                    WHERE table_name = 'leads' AND column_name = 'client_response_date'
                """)
                existing_column = cursor.fetchone()
                
                if not existing_column:
                    print("  Adding client_response_date column...")
                    cursor.execute("ALTER TABLE leads ADD COLUMN client_response_date DATE")
                    print("  ✓ Column added successfully")
                else:
                    print("  Column already exists, skipping...")
                
                conn.commit()
                print("✓ PostgreSQL migration completed successfully!")
                
            except Exception as e:
                conn.rollback()
                print(f"✗ PostgreSQL migration failed: {e}")
                raise
        
        else:
            # SQLite migration
            print("Migrating SQLite...")
            
            try:
                # Check if column already exists
                cursor.execute("PRAGMA table_info(leads)")
                existing_columns = [col[1] for col in cursor.fetchall()]
                
                if 'client_response_date' not in existing_columns:
                    print("  Adding client_response_date column...")
                    cursor.execute("ALTER TABLE leads ADD COLUMN client_response_date DATE")
                    print("  ✓ Column added successfully")
                else:
                    print("  Column already exists, skipping...")
                
                conn.commit()
                print("✓ SQLite migration completed successfully!")
                
            except Exception as e:
                conn.rollback()
                print(f"✗ SQLite migration failed: {e}")
                raise
        
        conn.close()

if __name__ == '__main__':
    migrate_client_response_date()
    print("\n✓ Client response date migration completed!")
