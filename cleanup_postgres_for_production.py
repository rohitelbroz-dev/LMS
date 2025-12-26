#!/usr/bin/env python3
import os
import psycopg2
import psycopg2.extras

print("=" * 80)
print("POSTGRESQL DATABASE CLEANUP FOR PRODUCTION")
print("=" * 80)

# Connect to PostgreSQL
conn = psycopg2.connect(
    host=os.environ.get('PGHOST'),
    port=os.environ.get('PGPORT'),
    user=os.environ.get('PGUSER'),
    password=os.environ.get('PGPASSWORD'),
    database=os.environ.get('PGDATABASE')
)
conn.autocommit = False
cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

try:
    print("\n📊 Current data counts:")
    
    # Show current counts
    tables = [
        'leads', 'lead_activities', 'lead_social_profiles', 'lead_stage_history',
        'lead_assignments', 'lead_assignment_history', 'bd_assignment_history',
        'lead_edit_changes', 'lead_notes', 'notifications', 'lead_targets'
    ]
    
    for table in tables:
        cursor.execute(f'SELECT COUNT(*) as count FROM {table}')
        count = cursor.fetchone()['count']
        print(f"  {table:30} {count:5} rows")
    
    # Confirm deletion
    print("\n⚠️  This will DELETE all data from the tables above!")
    print("   Users, services, and pipeline_stages will be PRESERVED.")
    
    # Delete data in reverse dependency order
    print("\n🗑️  Deleting test data...")
    
    cursor.execute('DELETE FROM notifications')
    print("  ✅ Deleted notifications")
    
    cursor.execute('DELETE FROM lead_targets')
    print("  ✅ Deleted lead_targets")
    
    cursor.execute('DELETE FROM lead_notes')
    print("  ✅ Deleted lead_notes")
    
    cursor.execute('DELETE FROM lead_edit_changes')
    print("  ✅ Deleted lead_edit_changes")
    
    cursor.execute('DELETE FROM bd_assignment_history')
    print("  ✅ Deleted bd_assignment_history")
    
    cursor.execute('DELETE FROM lead_assignment_history')
    print("  ✅ Deleted lead_assignment_history")
    
    cursor.execute('DELETE FROM lead_assignments')
    print("  ✅ Deleted lead_assignments")
    
    cursor.execute('DELETE FROM lead_stage_history')
    print("  ✅ Deleted lead_stage_history")
    
    cursor.execute('DELETE FROM lead_social_profiles')
    print("  ✅ Deleted lead_social_profiles")
    
    cursor.execute('DELETE FROM lead_activities')
    print("  ✅ Deleted lead_activities")
    
    cursor.execute('DELETE FROM leads')
    print("  ✅ Deleted leads")
    
    # Reset assignment round-robin state
    cursor.execute('UPDATE assignment_settings SET last_assigned_manager_id = NULL, last_assigned_bd_id = NULL WHERE id = 1')
    print("  ✅ Reset assignment round-robin state")
    
    # Commit changes
    conn.commit()
    
    print("\n📊 Final data counts:")
    for table in tables:
        cursor.execute(f'SELECT COUNT(*) as count FROM {table}')
        count = cursor.fetchone()['count']
        print(f"  {table:30} {count:5} rows")
    
    # Show preserved data
    print("\n✅ Preserved configuration:")
    cursor.execute('SELECT COUNT(*) as count FROM users')
    print(f"  Users:           {cursor.fetchone()['count']} accounts")
    
    cursor.execute('SELECT COUNT(*) as count FROM services')
    print(f"  Services:        {cursor.fetchone()['count']} services")
    
    cursor.execute('SELECT COUNT(*) as count FROM pipeline_stages')
    print(f"  Pipeline Stages: {cursor.fetchone()['count']} stages")
    
    cursor.execute('SELECT COUNT(*) as count FROM user_profiles')
    print(f"  User Profiles:   {cursor.fetchone()['count']} profiles")
    
    print("\n" + "=" * 80)
    print("✅ DATABASE CLEANUP COMPLETE!")
    print("=" * 80)
    
except Exception as e:
    conn.rollback()
    print(f"\n❌ Error during cleanup: {str(e)}")
    raise
finally:
    cursor.close()
    conn.close()
