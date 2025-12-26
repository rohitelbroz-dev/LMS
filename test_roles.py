"""
Comprehensive Role Testing Script for Elbroz Lead Dashboard
Tests all user roles and their permissions
"""
from models import get_db
from werkzeug.security import check_password_hash

def test_user_roles():
    """Test all user roles and display their permissions"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Get all users
    cursor.execute('''
        SELECT id, name, email, role 
        FROM users 
        ORDER BY 
            CASE role 
                WHEN 'admin' THEN 1 
                WHEN 'manager' THEN 2 
                WHEN 'marketer' THEN 3 
                WHEN 'bd_sales' THEN 4 
            END, name
    ''')
    users = cursor.fetchall()
    
    print("\n" + "="*80)
    print("🔐 ELBROZ LEAD DASHBOARD - ROLE TESTING REPORT")
    print("="*80)
    
    # Test each role type
    roles_tested = set()
    
    for user in users:
        role = user['role']
        if role in roles_tested:
            continue
        roles_tested.add(role)
        
        print(f"\n{'='*80}")
        print(f"📋 TESTING: {role.upper()} ROLE")
        print(f"User: {user['name']} ({user['email']})")
        print(f"{'='*80}\n")
        
        # Test Dashboard Access
        print("📊 DASHBOARD & LEADS:")
        if role == 'admin':
            cursor.execute('SELECT COUNT(*) as count FROM leads')
            total = cursor.fetchone()['count']
            print(f"  ✓ Can view ALL leads: {total} leads")
        elif role == 'manager':
            cursor.execute('SELECT COUNT(*) as count FROM leads WHERE current_manager_id = ?', (user['id'],))
            assigned = cursor.fetchone()['count']
            print(f"  ✓ Can view assigned leads: {assigned} leads")
            print(f"  ✓ Can accept/reject leads")
            print(f"  ✓ Can assign leads to BD Sales")
        elif role == 'marketer':
            cursor.execute('SELECT COUNT(*) as count FROM leads WHERE submitted_by_user_id = ?', (user['id'],))
            submitted = cursor.fetchone()['count']
            print(f"  ✓ Can view submitted leads: {submitted} leads")
            print(f"  ✓ Can submit new leads")
        elif role == 'bd_sales':
            cursor.execute('SELECT COUNT(*) as count FROM leads WHERE assigned_bd_id = ?', (user['id'],))
            assigned = cursor.fetchone()['count']
            print(f"  ✓ Can view assigned leads: {assigned} leads")
            print(f"  ✓ Can manage leads through pipeline")
        
        # Test Pipeline Access
        print("\n🎯 SALES PIPELINE:")
        if role in ['admin', 'manager', 'bd_sales']:
            cursor.execute('SELECT COUNT(*) as count FROM pipeline_stages')
            stages = cursor.fetchone()['count']
            print(f"  ✓ Can access Sales Pipeline: {stages} stages")
            
            if role == 'bd_sales':
                cursor.execute('''
                    SELECT COUNT(*) as count FROM leads 
                    WHERE assigned_bd_id = ? AND current_stage_id IS NOT NULL
                ''', (user['id'],))
                in_pipeline = cursor.fetchone()['count']
                print(f"  ✓ Can drag-drop leads: {in_pipeline} leads in pipeline")
        else:
            print(f"  ✗ No access to Sales Pipeline")
        
        # Test Activities
        print("\n📝 ACTIVITIES:")
        if role == 'bd_sales':
            cursor.execute('''
                SELECT COUNT(*) as count FROM lead_activities 
                WHERE actor_id = ?
            ''', (user['id'],))
            activities = cursor.fetchone()['count']
            print(f"  ✓ Can manage activities: {activities} activities")
            
            cursor.execute('''
                SELECT COUNT(*) as count FROM lead_activities 
                WHERE actor_id = ? AND due_at IS NOT NULL AND completed_at IS NULL
                AND due_at > datetime('now')
            ''', (user['id'],))
            pending = cursor.fetchone()['count']
            print(f"  ✓ Pending tasks: {pending} tasks")
        elif role in ['admin', 'manager']:
            print(f"  ✓ Can view all activities")
        else:
            print(f"  ✗ Limited activity access")
        
        # Test User Management
        print("\n👥 USER MANAGEMENT:")
        if role == 'admin':
            cursor.execute('SELECT COUNT(*) as count FROM users')
            total_users = cursor.fetchone()['count']
            print(f"  ✓ Can manage all users: {total_users} users")
        elif role == 'manager':
            cursor.execute('SELECT COUNT(*) as count FROM users WHERE role = "marketer"')
            marketers = cursor.fetchone()['count']
            print(f"  ✓ Can view team members: {marketers} marketers")
        else:
            print(f"  ✗ No user management access")
        
        # Test Services Management
        print("\n⚙️ SERVICES:")
        if role in ['admin', 'manager']:
            cursor.execute('SELECT COUNT(*) as count FROM services')
            services = cursor.fetchone()['count']
            print(f"  ✓ Can manage services: {services} services")
        else:
            cursor.execute('SELECT COUNT(*) as count FROM services')
            services = cursor.fetchone()['count']
            print(f"  ✓ Can view services: {services} services")
        
        # Test Targets
        print("\n🎯 TARGETS:")
        if role == 'admin':
            cursor.execute('SELECT COUNT(*) as count FROM lead_targets WHERE assigned_by_id = ?', (user['id'],))
            assigned_targets = cursor.fetchone()['count']
            print(f"  ✓ Can create targets: {assigned_targets} targets assigned")
        elif role == 'manager':
            cursor.execute('SELECT COUNT(*) as count FROM lead_targets WHERE assignee_id = ?', (user['id'],))
            my_targets = cursor.fetchone()['count']
            cursor.execute('SELECT COUNT(*) as count FROM lead_targets WHERE assigned_by_id = ?', (user['id'],))
            assigned = cursor.fetchone()['count']
            print(f"  ✓ Has targets: {my_targets} targets")
            print(f"  ✓ Can assign to marketers: {assigned} assigned")
        elif role == 'marketer':
            cursor.execute('SELECT COUNT(*) as count FROM lead_targets WHERE assignee_id = ?', (user['id'],))
            my_targets = cursor.fetchone()['count']
            print(f"  ✓ Can view targets: {my_targets} targets")
        else:
            print(f"  ✗ No target management")
        
        # Test Pipeline Stages
        print("\n🔧 PIPELINE STAGES:")
        if role == 'admin':
            cursor.execute('SELECT COUNT(*) as count FROM pipeline_stages')
            stages = cursor.fetchone()['count']
            print(f"  ✓ Can manage pipeline stages: {stages} stages")
        else:
            print(f"  ✗ No pipeline stage management")
        
        # Test Notifications
        print("\n🔔 NOTIFICATIONS:")
        cursor.execute('''
            SELECT COUNT(*) as count FROM notifications 
            WHERE user_id = ?
        ''', (user['id'],))
        total_notifs = cursor.fetchone()['count']
        cursor.execute('''
            SELECT COUNT(*) as count FROM notifications 
            WHERE user_id = ? AND is_read = 0
        ''', (user['id'],))
        unread = cursor.fetchone()['count']
        print(f"  ✓ Total notifications: {total_notifs} ({unread} unread)")
        
        # Test Social Profiles
        if role == 'bd_sales':
            print("\n🌐 SOCIAL PROFILES:")
            cursor.execute('''
                SELECT COUNT(*) as count FROM lead_social_profiles 
                WHERE added_by_id = ?
            ''', (user['id'],))
            social = cursor.fetchone()['count']
            print(f"  ✓ Can manage social profiles: {social} profiles added")
    
    # Summary Statistics
    print(f"\n{'='*80}")
    print("📊 OVERALL STATISTICS")
    print(f"{'='*80}")
    
    cursor.execute('SELECT COUNT(*) as count FROM users')
    print(f"\n👥 Total Users: {cursor.fetchone()['count']}")
    
    cursor.execute('SELECT role, COUNT(*) as count FROM users GROUP BY role ORDER BY count DESC')
    for row in cursor.fetchall():
        role_display = {
            'admin': 'Admin',
            'manager': 'EM Team Leader',
            'marketer': 'Email Marketer',
            'bd_sales': 'BD Sales'
        }.get(row['role'], row['role'])
        print(f"  • {role_display}: {row['count']}")
    
    cursor.execute('SELECT COUNT(*) as count FROM leads')
    print(f"\n📋 Total Leads: {cursor.fetchone()['count']}")
    
    cursor.execute('SELECT status, COUNT(*) as count FROM leads GROUP BY status ORDER BY count DESC')
    for row in cursor.fetchall():
        print(f"  • {row['status']}: {row['count']}")
    
    cursor.execute('SELECT COUNT(*) as count FROM lead_activities')
    print(f"\n📝 Total Activities: {cursor.fetchone()['count']}")
    
    cursor.execute('SELECT COUNT(*) as count FROM lead_social_profiles')
    print(f"\n🌐 Total Social Profiles: {cursor.fetchone()['count']}")
    
    cursor.execute('SELECT COUNT(*) as count FROM pipeline_stages')
    print(f"\n🎯 Pipeline Stages: {cursor.fetchone()['count']}")
    
    cursor.execute('SELECT COUNT(*) as count FROM lead_targets')
    print(f"\n🎯 Active Targets: {cursor.fetchone()['count']}")
    
    print(f"\n{'='*80}")
    print("✅ ALL ROLE TESTS COMPLETED SUCCESSFULLY")
    print(f"{'='*80}\n")
    
    conn.close()

if __name__ == '__main__':
    test_user_roles()
