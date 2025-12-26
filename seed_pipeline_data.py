#!/usr/bin/env python3
"""
Seed script for pipeline stages and BD Sales users
"""
import sqlite3
from werkzeug.security import generate_password_hash
from models import get_db

def seed_pipeline_stages():
    """Create default pipeline stages"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT id FROM users WHERE role = "admin" LIMIT 1')
    admin_user = cursor.fetchone()
    if not admin_user:
        print("No admin user found. Please create an admin user first.")
        conn.close()
        return
    
    admin_id = admin_user['id']
    
    stages = [
        ('New Qualified Lead', 1, '#17a2b8', 1),
        ('Lead Contacted / Discovery Call', 2, '#007bff', 0),
        ('Needs Identified / Proposal', 3, '#ffc107', 0),
        ('Negotiation / Follow-Up', 4, '#fd7e14', 0),
        ('Closed – Won', 5, '#28a745', 0),
        ('Closed – Lost', 6, '#dc3545', 0),
    ]
    
    cursor.execute('SELECT COUNT(*) as count FROM pipeline_stages')
    existing_count = cursor.fetchone()['count']
    
    if existing_count == 0:
        for name, position, color, is_default in stages:
            cursor.execute('''
                INSERT INTO pipeline_stages (name, position, color_code, is_default, created_by_id)
                VALUES (?, ?, ?, ?, ?)
            ''', (name, position, color, is_default, admin_id))
        print(f"✅ Created {len(stages)} default pipeline stages")
    else:
        print(f"ℹ️  Pipeline stages already exist ({existing_count} stages found)")
    
    conn.commit()
    conn.close()

def seed_bd_sales_users():
    """Create test BD Sales users"""
    conn = get_db()
    cursor = conn.cursor()
    
    bd_users = [
        ('BD Sales 1', 'bdsales1@example.com', 'bdsales123'),
        ('BD Sales 2', 'bdsales2@example.com', 'bdsales123'),
    ]
    
    created_count = 0
    for name, email, password in bd_users:
        cursor.execute('SELECT id FROM users WHERE email = ?', (email,))
        if not cursor.fetchone():
            password_hash = generate_password_hash(password)
            cursor.execute('''
                INSERT INTO users (name, email, password_hash, role)
                VALUES (?, ?, ?, 'bd_sales')
            ''', (name, email, password_hash))
            created_count += 1
    
    if created_count > 0:
        print(f"✅ Created {created_count} BD Sales test users")
    else:
        print("ℹ️  BD Sales test users already exist")
    
    conn.commit()
    conn.close()

def main():
    print("🔧 Initializing database schema...")
    from models import init_db
    init_db()
    print("✅ Database schema initialized")
    
    print("\n📊 Seeding pipeline stages...")
    seed_pipeline_stages()
    
    print("\n👥 Seeding BD Sales users...")
    seed_bd_sales_users()
    
    print("\n✨ Seed data complete!")
    print("\nDemo Accounts:")
    print("  Admin: admin@example.com / admin123")
    print("  EM Team Leader (Manager): manager@example.com / manager123")
    print("  Email Marketer: marketer@example.com / marketer123")
    print("  BD Sales 1: bdsales1@example.com / bdsales123")
    print("  BD Sales 2: bdsales2@example.com / bdsales123")

if __name__ == '__main__':
    main()
