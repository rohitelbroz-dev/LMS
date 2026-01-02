"""
Migration to add soft delete functionality to leads table
Adds: is_deleted, deleted_at, deleted_by_id columns
"""

import os
from datetime import datetime
from app import app
from models import get_db, USE_POSTGRES, execute_query

def migrate_soft_delete():
    """Add soft delete columns to leads table"""
    with app.app_context():
        conn = get_db()
        cursor = conn.cursor()
        
        print("Starting soft delete migration for leads...")
        
        if USE_POSTGRES:
            # PostgreSQL migration
            print("Migrating PostgreSQL...")
            
            try:
                # Check if columns already exist
                cursor.execute("""
                    SELECT column_name FROM information_schema.columns
                    WHERE table_name = 'leads' AND column_name IN ('is_deleted', 'deleted_at', 'deleted_by_id')
                """)
                existing_columns = [row['column_name'] for row in cursor.fetchall()]
                
                if 'is_deleted' not in existing_columns:
                    print("  Adding is_deleted column...")
                    cursor.execute("ALTER TABLE leads ADD COLUMN is_deleted BOOLEAN DEFAULT FALSE")
                
                if 'deleted_at' not in existing_columns:
                    print("  Adding deleted_at column...")
                    cursor.execute("ALTER TABLE leads ADD COLUMN deleted_at TIMESTAMP")
                
                if 'deleted_by_id' not in existing_columns:
                    print("  Adding deleted_by_id column...")
                    cursor.execute("""
                        ALTER TABLE leads ADD COLUMN deleted_by_id INTEGER REFERENCES users(id)
                    """)
                
                # Create index for deleted leads queries
                try:
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_leads_is_deleted ON leads(is_deleted)")
                    print("  Created index on is_deleted")
                except:
                    print("  Index already exists")
                
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
                # Check if columns already exist
                cursor.execute("PRAGMA table_info(leads)")
                existing_columns = [col[1] for col in cursor.fetchall()]
                
                if 'is_deleted' not in existing_columns:
                    print("  Adding is_deleted column...")
                    cursor.execute("ALTER TABLE leads ADD COLUMN is_deleted INTEGER DEFAULT 0")
                
                if 'deleted_at' not in existing_columns:
                    print("  Adding deleted_at column...")
                    cursor.execute("ALTER TABLE leads ADD COLUMN deleted_at TIMESTAMP")
                
                if 'deleted_by_id' not in existing_columns:
                    print("  Adding deleted_by_id column...")
                    cursor.execute("ALTER TABLE leads ADD COLUMN deleted_by_id INTEGER REFERENCES users(id)")
                
                # Create index for deleted leads queries
                try:
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_leads_is_deleted ON leads(is_deleted)")
                    print("  Created index on is_deleted")
                except:
                    print("  Index already exists")
                
                conn.commit()
                print("✓ SQLite migration completed successfully!")
                
            except Exception as e:
                conn.rollback()
                print(f"✗ SQLite migration failed: {e}")
                raise
        
        conn.close()

if __name__ == '__main__':
    migrate_soft_delete()
    print("\n✓ Soft delete migration completed!")
