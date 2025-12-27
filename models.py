import os
import sqlite3
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask import g

DATABASE = 'leads.db'

# Check if PostgreSQL is available
USE_POSTGRES = os.environ.get('DATABASE_URL') is not None

if USE_POSTGRES:
    import psycopg2
    import psycopg2.extras
    # from psycopg2 import pool

    # Create connection pool
    # db_pool = None
    # if os.environ.get('DATABASE_URL'):
    #     db_pool = pool.SimpleConnectionPool(1, 3, os.environ.get('DATABASE_URL'), sslmode=os.environ.get('PGSSLMODE', 'require'))
    # else:
    #     db_pool = pool.SimpleConnectionPool(1, 3,
    #         host=os.environ.get('PGHOST'),
    #         port=os.environ.get('PGPORT'),
    #         user=os.environ.get('PGUSER'),
    #         password=os.environ.get('PGPASSWORD'),
    #         database=os.environ.get('PGDATABASE'),
    #         sslmode=os.environ.get('PGSSLMODE', 'require')
    # )

def get_db():
    """Get database connection - PostgreSQL or SQLite based on environment"""
    if 'db' not in g:
        if USE_POSTGRES:
            # Prefer DATABASE_URL if provided (works with Neon & Render). Fall back to PGHOST/PGUSER if not.
            database_url = os.environ.get('DATABASE_URL')
            sslmode = os.environ.get('PGSSLMODE', 'require')
            if database_url:
                # Use the full DATABASE_URL; enforce SSL by default
                g.db = psycopg2.connect(database_url, sslmode=sslmode)
            else:
                # Fall back to individual PG* environment variables
                g.db = psycopg2.connect(
                    host=os.environ.get('PGHOST'),
                    port=os.environ.get('PGPORT'),
                    user=os.environ.get('PGUSER'),
                    password=os.environ.get('PGPASSWORD'),
                    database=os.environ.get('PGDATABASE'),
                    sslmode=sslmode
                )
            # Use RealDictCursor for dict-like row access (similar to sqlite3.Row)
            g.db.cursor_factory = psycopg2.extras.RealDictCursor
        else:
            g.db = sqlite3.connect(DATABASE, timeout=30.0)
            g.db.row_factory = sqlite3.Row
            g.db.execute('PRAGMA journal_mode=WAL')
            g.db.execute('PRAGMA foreign_keys = ON')
    else:
        # Check if PostgreSQL connection is still alive
        if USE_POSTGRES and hasattr(g.db, 'closed') and g.db.closed:
            # Reconnect if closed
            database_url = os.environ.get('DATABASE_URL')
            sslmode = os.environ.get('PGSSLMODE', 'require')
            if database_url:
                g.db = psycopg2.connect(database_url, sslmode=sslmode)
            else:
                g.db = psycopg2.connect(
                    host=os.environ.get('PGHOST'),
                    port=os.environ.get('PGPORT'),
                    user=os.environ.get('PGUSER'),
                    password=os.environ.get('PGPASSWORD'),
                    database=os.environ.get('PGDATABASE'),
                    sslmode=sslmode
                )
            g.db.cursor_factory = psycopg2.extras.RealDictCursor
    return g.db

def close_db(e=None):
    """Close database connection"""
    db = g.pop('db', None)
    if db is not None:
        db.close()

def execute_query(cursor, sql, params=None):
    """Execute SQL using cursor and convert %s placeholders to ? for SQLite when not using Postgres"""
    # For SQLite (development), psycopg2-style %s placeholders need to be converted to qmark (?) placeholders
    if not USE_POSTGRES and params is not None and '%s' in sql:
        sql = sql.replace('%s', '?')
    if params is None:
        return cursor.execute(sql)
    return cursor.execute(sql, params)

def init_db():
    """Initialize SQLite database schema - PostgreSQL schema managed separately"""
    if USE_POSTGRES:
        # PostgreSQL schema already created via create_postgres_schema.py
        # Skip init_db to avoid conflicts with existing schema
        return
    
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('admin', 'manager', 'marketer', 'bd_sales')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS services (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            submitted_by_user_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            full_name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT NOT NULL,
            company TEXT NOT NULL,
            domain TEXT NOT NULL,
            industry VARCHAR(50),
            services_csv TEXT NOT NULL,
            country TEXT NOT NULL,
            state TEXT NOT NULL,
            city TEXT NOT NULL,
            attachment_path TEXT,
            status TEXT NOT NULL DEFAULT 'Pending' CHECK(status IN ('Pending', 'Rejected', 'Accepted', 'Resubmitted')),
            FOREIGN KEY (submitted_by_user_id) REFERENCES users(id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS lead_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER NOT NULL,
            author_user_id INTEGER NOT NULL,
            note_type TEXT NOT NULL CHECK(note_type IN ('rejection', 'resubmission', 'system', 'edit')),
            message TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (lead_id) REFERENCES leads(id),
            FOREIGN KEY (author_user_id) REFERENCES users(id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            lead_id INTEGER NOT NULL,
            message TEXT NOT NULL,
            is_read INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (lead_id) REFERENCES leads(id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS lead_edit_changes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER NOT NULL,
            editor_user_id INTEGER NOT NULL,
            field_name TEXT NOT NULL,
            old_value TEXT,
            new_value TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (lead_id) REFERENCES leads(id),
            FOREIGN KEY (editor_user_id) REFERENCES users(id)
        )
    ''')
    
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_lead_edit_changes_lead_id ON lead_edit_changes(lead_id)')
    
    # New tables for lead assignment and targets system
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
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_profiles (
            user_id INTEGER PRIMARY KEY,
            avatar_path TEXT,
            bio TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS assignment_settings (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            last_assigned_manager_id INTEGER,
            last_assigned_bd_id INTEGER,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (last_assigned_manager_id) REFERENCES users(id),
            FOREIGN KEY (last_assigned_bd_id) REFERENCES users(id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pipeline_stages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            position INTEGER NOT NULL,
            color TEXT DEFAULT '#6c757d',
            description TEXT,
            is_default INTEGER DEFAULT 0,
            created_by_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (created_by_id) REFERENCES users(id)
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_pipeline_stages_position ON pipeline_stages(position)')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS lead_stage_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER NOT NULL,
            from_stage_id INTEGER,
            to_stage_id INTEGER NOT NULL,
            changed_by_id INTEGER NOT NULL,
            note TEXT,
            changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (lead_id) REFERENCES leads(id),
            FOREIGN KEY (from_stage_id) REFERENCES pipeline_stages(id),
            FOREIGN KEY (to_stage_id) REFERENCES pipeline_stages(id),
            FOREIGN KEY (changed_by_id) REFERENCES users(id)
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_lead_stage_history_lead_id ON lead_stage_history(lead_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_lead_stage_history_changed_at ON lead_stage_history(changed_at DESC)')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS lead_activities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER NOT NULL,
            actor_id INTEGER NOT NULL,
            activity_type TEXT NOT NULL CHECK(activity_type IN ('note', 'task', 'follow_up', 'reminder', 'call_log', 'email_log', 'stage_change', 'assignment')),
            title TEXT,
            description TEXT,
            due_at TIMESTAMP,
            completed_at TIMESTAMP,
            reminder_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (lead_id) REFERENCES leads(id),
            FOREIGN KEY (actor_id) REFERENCES users(id)
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_lead_activities_lead_id ON lead_activities(lead_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_lead_activities_actor_id ON lead_activities(actor_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_lead_activities_due_at ON lead_activities(due_at)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_lead_activities_created_at ON lead_activities(created_at DESC)')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS lead_social_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER NOT NULL,
            platform TEXT NOT NULL CHECK(platform IN ('linkedin', 'twitter', 'facebook', 'instagram', 'website', 'other')),
            url TEXT NOT NULL,
            added_by_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (lead_id) REFERENCES leads(id),
            FOREIGN KEY (added_by_id) REFERENCES users(id)
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_lead_social_profiles_lead_id ON lead_social_profiles(lead_id)')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bd_assignment_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER NOT NULL,
            from_bd_id INTEGER,
            to_bd_id INTEGER NOT NULL,
            assigned_by_id INTEGER NOT NULL,
            reassigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            reason TEXT,
            FOREIGN KEY (lead_id) REFERENCES leads(id),
            FOREIGN KEY (from_bd_id) REFERENCES users(id),
            FOREIGN KEY (to_bd_id) REFERENCES users(id),
            FOREIGN KEY (assigned_by_id) REFERENCES users(id)
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_bd_assignment_history_lead_id ON bd_assignment_history(lead_id)')
    
    # Initialize assignment settings if empty
    cursor.execute('SELECT COUNT(*) FROM assignment_settings')
    if cursor.fetchone()[0] == 0:
        cursor.execute('INSERT INTO assignment_settings (id) VALUES (1)')
    
    # Add new columns to existing tables if they don't exist
    cursor.execute("PRAGMA table_info(leads)")
    existing_columns = [column[1] for column in cursor.fetchall()]
    
    if 'current_manager_id' not in existing_columns:
        cursor.execute('ALTER TABLE leads ADD COLUMN current_manager_id INTEGER REFERENCES users(id)')
    
    if 'accepted_at' not in existing_columns:
        cursor.execute('ALTER TABLE leads ADD COLUMN accepted_at TIMESTAMP')
    
    if 'rejected_at' not in existing_columns:
        cursor.execute('ALTER TABLE leads ADD COLUMN rejected_at TIMESTAMP')
    
    if 'assigned_at' not in existing_columns:
        cursor.execute('ALTER TABLE leads ADD COLUMN assigned_at TIMESTAMP')
    
    if 'assigned_bd_id' not in existing_columns:
        cursor.execute('ALTER TABLE leads ADD COLUMN assigned_bd_id INTEGER REFERENCES users(id)')
    
    if 'current_stage_id' not in existing_columns:
        cursor.execute('ALTER TABLE leads ADD COLUMN current_stage_id INTEGER REFERENCES pipeline_stages(id)')
    
    if 'deal_amount' not in existing_columns:
        cursor.execute('ALTER TABLE leads ADD COLUMN deal_amount DECIMAL(10, 2)')
    
    if 'assigned_to_bd_at' not in existing_columns:
        cursor.execute('ALTER TABLE leads ADD COLUMN assigned_to_bd_at TIMESTAMP')
    
    cursor.execute("PRAGMA table_info(notifications)")
    notification_columns = [column[1] for column in cursor.fetchall()]
    
    if 'notification_type' not in notification_columns:
        cursor.execute("ALTER TABLE notifications ADD COLUMN notification_type TEXT DEFAULT 'info' CHECK(notification_type IN ('info', 'warning', 'success', 'assignment'))")
    
    if 'sound_enabled' not in notification_columns:
        cursor.execute('ALTER TABLE notifications ADD COLUMN sound_enabled INTEGER DEFAULT 1')
    
    cursor.execute("PRAGMA table_info(assignment_settings)")
    assignment_settings_columns = [column[1] for column in cursor.fetchall()]
    
    if 'last_assigned_bd_id' not in assignment_settings_columns:
        cursor.execute('ALTER TABLE assignment_settings ADD COLUMN last_assigned_bd_id INTEGER REFERENCES users(id)')
    
    cursor.execute("PRAGMA table_info(lead_notes)")
    lead_notes_columns = [column[1] for column in cursor.fetchall()]
    
    if 'reversion' not in str(cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='lead_notes'").fetchone()):
        cursor.execute('DROP TABLE IF EXISTS lead_notes')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS lead_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lead_id INTEGER NOT NULL,
                author_user_id INTEGER NOT NULL,
                note_type TEXT NOT NULL CHECK(note_type IN ('rejection', 'resubmission', 'system', 'edit', 'reversion')),
                message TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (lead_id) REFERENCES leads(id),
                FOREIGN KEY (author_user_id) REFERENCES users(id)
            )
        ''')
    
    conn.commit()
    conn.close()

class User:
    def __init__(self, id, name, email, role):
        self.id = id
        self.name = name
        self.email = email
        self.role = role
        self.is_authenticated = True
        self.is_active = True
        self.is_anonymous = False
    
    def get_id(self):
        return str(self.id)
    
    @staticmethod
    def get(user_id):
        conn = None
        try:
            conn = get_db()
            cursor = conn.cursor()
            placeholder = '%s' if USE_POSTGRES else '?'
            cursor.execute(f'SELECT id, name, email, role FROM users WHERE id = {placeholder}', (user_id,))
            row = cursor.fetchone()
            if row:
                return User(row['id'], row['name'], row['email'], row['role'])
            return None
        except Exception as e:
            print(f"[SESSION ERROR] User.get failed for user_id '{user_id}': {e}")
            return None
        finally:
            if conn:
                conn.close()
    
    @staticmethod
    def get_by_email(email):
        conn = None
        try:
            conn = get_db()
            cursor = conn.cursor()
            placeholder = '%s' if USE_POSTGRES else '?'
            if USE_POSTGRES:
                cursor.execute(f'SELECT id, name, email, role FROM users WHERE LOWER(email) = LOWER({placeholder})', (email,))
            else:
                cursor.execute(f'SELECT id, name, email, role FROM users WHERE email = {placeholder} COLLATE NOCASE', (email,))
            row = cursor.fetchone()
            if row:
                return User(row['id'], row['name'], row['email'], row['role'])
            return None
        except Exception as e:
            print(f"[LOGIN ERROR] get_by_email failed for email '{email}': {e}")
            return None
        finally:
            if conn:
                conn.close()
    
    @staticmethod
    def verify_password(email, password):
        conn = None
        try:
            conn = get_db()
            cursor = conn.cursor()
            placeholder = '%s' if USE_POSTGRES else '?'
            if USE_POSTGRES:
                cursor.execute(f'SELECT password_hash FROM users WHERE LOWER(email) = LOWER({placeholder})', (email,))
            else:
                cursor.execute(f'SELECT password_hash FROM users WHERE email = {placeholder} COLLATE NOCASE', (email,))
            row = cursor.fetchone()
            if row and check_password_hash(row['password_hash'], password):
                return True
            return False
        except Exception as e:
            print(f"[LOGIN ERROR] verify_password failed for email '{email}': {e}")
            return False
        finally:
            if conn:
                conn.close()

class UserProfile:
    """Handles user profile data including avatars and bios"""
    
    @staticmethod
    def get_or_create(user_id):
        """Get user profile or create if doesn't exist"""
        conn = get_db()
        cursor = conn.cursor()
        placeholder = '%s' if USE_POSTGRES else '?'
        cursor.execute(f'SELECT * FROM user_profiles WHERE user_id = {placeholder}', (user_id,))
        row = cursor.fetchone()
        
        if not row:
            cursor.execute(f'''
                INSERT INTO user_profiles (user_id, avatar_path, bio)
                VALUES ({placeholder}, NULL, NULL)
            ''', (user_id,))
            conn.commit()
            cursor.execute(f'SELECT * FROM user_profiles WHERE user_id = {placeholder}', (user_id,))
            row = cursor.fetchone()
        
        conn.close()
        return {
            'user_id': row['user_id'],
            'avatar_path': row['avatar_path'],
            'bio': row['bio'],
            'updated_at': row['updated_at']
        } if row else None
    
    @staticmethod
    def update_profile(user_id, avatar_path=None, bio=None):
        """Update user profile with avatar and/or bio"""
        conn = get_db()
        cursor = conn.cursor()
        placeholder = '%s' if USE_POSTGRES else '?'
        
        cursor.execute(f'SELECT * FROM user_profiles WHERE user_id = {placeholder}', (user_id,))
        if not cursor.fetchone():
            cursor.execute(f'''
                INSERT INTO user_profiles (user_id, avatar_path, bio)
                VALUES ({placeholder}, {placeholder}, {placeholder})
            ''', (user_id, avatar_path, bio))
        else:
            if avatar_path is not None and bio is not None:
                cursor.execute(f'''
                    UPDATE user_profiles SET avatar_path = {placeholder}, bio = {placeholder}, updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = {placeholder}
                ''', (avatar_path, bio, user_id))
            elif avatar_path is not None:
                cursor.execute(f'''
                    UPDATE user_profiles SET avatar_path = {placeholder}, updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = {placeholder}
                ''', (avatar_path, user_id))
            elif bio is not None:
                cursor.execute(f'''
                    UPDATE user_profiles SET bio = {placeholder}, updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = {placeholder}
                ''', (bio, user_id))
        
        conn.commit()
        conn.close()
    
    @staticmethod
    def get_avatar_url(user_id, default='/static/img/default-avatar.png'):
        """Get avatar URL with fallback. Returns direct URL if avatar_path is a URL, otherwise uses local route."""
        conn = get_db()
        cursor = conn.cursor()
        placeholder = '%s' if USE_POSTGRES else '?'
        cursor.execute(f'SELECT avatar_path FROM user_profiles WHERE user_id = {placeholder}', (user_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row and row['avatar_path']:
            avatar = row['avatar_path']
            if isinstance(avatar, str) and avatar.startswith('http'):
                return avatar
            return f'/uploads/profile/{avatar}'
        return default
    
    @staticmethod
    def get_bio(user_id):
        """Get user bio"""
        conn = get_db()
        cursor = conn.cursor()
        placeholder = '%s' if USE_POSTGRES else '?'
        cursor.execute(f'SELECT bio FROM user_profiles WHERE user_id = {placeholder}', (user_id,))
        row = cursor.fetchone()
        conn.close()
        return row['bio'] if row and row['bio'] else ''
    
    @staticmethod
    def delete_avatar(user_id):
        """Delete user avatar file and update database"""
        from storage_helper import delete_file
        conn = get_db()
        cursor = conn.cursor()
        placeholder = '%s' if USE_POSTGRES else '?'
        cursor.execute(f'SELECT avatar_path FROM user_profiles WHERE user_id = {placeholder}', (user_id,))
        row = cursor.fetchone()
        
        if row and row['avatar_path']:
            # Delete from storage (Object Storage in production, local in development)
            delete_file(row['avatar_path'], 'uploads/profile')
            
            cursor.execute(f'''
                UPDATE user_profiles SET avatar_path = NULL, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = {placeholder}
            ''', (user_id,))
            conn.commit()
        
        conn.close()
