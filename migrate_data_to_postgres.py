import os
from dotenv import load_dotenv
load_dotenv()
import sqlite3
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from psycopg2.extras import RealDictCursor

def migrate_data():
    """Migrate all data from SQLite to PostgreSQL in correct dependency order"""
    
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        print("❌ DATABASE_URL environment variable not found!")
        return False
    
    print("="*80)
    print("DATA MIGRATION: SQLite → PostgreSQL")
    print("="*80)
    
    # Connect to both databases
    print("\n📊 Connecting to databases...")
    sqlite_conn = sqlite3.connect('leads.db')
    sqlite_conn.row_factory = sqlite3.Row
    sqlite_cursor = sqlite_conn.cursor()
    
    pg_conn = psycopg2.connect(database_url)
    pg_cursor = pg_conn.cursor(cursor_factory=RealDictCursor)
    
    print("✅ Connected to SQLite and PostgreSQL")
    
    try:
        # Start transaction
        pg_conn.rollback()  # Clear any pending transaction
        
        print("\n🔄 Starting migration in dependency order...\n")
        print("   (Data inserted respecting FK constraints - no deferral needed)\n")
        
        # Track migrated rows
        migration_stats = {}
        
        # 1. Migrate users (no dependencies)
        print("📋 Migrating users...")
        sqlite_cursor.execute("SELECT * FROM users ORDER BY id")
        users = sqlite_cursor.fetchall()
        for user in users:
            pg_cursor.execute("""
                INSERT INTO users (id, name, email, password_hash, role, created_at, is_protected)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING
            """, (user['id'], user['name'], user['email'], user['password_hash'], 
                  user['role'], user['created_at'], 
                  int(user['is_protected']) if 'is_protected' in user.keys() else 0))
        migration_stats['users'] = len(users)
        print(f"  ✅ Migrated {len(users)} users")
        
        # Reset sequence for users
        if users:
            max_id = max(u['id'] for u in users)
            pg_cursor.execute(f"SELECT setval('users_id_seq', {max_id}, true)")
        
        # 2. Migrate services (no dependencies)
        print("📋 Migrating services...")
        sqlite_cursor.execute("SELECT * FROM services ORDER BY id")
        services = sqlite_cursor.fetchall()
        for service in services:
            pg_cursor.execute("""
                INSERT INTO services (id, name, created_at)
                VALUES (%s, %s, %s)
                ON CONFLICT (id) DO NOTHING
            """, (service['id'], service['name'], service['created_at']))
        migration_stats['services'] = len(services)
        print(f"  ✅ Migrated {len(services)} services")
        
        if services:
            max_id = max(s['id'] for s in services)
            pg_cursor.execute(f"SELECT setval('services_id_seq', {max_id}, true)")
        
        # 3. Migrate pipeline_stages (depends on users)
        print("📋 Migrating pipeline_stages...")
        sqlite_cursor.execute("SELECT * FROM pipeline_stages ORDER BY id")
        stages = sqlite_cursor.fetchall()
        for stage in stages:
            pg_cursor.execute("""
                INSERT INTO pipeline_stages 
                (id, name, position, color, is_default, created_by_id, created_at, description, is_protected)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING
            """, (stage['id'], stage['name'], stage['position'], stage['color'], 
                  stage['is_default'], stage['created_by_id'], stage['created_at'],
                  stage['description'], 
                  int(stage['is_protected']) if 'is_protected' in stage.keys() else 0))
        migration_stats['pipeline_stages'] = len(stages)
        print(f"  ✅ Migrated {len(stages)} pipeline stages")
        
        if stages:
            max_id = max(s['id'] for s in stages)
            pg_cursor.execute(f"SELECT setval('pipeline_stages_id_seq', {max_id}, true)")
        
        # 4. Migrate user_profiles (depends on users) - only profiles with existing users
        print("📋 Migrating user_profiles...")
        sqlite_cursor.execute("""
            SELECT up.* FROM user_profiles up
            INNER JOIN users u ON up.user_id = u.id
            ORDER BY up.user_id
        """)
        profiles = sqlite_cursor.fetchall()
        for profile in profiles:
            pg_cursor.execute("""
                INSERT INTO user_profiles (user_id, avatar_path, bio, updated_at)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (user_id) DO NOTHING
            """, (profile['user_id'], profile['avatar_path'], 
                  profile['bio'], profile['updated_at']))
        migration_stats['user_profiles'] = len(profiles)
        print(f"  ✅ Migrated {len(profiles)} user profiles")
        
        # 5. Migrate leads (depends on users, pipeline_stages)
        print("📋 Migrating leads...")
        sqlite_cursor.execute("SELECT * FROM leads ORDER BY id")
        leads = sqlite_cursor.fetchall()
        for lead in leads:
            pg_cursor.execute("""
                INSERT INTO leads 
                (id, submitted_by_user_id, created_at, full_name, email, phone, company, 
                 domain, services_csv, country, state, city, attachment_path, status,
                 current_manager_id, accepted_at, rejected_at, assigned_at, assigned_bd_id,
                 current_stage_id, deal_amount, assigned_to_bd_at, industry)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING
            """, (lead['id'], lead['submitted_by_user_id'], lead['created_at'],
                  lead['full_name'], lead['email'], lead['phone'], lead['company'],
                  lead['domain'], lead['services_csv'], lead['country'], lead['state'],
                  lead['city'], lead['attachment_path'], lead['status'],
                  lead['current_manager_id'], lead['accepted_at'], lead['rejected_at'],
                  lead['assigned_at'], lead['assigned_bd_id'], lead['current_stage_id'],
                  lead['deal_amount'], lead['assigned_to_bd_at'], lead['industry']))
        migration_stats['leads'] = len(leads)
        print(f"  ✅ Migrated {len(leads)} leads")
        
        if leads:
            max_id = max(l['id'] for l in leads)
            pg_cursor.execute(f"SELECT setval('leads_id_seq', {max_id}, true)")
        
        # 6. Migrate lead-dependent tables
        dependent_tables = [
            ('lead_activities', """
                INSERT INTO lead_activities 
                (id, lead_id, actor_id, activity_type, title, description, due_at, completed_at, reminder_at, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING
            """, ['id', 'lead_id', 'actor_id', 'activity_type', 'title', 'description', 'due_at', 'completed_at', 'reminder_at', 'created_at']),
            
            ('lead_social_profiles', """
                INSERT INTO lead_social_profiles (id, lead_id, platform, url, added_by_id, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING
            """, ['id', 'lead_id', 'platform', 'url', 'added_by_id', 'created_at']),
            
            ('lead_stage_history', """
                INSERT INTO lead_stage_history (id, lead_id, from_stage_id, to_stage_id, changed_by_id, note, changed_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING
            """, ['id', 'lead_id', 'from_stage_id', 'to_stage_id', 'changed_by_id', 'note', 'changed_at']),
            
            ('lead_assignments', """
                INSERT INTO lead_assignments 
                (id, lead_id, manager_id, assigned_at, acted_at, deadline_at, status, is_initial_assignment)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING
            """, ['id', 'lead_id', 'manager_id', 'assigned_at', 'acted_at', 'deadline_at', 'status', 'is_initial_assignment']),
            
            ('lead_assignment_history', """
                INSERT INTO lead_assignment_history 
                (id, lead_id, from_manager_id, to_manager_id, reassigned_at, reason, triggered_by)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING
            """, ['id', 'lead_id', 'from_manager_id', 'to_manager_id', 'reassigned_at', 'reason', 'triggered_by']),
            
            ('bd_assignment_history', """
                INSERT INTO bd_assignment_history 
                (id, lead_id, from_bd_id, to_bd_id, assigned_by_id, reassigned_at, reason)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING
            """, ['id', 'lead_id', 'from_bd_id', 'to_bd_id', 'assigned_by_id', 'reassigned_at', 'reason']),
            
            ('lead_edit_changes', """
                INSERT INTO lead_edit_changes 
                (id, lead_id, editor_user_id, field_name, old_value, new_value, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING
            """, ['id', 'lead_id', 'editor_user_id', 'field_name', 'old_value', 'new_value', 'created_at']),
            
            ('lead_notes', """
                INSERT INTO lead_notes (id, lead_id, author_user_id, note_type, message, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING
            """, ['id', 'lead_id', 'author_user_id', 'note_type', 'message', 'created_at']),
            
            ('notifications', """
                INSERT INTO notifications 
                (id, user_id, lead_id, message, is_read, created_at, notification_type, sound_enabled)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING
            """, ['id', 'user_id', 'lead_id', 'message', 'is_read', 'created_at', 'notification_type', 'sound_enabled']),
            
            ('lead_targets', """
                INSERT INTO lead_targets 
                (id, assigned_by_id, assignee_id, target_count, period_start, period_end, target_type, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING
            """, ['id', 'assigned_by_id', 'assignee_id', 'target_count', 'period_start', 'period_end', 'target_type', 'created_at']),
        ]
        
        for table_name, insert_sql, columns in dependent_tables:
            print(f"📋 Migrating {table_name}...")
            sqlite_cursor.execute(f"SELECT * FROM {table_name} ORDER BY id")
            rows = sqlite_cursor.fetchall()
            for row in rows:
                values = tuple(row[col] for col in columns)
                pg_cursor.execute(insert_sql, values)
            migration_stats[table_name] = len(rows)
            print(f"  ✅ Migrated {len(rows)} {table_name}")
            
            # Reset sequence
            if rows:
                max_id = max(r['id'] for r in rows)
                pg_cursor.execute(f"SELECT setval('{table_name}_id_seq', {max_id}, true)")
        
        # 7. Migrate assignment_settings
        print("📋 Migrating assignment_settings...")
        sqlite_cursor.execute("SELECT * FROM assignment_settings")
        settings = sqlite_cursor.fetchall()
        for setting in settings:
            pg_cursor.execute("""
                INSERT INTO assignment_settings (id, last_assigned_manager_id, updated_at, last_assigned_bd_id)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING
            """, (setting['id'], setting['last_assigned_manager_id'], 
                  setting['updated_at'], setting['last_assigned_bd_id']))
        migration_stats['assignment_settings'] = len(settings)
        print(f"  ✅ Migrated {len(settings)} assignment settings")
        
        if settings:
            max_id = max(s['id'] for s in settings)
            pg_cursor.execute(f"SELECT setval('assignment_settings_id_seq', {max_id}, true)")
        
        # 8. Migrate migration_log
        print("📋 Migrating migration_log...")
        sqlite_cursor.execute("SELECT * FROM migration_log")
        migrations = sqlite_cursor.fetchall()
        for mig in migrations:
            pg_cursor.execute("""
                INSERT INTO migration_log (id, migration_name, run_at)
                VALUES (%s, %s, %s)
                ON CONFLICT (id) DO NOTHING
            """, (mig['id'], mig['migration_name'], mig['run_at']))
        migration_stats['migration_log'] = len(migrations)
        print(f"  ✅ Migrated {len(migrations)} migration records")
        
        if migrations:
            max_id = max(m['id'] for m in migrations)
            pg_cursor.execute(f"SELECT setval('migration_log_id_seq', {max_id}, true)")
        
        # Commit transaction
        pg_conn.commit()
        
        print("\n" + "="*80)
        print("✅ DATA MIGRATION COMPLETE!")
        print("="*80)
        print("\n📊 Migration Summary:")
        for table, count in migration_stats.items():
            print(f"  {table:30s} {count:5d} rows")
        print("="*80)
        
        # Verify migration
        print("\n🔍 Verifying migration...")
        all_good = True
        for table in migration_stats.keys():
            pg_cursor.execute(f"SELECT COUNT(*) as count FROM {table}")
            pg_count = pg_cursor.fetchone()['count']
            if pg_count != migration_stats[table]:
                print(f"  ⚠️  {table}: Expected {migration_stats[table]}, got {pg_count}")
                all_good = False
            else:
                print(f"  ✅ {table}: {pg_count} rows verified")
        
        if all_good:
            print("\n🎉 All data verified successfully!")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Migration error: {e}")
        pg_conn.rollback()
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        sqlite_cursor.close()
        sqlite_conn.close()
        pg_cursor.close()
        pg_conn.close()

if __name__ == '__main__':
    migrate_data()
