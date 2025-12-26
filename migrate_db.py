import sqlite3
from datetime import datetime

DATABASE = 'leads.db'

def migrate_database():
    """
    Migration script to add new features:
    - Lead assignment system
    - Assignment history tracking
    - Monthly targets system
    - User profiles with pictures and bios
    - Enhanced notifications
    """
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    print("Starting database migration...")
    
    # 1. Create lead_assignments table
    print("Creating lead_assignments table...")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS lead_assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER NOT NULL,
            manager_id INTEGER NOT NULL,
            assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            acted_at TIMESTAMP,
            deadline_at TIMESTAMP NOT NULL,
            status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'acted', 'reassigned', 'expired')),
            is_initial_assignment INTEGER DEFAULT 1,
            FOREIGN KEY (lead_id) REFERENCES leads(id),
            FOREIGN KEY (manager_id) REFERENCES users(id)
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_lead_assignments_lead_id ON lead_assignments(lead_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_lead_assignments_manager_id ON lead_assignments(manager_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_lead_assignments_status ON lead_assignments(status)')
    
    # 2. Create lead_assignment_history table
    print("Creating lead_assignment_history table...")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS lead_assignment_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER NOT NULL,
            from_manager_id INTEGER,
            to_manager_id INTEGER NOT NULL,
            reassigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            reason TEXT NOT NULL,
            triggered_by TEXT NOT NULL CHECK(triggered_by IN ('admin', 'system')),
            FOREIGN KEY (lead_id) REFERENCES leads(id),
            FOREIGN KEY (from_manager_id) REFERENCES users(id),
            FOREIGN KEY (to_manager_id) REFERENCES users(id)
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_lead_assignment_history_lead_id ON lead_assignment_history(lead_id)')
    
    # 3. Create lead_targets table
    print("Creating lead_targets table...")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS lead_targets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            assigned_by_id INTEGER NOT NULL,
            assignee_id INTEGER NOT NULL,
            target_count INTEGER NOT NULL,
            period_start DATE NOT NULL,
            period_end DATE NOT NULL,
            target_type TEXT NOT NULL CHECK(target_type IN ('monthly', 'weekly')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (assigned_by_id) REFERENCES users(id),
            FOREIGN KEY (assignee_id) REFERENCES users(id),
            UNIQUE(assignee_id, period_start, period_end)
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_lead_targets_assignee ON lead_targets(assignee_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_lead_targets_period ON lead_targets(period_start, period_end)')
    
    # 4. Create user_profiles table
    print("Creating user_profiles table...")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_profiles (
            user_id INTEGER PRIMARY KEY,
            avatar_path TEXT,
            bio TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    # 5. Add columns to leads table if they don't exist
    print("Updating leads table...")
    
    # Check if columns exist before adding
    cursor.execute("PRAGMA table_info(leads)")
    existing_columns = [column[1] for column in cursor.fetchall()]
    
    if 'current_manager_id' not in existing_columns:
        cursor.execute('ALTER TABLE leads ADD COLUMN current_manager_id INTEGER REFERENCES users(id)')
        print("  - Added current_manager_id column")
    
    if 'accepted_at' not in existing_columns:
        cursor.execute('ALTER TABLE leads ADD COLUMN accepted_at TIMESTAMP')
        print("  - Added accepted_at column")
    
    if 'rejected_at' not in existing_columns:
        cursor.execute('ALTER TABLE leads ADD COLUMN rejected_at TIMESTAMP')
        print("  - Added rejected_at column")
    
    if 'assigned_at' not in existing_columns:
        cursor.execute('ALTER TABLE leads ADD COLUMN assigned_at TIMESTAMP')
        print("  - Added assigned_at column")
    
    if 'industry' not in existing_columns:
        cursor.execute('ALTER TABLE leads ADD COLUMN industry VARCHAR(50)')
        print("  - Added industry column")
    
    # 6. Add columns to notifications table
    print("Updating notifications table...")
    cursor.execute("PRAGMA table_info(notifications)")
    notification_columns = [column[1] for column in cursor.fetchall()]
    
    if 'notification_type' not in notification_columns:
        cursor.execute("ALTER TABLE notifications ADD COLUMN notification_type TEXT DEFAULT 'info' CHECK(notification_type IN ('info', 'warning', 'success', 'assignment'))")
        print("  - Added notification_type column")
    
    if 'sound_enabled' not in notification_columns:
        cursor.execute('ALTER TABLE notifications ADD COLUMN sound_enabled INTEGER DEFAULT 1')
        print("  - Added sound_enabled column")
    
    # 7. Create lead_social_profiles table
    print("Creating lead_social_profiles table...")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS lead_social_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER NOT NULL,
            platform TEXT NOT NULL CHECK(platform IN ('linkedin', 'twitter', 'facebook', 'instagram', 'website', 'other')),
            url TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (lead_id) REFERENCES leads(id)
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_lead_social_profiles_lead_id ON lead_social_profiles(lead_id)')
    
    # 8. Create assignment_settings table for round-robin tracking
    print("Creating assignment_settings table...")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS assignment_settings (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            last_assigned_manager_id INTEGER,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (last_assigned_manager_id) REFERENCES users(id)
        )
    ''')
    
    # Initialize assignment settings if empty
    cursor.execute('SELECT COUNT(*) FROM assignment_settings')
    if cursor.fetchone()[0] == 0:
        cursor.execute('INSERT INTO assignment_settings (id) VALUES (1)')
        print("  - Initialized assignment settings")
    
    conn.commit()
    conn.close()
    
    print("✅ Database migration completed successfully!")
    print("\nNew tables created:")
    print("  - lead_assignments (for tracking lead-manager assignments)")
    print("  - lead_assignment_history (for reassignment audit trail)")
    print("  - lead_targets (for monthly/weekly performance targets)")
    print("  - user_profiles (for avatars and bios)")
    print("  - assignment_settings (for round-robin tracking)")
    print("\nColumns added:")
    print("  - leads: current_manager_id, accepted_at, rejected_at, assigned_at")
    print("  - notifications: notification_type, sound_enabled")

if __name__ == '__main__':
    migrate_database()
