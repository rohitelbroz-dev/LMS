import os
from dotenv import load_dotenv
load_dotenv()  # load environment variables from .env
import csv
import time
import sqlite3
from io import StringIO, BytesIO
from datetime import datetime, timedelta, date
from typing import cast
import pytz
from flask import Flask, render_template, redirect, url_for, flash, request, send_file, make_response, send_from_directory, session, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_socketio import SocketIO, emit, join_room
from flask_caching import Cache
from flask_compress import Compress
from flask_debugtoolbar import DebugToolbarExtension
# from flask_htmlmin import HTMLMIN
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash
from functools import wraps
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from models import User, get_db, init_db, USE_POSTGRES, execute_query, close_db
from forms import (LoginForm, LeadForm, RejectForm, ResubmitForm, ServiceForm, UserForm, 
                   UserEditForm, ProfileForm, LeadEditForm, TargetForm, BDAssignmentForm,
                   SocialProfileForm, ActivityForm, DealAmountForm, PipelineStageForm)
from constants import (ROLE_ADMIN, ROLE_MANAGER, ROLE_MARKETER, ROLE_BD_SALES, 
                       ROLE_LABELS, ROLE_BADGE_COLORS)
from storage_helper import upload_file, download_file, get_mime_type

# Import PostgreSQL error types if using PostgreSQL
if USE_POSTGRES:
    import psycopg2

def retry_on_db_lock(max_retries=5, initial_delay=0.1):
    """Decorator to retry database operations on lock errors"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except (sqlite3.OperationalError if not USE_POSTGRES else psycopg2.Error) as e:
                    if ('database is locked' in str(e) or 'deadlock detected' in str(e)) and attempt < max_retries - 1:
                        delay = initial_delay * (2 ** attempt)
                        time.sleep(delay)
                        continue
                    raise
            return func(*args, **kwargs)
        return wrapper
    return decorator

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SESSION_SECRET', 'dev-secret-key-change-in-production')
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
app.config['CACHE_TYPE'] = 'SimpleCache'  # Use SimpleCache for free tier, or Redis if available
app.config['CACHE_DEFAULT_TIMEOUT'] = 300  # 5 minutes

cache = Cache(app)

compress = Compress(app)
toolbar = DebugToolbarExtension(app)
# htmlmin = HTMLMIN(app)

socketio = SocketIO(app, cors_allowed_origins="*")

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'  # type: ignore[assignment]

@app.teardown_appcontext
def teardown_db(exception):
    close_db()

@login_manager.user_loader
def load_user(user_id):
    return User.get(user_id)

def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated or current_user.role not in roles:
                flash('You do not have permission to access this page.', 'danger')
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def safe_commit(conn, max_retries=5, context=""):
    """Commit database transaction with retry on lock errors and logging"""
    for attempt in range(max_retries):
        try:
            conn.commit()
            if attempt > 0:
                app.logger.info(f"Database commit succeeded after {attempt + 1} attempts{f' ({context})' if context else ''}")
            return True
        except (sqlite3.OperationalError if not USE_POSTGRES else psycopg2.Error) as e:
            if ('database is locked' in str(e) or 'deadlock detected' in str(e)) and attempt < max_retries - 1:
                delay = 0.1 * (2 ** attempt)
                app.logger.warning(f"Database locked on attempt {attempt + 1}/{max_retries}{f' ({context})' if context else ''}, retrying in {delay}s")
                time.sleep(delay)
                if USE_POSTGRES:
                    conn.rollback()  # PostgreSQL requires explicit rollback after error
                continue
            app.logger.error(f"Database commit failed after {attempt + 1} attempts{f' ({context})' if context else ''}: {str(e)}")
            raise
    return False

def get_user_avatar(user_id):
    """Get user avatar filename"""
    conn = get_db()
    cursor = conn.cursor()
    execute_query(cursor, 'SELECT avatar_path FROM user_profiles WHERE user_id = %s', (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row['avatar_path'] if row and row['avatar_path'] else None

@app.context_processor
def inject_helper_functions():
    from models import UserProfile
    return dict(
        get_avatar_url=UserProfile.get_avatar_url,
        get_user_avatar=get_user_avatar,
        ROLE_LABELS=ROLE_LABELS,
        ROLE_BADGE_COLORS=ROLE_BADGE_COLORS,
        format_indian_datetime=format_indian_datetime
    )

def convert_to_indian_timezone(dt_string):
    """Convert UTC datetime string to Indian timezone"""
    if not dt_string:
        return None
    try:
        utc_tz = pytz.UTC
        indian_tz = pytz.timezone('Asia/Kolkata')
        
        # Handle both full datetime and truncated formats
        if isinstance(dt_string, str):
            # Try with microseconds first
            try:
                dt = datetime.strptime(dt_string, '%Y-%m-%d %H:%M:%S.%f')
            except ValueError:
                # Try with full format without microseconds
                try:
                    dt = datetime.strptime(dt_string, '%Y-%m-%d %H:%M:%S')
                except ValueError:
                    # Try without seconds
                    try:
                        dt = datetime.strptime(dt_string, '%Y-%m-%d %H:%M')
                    except ValueError:
                        print(f"Failed to parse datetime: {dt_string}")
                        return None
        else:
            # If it's already a datetime object
            dt = dt_string
        
        dt_utc = utc_tz.localize(dt)
        dt_indian = dt_utc.astimezone(indian_tz)
        
        return dt_indian
    except Exception as e:
        print(f"Error converting timezone for {dt_string}: {str(e)}")
        return None

def convert_ist_to_utc(dt_obj):
    """Convert IST datetime to UTC for database storage"""
    if not dt_obj:
        return None
    try:
        indian_tz = pytz.timezone('Asia/Kolkata')
        utc_tz = pytz.UTC
        
        # Localize the naive datetime as IST
        if dt_obj.tzinfo is None:
            dt_ist = indian_tz.localize(dt_obj)
        else:
            dt_ist = dt_obj.astimezone(indian_tz)
        
        # Convert to UTC
        dt_utc = dt_ist.astimezone(utc_tz)
        
        # Return as string in the format SQLite expects
        return dt_utc.strftime('%Y-%m-%d %H:%M:%S')
    except Exception as e:
        print(f"Error converting IST to UTC for {dt_obj}: {str(e)}")
        return None

def format_indian_datetime(dt_string, format_type='full'):
    """Format datetime in Indian timezone
    format_type: 'full' = '10 November, 2025, Monday, 10:30 AM'
                 'date' = '10 November, 2025'
                 'time' = '10:30 AM'
                 'datetime' = '10 November, 2025, 10:30 AM'
    """
    if not dt_string:
        return 'N/A'
    
    try:
        dt_indian = convert_to_indian_timezone(dt_string)
        if not dt_indian:
            return dt_string
        
        if format_type == 'full':
            return dt_indian.strftime('%d %B, %Y, %A, %I:%M %p')
        elif format_type == 'date':
            return dt_indian.strftime('%d %B, %Y')
        elif format_type == 'time':
            return dt_indian.strftime('%I:%M %p')
        elif format_type == 'datetime':
            return dt_indian.strftime('%d %B, %Y, %I:%M %p')
        else:
            return dt_indian.strftime('%d %B, %Y, %A, %I:%M %p')
    except:
        return dt_string

def build_unified_timeline(lead_id, lead, cursor):
    """Build a unified activity timeline from all sources"""
    timeline = []
    
    # 1. Lead submission (from lead creation)
    if lead['created_at']:
        execute_query(cursor, 'SELECT name FROM users WHERE id = %s', (lead['submitted_by_user_id'],))
        submitter = cursor.fetchone()
        timeline.append({
            'timestamp': lead['created_at'],
            'type': 'lead_created',
            'icon': 'fa-plus-circle',
            'color': 'success',
            'title': 'Lead Submitted',
            'description': f"Lead submitted by {submitter['name'] if submitter else 'Unknown'}",
            'user_name': submitter['name'] if submitter else 'Unknown'
        })
    
    # 2. Lead notes (rejection, acceptance, edits)
    execute_query(cursor, '''
        SELECT ln.*, u.name as user_name
        FROM lead_notes ln
        JOIN users u ON ln.author_user_id = u.id
        WHERE ln.lead_id = %s
    ''', (lead_id,))
    notes = cursor.fetchall()
    
    for note in notes:
        icon = 'fa-comment'
        color = 'secondary'
        title = 'Note'
        
        if note['note_type'] == 'rejection':
            icon = 'fa-times-circle'
            color = 'danger'
            title = 'Lead Rejected'
        elif note['note_type'] == 'resubmission':
            icon = 'fa-paper-plane'
            color = 'info'
            title = 'Lead Resubmitted'
        elif note['note_type'] == 'edit':
            icon = 'fa-edit'
            color = 'warning'
            title = 'Lead Edited'
        elif note['note_type'] == 'reversion':
            icon = 'fa-undo'
            color = 'danger'
            title = 'Lead Reverted'
        elif note['note_type'] == 'system':
            icon = 'fa-info-circle'
            color = 'primary'
            if 'accepted' in note['message'].lower():
                icon = 'fa-check-circle'
                color = 'success'
                title = 'Lead Accepted'
            else:
                title = 'System Event'
        
        timeline.append({
            'timestamp': note['created_at'],
            'type': 'note',
            'icon': icon,
            'color': color,
            'title': title,
            'description': note['message'],
            'user_name': note['user_name']
        })
    
    # 3. BD Assignment history
    execute_query(cursor, '''
        SELECT bah.*, u1.name as assigned_by_name, u2.name as from_bd_name, u3.name as to_bd_name
        FROM bd_assignment_history bah
        JOIN users u1 ON bah.assigned_by_id = u1.id
        LEFT JOIN users u2 ON bah.from_bd_id = u2.id
        JOIN users u3 ON bah.to_bd_id = u3.id
        WHERE bah.lead_id = %s
    ''', (lead_id,))
    bd_assignments = cursor.fetchall()
    
    for assignment in bd_assignments:
        if assignment['from_bd_id']:
            description = f"{assignment['assigned_by_name']} reassigned lead from {assignment['from_bd_name']} to {assignment['to_bd_name']}"
            if assignment['reason']:
                description += f"\nReason: {assignment['reason']}"
            title = 'BD Reassignment'
        else:
            description = f"{assignment['assigned_by_name']} assigned lead to {assignment['to_bd_name']}"
            if assignment['reason']:
                description += f"\nNote: {assignment['reason']}"
            title = 'Assigned to BD Sales'
        
        timeline.append({
            'timestamp': assignment['reassigned_at'],
            'type': 'bd_assignment',
            'icon': 'fa-user-tie',
            'color': 'info',
            'title': title,
            'description': description,
            'user_name': assignment['assigned_by_name']
        })
    
    # 4. Stage changes
    execute_query(cursor, '''
        SELECT lsh.*, u.name as user_name, 
               ps1.name as from_stage_name, ps1.color as from_stage_color,
               ps2.name as to_stage_name, ps2.color as to_stage_color
        FROM lead_stage_history lsh
        JOIN users u ON lsh.changed_by_id = u.id
        LEFT JOIN pipeline_stages ps1 ON lsh.from_stage_id = ps1.id
        JOIN pipeline_stages ps2 ON lsh.to_stage_id = ps2.id
        WHERE lsh.lead_id = %s
    ''', (lead_id,))
    stage_changes = cursor.fetchall()
    
    for change in stage_changes:
        if change['from_stage_name']:
            description = f"Stage changed from '{change['from_stage_name']}' to '{change['to_stage_name']}'"
        else:
            description = f"Stage set to '{change['to_stage_name']}'"
        
        if change['note']:
            description += f"\nNote: {change['note']}"
        
        timeline.append({
            'timestamp': change['changed_at'],
            'type': 'stage_change',
            'icon': 'fa-exchange-alt',
            'color': 'purple',
            'title': 'Pipeline Stage Changed',
            'description': description,
            'user_name': change['user_name'],
            'to_stage_name': change['to_stage_name'],
            'to_stage_color': change['to_stage_color']
        })
    
    # 5. Activities (notes, tasks, calls, emails, follow-ups)
    execute_query(cursor, '''
        SELECT la.*, u.name as user_name
        FROM lead_activities la
        JOIN users u ON la.actor_id = u.id
        WHERE la.lead_id = %s
    ''', (lead_id,))
    activities = cursor.fetchall()
    
    for activity in activities:
        icon = 'fa-sticky-note'
        color = 'info'
        
        if activity['activity_type'] == 'note':
            icon = 'fa-sticky-note'
            color = 'info'
        elif activity['activity_type'] == 'task':
            icon = 'fa-tasks'
            color = 'warning'
        elif activity['activity_type'] == 'follow_up':
            icon = 'fa-phone-volume'
            color = 'success'
        elif activity['activity_type'] == 'call_log':
            icon = 'fa-phone'
            color = 'primary'
        elif activity['activity_type'] == 'email_log':
            icon = 'fa-envelope'
            color = 'secondary'
        elif activity['activity_type'] == 'assignment':
            icon = 'fa-user-plus'
            color = 'info'
        elif activity['activity_type'] == 'stage_change':
            icon = 'fa-exchange-alt'
            color = 'purple'
        
        title_text = activity['title'] if activity['title'] else activity['activity_type'].replace('_', ' ').title()
        
        timeline.append({
            'id': activity['id'],
            'timestamp': activity['created_at'],
            'type': 'activity',
            'activity_type': activity['activity_type'],
            'icon': icon,
            'color': color,
            'title': title_text,
            'description': activity['description'],
            'user_name': activity['user_name'],
            'due_at': activity['due_at'] if 'due_at' in activity.keys() else None,
            'completed_at': activity['completed_at'] if 'completed_at' in activity.keys() else None,
            'reminder_at': activity['reminder_at'] if 'reminder_at' in activity.keys() else None
        })
    
    # Sort by timestamp DESC (latest first)
    timeline.sort(key=lambda x: x['timestamp'], reverse=True)
    
    return timeline

def get_next_manager_for_assignment(conn=None):
    """Get next manager for round-robin assignment. If conn is provided, reuse it."""
    should_close = False
    if conn is None:
        conn = get_db()
        should_close = True
    
    cursor = conn.cursor()
    
    execute_query(cursor, 'SELECT id FROM users WHERE role = %s ORDER BY id', ('manager',))
    managers = cursor.fetchall()
    
    if not managers:
        if should_close:
            conn.close()
        return None
    
    manager_ids = [m['id'] for m in managers]
    
    cursor.execute('SELECT last_assigned_manager_id, last_assigned_bd_id FROM assignment_settings WHERE id = 1')
    settings = cursor.fetchone()
    
    if settings:
        last_assigned_id = settings['last_assigned_manager_id']
        current_bd_id = settings['last_assigned_bd_id']
    else:
        last_assigned_id = None
        current_bd_id = None
    
    if last_assigned_id and last_assigned_id in manager_ids:
        current_index = manager_ids.index(last_assigned_id)
        next_index = (current_index + 1) % len(manager_ids)
        next_manager_id = manager_ids[next_index]
    else:
        next_manager_id = manager_ids[0]
    
    if settings:
        execute_query(cursor, '''
            UPDATE assignment_settings 
            SET last_assigned_manager_id = %s, updated_at = CURRENT_TIMESTAMP 
            WHERE id = 1
        ''', (next_manager_id,))
    else:
        execute_query(cursor, '''
            INSERT INTO assignment_settings (id, last_assigned_manager_id, last_assigned_bd_id, updated_at)
            VALUES (1, %s, %s, CURRENT_TIMESTAMP)
        ''', (next_manager_id, current_bd_id))
    
    if should_close:
        safe_commit(conn, context="get_next_manager_for_assignment")
        conn.close()
    
    return next_manager_id

def peek_next_bd_sales_for_assignment():
    """Peek at next BD Sales user for round-robin suggestion (read-only, no pointer update)"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT id FROM users WHERE role = %s ORDER BY id', (ROLE_BD_SALES,))
    bd_sales = cursor.fetchall()
    
    if not bd_sales:
        conn.close()
        return None
    
    bd_ids = [b['id'] for b in bd_sales]
    
    cursor.execute('SELECT last_assigned_bd_id FROM assignment_settings WHERE id = 1')
    settings = cursor.fetchone()
    
    if not settings:
        cursor.execute('''
            INSERT INTO assignment_settings (id, last_assigned_manager_id, last_assigned_bd_id, updated_at)
            VALUES (1, NULL, NULL, CURRENT_TIMESTAMP)
        ''')
        safe_commit(conn, context="peek_next_bd_sales_for_assignment")
        last_assigned_id = None
    else:
        last_assigned_id = settings['last_assigned_bd_id']
    
    if last_assigned_id and last_assigned_id in bd_ids:
        current_index = bd_ids.index(last_assigned_id)
        next_index = (current_index + 1) % len(bd_ids)
        next_bd_id = bd_ids[next_index]
    else:
        next_bd_id = bd_ids[0]
    
    conn.close()
    return next_bd_id

def commit_bd_sales_assignment(bd_sales_id):
    """Update round-robin pointer to the actually assigned BD Sales user (commit after successful assignment)"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT id FROM assignment_settings WHERE id = 1')
    if not cursor.fetchone():
        cursor.execute('''
            INSERT INTO assignment_settings (id, last_assigned_manager_id, last_assigned_bd_id, updated_at)
            VALUES (1, NULL, %s, CURRENT_TIMESTAMP)
        ''', (bd_sales_id,))
    else:
        cursor.execute('''
            UPDATE assignment_settings 
            SET last_assigned_bd_id = %s, updated_at = CURRENT_TIMESTAMP 
            WHERE id = 1
        ''', (bd_sales_id,))
    
    safe_commit(conn, context="commit_bd_sales_assignment")
    conn.close()

def send_realtime_notification(user_id, message, notification_type='info', play_sound=True):
    """Send real-time notification via SocketIO to specific user"""
    socketio.emit('notification', {
        'message': message,
        'type': notification_type,
        'play_sound': play_sound,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }, room=f'user_{user_id}')

def compute_target_progress(target, cursor=None):
    """Calculate progress for a target (actual count vs target count)"""
    own_connection = False
    conn = None
    if cursor is None:
        conn = get_db()
        cursor = conn.cursor()
        own_connection = True
    
    cursor.execute('SELECT role FROM users WHERE id = %s', (target['assignee_id'],))
    assignee = cursor.fetchone()
    
    if not assignee:
        if own_connection and conn:
            conn.close()
        return {'actual': 0, 'target': target['target_count'], 'percent': 0}
    
    if assignee['role'] == 'manager':
        cursor.execute('''
            SELECT COUNT(DISTINCT la.lead_id) as count 
            FROM lead_assignments la
            JOIN leads l ON la.lead_id = l.id
            WHERE la.manager_id = %s
            AND la.status = 'acted'
            AND l.status = 'Accepted'
            AND DATE(la.acted_at) BETWEEN %s AND %s
        ''', (target['assignee_id'], target['period_start'], target['period_end']))
    else:
        cursor.execute('''
            SELECT COUNT(*) as count FROM leads 
            WHERE submitted_by_user_id = %s 
            AND status != 'Rejected'
            AND DATE(created_at) BETWEEN %s AND %s
        ''', (target['assignee_id'], target['period_start'], target['period_end']))
    
    result = cursor.fetchone()
    actual_count = result['count'] if result else 0
    
    if own_connection and conn:
        conn.close()
    
    return {
        'actual': actual_count,
        'target': target['target_count'],
        'percent': (actual_count / target['target_count'] * 100) if target['target_count'] > 0 else 0
    }

def has_period_overlap(assignee_id, period_start, period_end, exclude_id=None):
    """Check if target period overlaps with existing targets for same assignee"""
    conn = get_db()
    cursor = conn.cursor()
    
    query = '''
        SELECT id FROM lead_targets 
        WHERE assignee_id = %s 
        AND ((DATE(period_start) <= DATE(%s) AND DATE(period_end) >= DATE(%s))
        OR (DATE(period_start) <= DATE(%s) AND DATE(period_end) >= DATE(%s))
        OR (DATE(period_start) >= DATE(%s) AND DATE(period_end) <= DATE(%s)))
    '''
    
    params = [assignee_id, period_end, period_end, period_start, period_start, period_start, period_end]
    
    if exclude_id:
        query += ' AND id != %s'
        params.append(exclude_id)
    
    cursor.execute(query, params)
    result = cursor.fetchone()
    conn.close()
    
    return result is not None

def check_and_reassign_overdue_leads():
    """Check for overdue lead assignments and reassign them"""
    start_time = time.time()
    with app.app_context():
        conn = get_db()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                SELECT COUNT(*) as count FROM lead_assignments la
                JOIN leads l ON la.lead_id = l.id
                WHERE la.status = 'pending'
                  AND la.deadline_at < CURRENT_TIMESTAMP
                  AND l.status IN ('Pending', 'Resubmitted')
            ''')
            
            overdue_count = cursor.fetchone()['count']
            if overdue_count == 0:
                print(f'No overdue assignments found')
                conn.close()
                return
            
            print(f'Found {overdue_count} overdue assignments, processing...')
            
            cursor.execute('''
                SELECT la.id as assignment_id, la.lead_id, la.manager_id, la.deadline_at, 
                       la.is_initial_assignment, l.company, l.full_name, u.name as manager_name
                FROM lead_assignments la
                JOIN leads l ON la.lead_id = l.id
                JOIN users u ON la.manager_id = u.id
                WHERE la.status = 'pending'
                  AND la.deadline_at < CURRENT_TIMESTAMP
                  AND l.status IN ('Pending', 'Resubmitted')
                ORDER BY la.deadline_at ASC
                LIMIT 10
            ''')
            
            overdue_assignments = cursor.fetchall()
            
            for assignment in overdue_assignments:
                lead_id = assignment['lead_id']
                old_manager_id = assignment['manager_id']
                assignment_id = assignment['assignment_id']
                is_initial = assignment['is_initial_assignment']
                company = assignment['company']
                
                cursor.execute('SELECT id FROM users WHERE role = %s AND id != %s ORDER BY id', (old_manager_id,))
                other_managers = cursor.fetchall()
                
                if not other_managers:
                    print(f'No other managers available to reassign lead {lead_id}')
                    continue
                
                new_manager_id = get_next_manager_for_assignment()
                if new_manager_id == old_manager_id and len(other_managers) > 0:
                    new_manager_id = other_managers[0]['id']
                
                # Note: reassigned_at column doesn't exist, removing this UPDATE
                # cursor.execute('UPDATE lead_assignments SET reassigned_at = CURRENT_TIMESTAMP WHERE id = %s', 
                #              (assignment_id,))
                
                next_deadline_hours = 4 if is_initial else 4
                cursor.execute('''
                    INSERT INTO lead_assignments (lead_id, manager_id, deadline_at, is_initial_assignment)
                    VALUES (%s, %s, NOW() + INTERVAL '%s hours', 0)
                    RETURNING id
                ''', (lead_id, new_manager_id, next_deadline_hours))
                
                new_assignment_id = cursor.fetchone()['id']
                
                cursor.execute('''
                    INSERT INTO lead_assignment_history (assignment_id, lead_id, old_manager_id, 
                                                         new_manager_id, reassignment_reason)
                    VALUES (%s, %s, %s, %s, %s)
                ''', (assignment_id, lead_id, old_manager_id, new_manager_id, 
                     'Automatic reassignment due to missed deadline'))
                
                cursor.execute('UPDATE leads SET current_manager_id = %s WHERE id = %s', 
                             (new_manager_id, lead_id))
                
                cursor.execute('SELECT name FROM users WHERE id = %s', (new_manager_id,))
                new_manager = cursor.fetchone()
                
                cursor.execute('''
                    INSERT INTO lead_notes (lead_id, author_user_id, note_type, message)
                    VALUES (%s, 1, 'system', %s)
                ''', (lead_id, f'Lead auto-reassigned from {assignment["manager_name"]} to {new_manager["name"]} due to missed deadline'))
                
                notification_msg = f'Lead for {company} has been reassigned to you (previous manager missed deadline)'
                cursor.execute('''
                    INSERT INTO notifications (user_id, lead_id, message, notification_type)
                    VALUES (%s, %s, %s, 'assignment')
                ''', (new_manager_id, lead_id, notification_msg))
                
                send_realtime_notification(new_manager_id, notification_msg, 'assignment', play_sound=True)
                
                old_manager_msg = f'Lead for {company} was reassigned (deadline missed)'
                cursor.execute('''
                    INSERT INTO notifications (user_id, lead_id, message, notification_type)
                    VALUES (%s, %s, %s, 'warning')
                ''', (old_manager_id, lead_id, old_manager_msg))
                
                send_realtime_notification(old_manager_id, old_manager_msg, 'warning', play_sound=True)
                
                print(f'Reassigned lead {lead_id} from manager {old_manager_id} to {new_manager_id}')
            
            safe_commit(conn, context="check_and_reassign_overdue_leads")
            end_time = time.time()
            print(f'Processed {len(overdue_assignments)} overdue assignments in {end_time - start_time:.2f} seconds')
            
        except Exception as e:
            print(f'Error in reassignment check: {str(e)}')
            conn.rollback()
        finally:
            conn.close()

def check_and_send_activity_reminders():
    """Check for activity reminders that are due and send notifications"""
    start_time = time.time()
    with app.app_context():
        conn = get_db()
        cursor = conn.cursor()
        
        try:
            # Count reminders first
            cursor.execute('''
                SELECT COUNT(*) as count FROM lead_activities la
                WHERE la.reminder_at IS NOT NULL 
                  AND la.reminder_at <= NOW()
                  AND la.completed_at IS NULL
            ''')
            
            reminder_count = cursor.fetchone()['count']
            if reminder_count == 0:
                print('No activity reminders due')
                conn.close()
                return
            
            print(f'Found {reminder_count} activity reminders due, processing...')
            
            # Find activities with reminders due (reminder_at is now or past) and not completed
            cursor.execute('''
                SELECT la.id, la.lead_id, la.actor_id, la.activity_type, la.title, 
                       la.description, la.reminder_at, la.due_at,
                       l.company, l.full_name as lead_name, u.name as user_name
                FROM lead_activities la
                JOIN leads l ON la.lead_id = l.id
                JOIN users u ON la.actor_id = u.id
                WHERE la.reminder_at IS NOT NULL 
                  AND la.reminder_at <= NOW()
                  AND la.completed_at IS NULL
                ORDER BY la.reminder_at ASC
                LIMIT 20
            ''')
            
            activities_with_reminders = cursor.fetchall()
            
            for activity in activities_with_reminders:
                activity_id = activity['id']
                actor_id = activity['actor_id']
                lead_id = activity['lead_id']
                activity_type = activity['activity_type']
                title = activity['title'] or activity_type.replace('_', ' ').title()
                company = activity['company']
                
                # Create notification message with activity_id for deduplication
                if activity['due_at']:
                    notification_msg = f'Reminder: {title} for {company} (Due: {activity["due_at"][:10]}) [Activity #{activity_id}]'
                else:
                    notification_msg = f'Reminder: {title} for {company} [Activity #{activity_id}]'
                
                # Check if we've already sent a reminder for this specific activity today
                cursor.execute('''
                    SELECT id FROM notifications 
                    WHERE user_id = %s 
                      AND message LIKE %s
                      AND DATE(created_at) = CURRENT_DATE
                ''', (actor_id, f'%[Activity #{activity_id}]'))
                
                existing_notification = cursor.fetchone()
                
                if existing_notification:
                    # Already sent a reminder for this specific activity today, skip
                    continue
                
                # Insert notification to database
                cursor.execute('''
                    INSERT INTO notifications (user_id, lead_id, message, notification_type)
                    VALUES (%s, %s, %s, 'info')
                ''', (actor_id, lead_id, notification_msg))
                
                # Send real-time notification via Socket.IO
                send_realtime_notification(actor_id, notification_msg, 'reminder', play_sound=True)
                
                print(f'Sent reminder for activity {activity_id} to user {actor_id}: {notification_msg}')
            
            safe_commit(conn, context="check_and_send_activity_reminders")
            end_time = time.time()
            print(f'Processed {len(activities_with_reminders)} activity reminders in {end_time - start_time:.2f} seconds')
            
        except Exception as e:
            print(f'Error in reminder check: {str(e)}')
            conn.rollback()
        finally:
            conn.close()

@socketio.on('connect')
def handle_connect():
    """Handle client connection to SocketIO"""
    if current_user.is_authenticated:
        join_room(f'user_{current_user.id}')
        print(f'User {current_user.id} connected to SocketIO')

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    if current_user.is_authenticated:
        print(f'User {current_user.id} disconnected from SocketIO')

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    form = LoginForm()
    if form.validate_on_submit():
        if User.verify_password(form.email.data, form.password.data):
            user = User.get_by_email(form.email.data)
            if user:
                login_user(user)
                flash(f'Welcome back, {user.name}!', 'success')
                return redirect(url_for('dashboard'))
            else:
                flash('Invalid email or password.', 'danger')
        else:
            flash('Invalid email or password.', 'danger')
    
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute(
        'SELECT COUNT(*) as count FROM notifications WHERE user_id = %s AND is_read = 0',
        (current_user.id,)
    )
    unread_count = cursor.fetchone()['count']
    
    status_filter = request.args.get('status', '')
    service_filter = request.args.get('service', '')
    submitter_filter = request.args.get('submitter', '')
    date_range = request.args.get('date_range', 'current_month')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    
    from datetime import date
    from calendar import monthrange
    
    if not date_from and not date_to and date_range:
        today = date.today()
        if date_range == 'current_month':
            date_from = today.replace(day=1).isoformat()
            last_day = monthrange(today.year, today.month)[1]
            date_to = today.replace(day=last_day).isoformat()
        elif date_range == 'last_month':
            if today.month == 1:
                last_month = date(today.year - 1, 12, 1)
            else:
                last_month = date(today.year, today.month - 1, 1)
            date_from = last_month.isoformat()
            last_day = monthrange(last_month.year, last_month.month)[1]
            date_to = last_month.replace(day=last_day).isoformat()
        elif date_range == 'this_week':
            weekday = today.weekday()
            date_from = (today - __import__('datetime').timedelta(days=weekday)).isoformat()
            date_to = (today + __import__('datetime').timedelta(days=6-weekday)).isoformat()
        elif date_range == 'all_time':
            date_from = ''
            date_to = ''
    
    if current_user.role == 'marketer':
        query = 'SELECT * FROM leads WHERE submitted_by_user_id = %s'
        params = [current_user.id]
    elif current_user.role == 'bd_sales':
        # BD Sales only sees leads assigned to them
        query = 'SELECT * FROM leads WHERE assigned_bd_id = %s'
        params = [current_user.id]
    else:
        # Admin and Manager see all leads
        query = 'SELECT * FROM leads WHERE 1=1'
        params = []
    
    if status_filter:
        query += ' AND status = %s'
        params.append(status_filter)
    
    if service_filter:
        query += ' AND (services_csv LIKE %s OR services_csv LIKE %s OR services_csv LIKE %s OR services_csv = %s)'
        params.extend([f'{service_filter},%', f'%,{service_filter},%', f'%,{service_filter}', service_filter])
    
    if submitter_filter and current_user.role in ['admin', 'manager']:
        query += ' AND submitted_by_user_id = %s'
        params.append(submitter_filter)
    
    if date_from:
        query += ' AND DATE(created_at) >= %s'
        params.append(date_from)
    
    if date_to:
        query += ' AND DATE(created_at) <= %s'
        params.append(date_to)
    
    # Get all leads with submitter info and deadlines in single queries
    if current_user.role == 'marketer':
        base_query = '''
            SELECT l.*, u.name as submitter_name, la.deadline_at,
                   CASE WHEN la.deadline_at < CURRENT_TIMESTAMP THEN 1 ELSE 0 END as is_overdue
            FROM leads l
            LEFT JOIN users u ON l.submitted_by_user_id = u.id
            LEFT JOIN lead_assignments la ON l.id = la.lead_id 
                AND la.status = 'pending' 
                AND la.deadline_at = (
                    SELECT MAX(deadline_at) FROM lead_assignments 
                    WHERE lead_id = l.id AND status = 'pending'
                )
            WHERE l.submitted_by_user_id = %s
        '''
        params = [current_user.id]
    elif current_user.role == 'bd_sales':
        base_query = '''
            SELECT l.*, u.name as submitter_name, la.deadline_at,
                   CASE WHEN la.deadline_at < CURRENT_TIMESTAMP THEN 1 ELSE 0 END as is_overdue
            FROM leads l
            LEFT JOIN users u ON l.submitted_by_user_id = u.id
            LEFT JOIN lead_assignments la ON l.id = la.lead_id 
                AND la.status = 'pending' 
                AND la.deadline_at = (
                    SELECT MAX(deadline_at) FROM lead_assignments 
                    WHERE lead_id = l.id AND status = 'pending'
                )
            WHERE l.assigned_bd_id = %s
        '''
        params = [current_user.id]
    else:
        base_query = '''
            SELECT l.*, u.name as submitter_name, la.deadline_at,
                   CASE WHEN la.deadline_at < CURRENT_TIMESTAMP THEN 1 ELSE 0 END as is_overdue
            FROM leads l
            LEFT JOIN users u ON l.submitted_by_user_id = u.id
            LEFT JOIN lead_assignments la ON l.id = la.lead_id 
                AND la.status = 'pending' 
                AND la.deadline_at = (
                    SELECT MAX(deadline_at) FROM lead_assignments 
                    WHERE lead_id = l.id AND status = 'pending'
                )
            WHERE 1=1
        '''
        params = []
    
    if status_filter:
        base_query += ' AND l.status = %s'
        params.append(status_filter)
    
    if service_filter:
        base_query += ' AND (l.services_csv LIKE %s OR l.services_csv LIKE %s OR l.services_csv LIKE %s OR l.services_csv = %s)'
        params.extend([f'{service_filter},%', f'%,{service_filter},%', f'%,{service_filter}', service_filter])
    
    if submitter_filter and current_user.role in ['admin', 'manager']:
        base_query += ' AND l.submitted_by_user_id = %s'
        params.append(submitter_filter)
    
    if date_from:
        base_query += ' AND DATE(l.created_at) >= %s'
        params.append(date_from)
    
    if date_to:
        base_query += ' AND DATE(l.created_at) <= %s'
        params.append(date_to)
    
    base_query += ' ORDER BY l.created_at DESC'
    
    # Pagination
    page = request.args.get('page', 1, type=int)
    per_page = 50
    offset = (page - 1) * per_page
    
    # Get total count for pagination
    count_query = base_query.replace(' ORDER BY l.created_at DESC', '').replace('SELECT l.*, u.name as submitter_name, la.deadline_at, CASE WHEN la.deadline_at < CURRENT_TIMESTAMP THEN 1 ELSE 0 END as is_overdue', 'SELECT COUNT(*) as total')
    cursor.execute(count_query, params)
    total_leads = cursor.fetchone()['total']
    total_pages = (total_leads + per_page - 1) // per_page
    
    # Get status counts for stats
    status_count_query = base_query.replace(' ORDER BY l.created_at DESC', '').replace('SELECT l.*, u.name as submitter_name, la.deadline_at, CASE WHEN la.deadline_at < CURRENT_TIMESTAMP THEN 1 ELSE 0 END as is_overdue', 'SELECT l.status, COUNT(*) as count')
    status_count_query += ' GROUP BY l.status'
    cursor.execute(status_count_query, params)
    status_counts_raw = cursor.fetchall()
    status_counts = {row['status']: row['count'] for row in status_counts_raw}
    
    # Add LIMIT and OFFSET
    base_query += ' LIMIT %s OFFSET %s'
    params.extend([per_page, offset])
    
    cursor.execute(base_query, params)
    leads_raw = cursor.fetchall()
    
    # Format leads for template
    leads_with_submitters = []
    for lead in leads_raw:
        leads_with_submitters.append({
            'lead': lead,
            'submitter_name': lead['submitter_name'] or 'Unknown',
            'deadline': lead['deadline_at'],
            'is_overdue': bool(lead['is_overdue'])
        })
    
    cursor.execute('SELECT * FROM services ORDER BY name')
    services = cursor.fetchall()
    
    # Only admin and manager can filter by submitter
    submitters = []
    if current_user.role in ['admin', 'manager']:
        cursor.execute('SELECT id, name FROM users WHERE role = %s ORDER BY name', ('marketer',))
        submitters = cursor.fetchall()
    
    cursor.execute('''
        SELECT * FROM lead_targets 
        WHERE assignee_id = %s 
          AND period_start <= DATE('now') 
          AND period_end >= DATE('now')
        ORDER BY period_end ASC
        LIMIT 3
    ''', (current_user.id,))
    active_targets_raw = cursor.fetchall()
    
    active_targets = []
    for target in active_targets_raw:
        progress = compute_target_progress(target, cursor)
        from datetime import datetime as dt
        try:
            period_end = dt.strptime(target['period_end'], '%Y-%m-%d').date()
            days_left = (period_end - date.today()).days
        except:
            days_left = None
        
        active_targets.append({
            'target': target,
            'progress': progress,
            'days_left': max(0, days_left) if days_left is not None else None
        })
    
    conn.close()
    
    return render_template('dashboard.html', 
                         leads=leads_with_submitters, 
                         services=services,
                         submitters=submitters,
                         unread_count=unread_count,
                         active_targets=active_targets,
                         date_today=date.today().isoformat(),
                         filters={
                             'status': status_filter,
                             'service': service_filter,
                             'submitter': submitter_filter,
                             'date_from': date_from,
                             'date_to': date_to,
                             'date_range': date_range
                         },
                         pagination={
                             'page': page,
                             'per_page': per_page,
                             'total_leads': total_leads,
                             'total_pages': total_pages
                         },
                         status_counts=status_counts)

@app.route('/pipeline')
@login_required
@role_required('admin', 'manager', 'bd_sales')
def pipeline():
    """Sales Pipeline Kanban View - BD Sales sees assigned leads, Admin/EM Team Leader see all"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Get all pipeline stages ordered by position
    cursor.execute('SELECT * FROM pipeline_stages ORDER BY position ASC')
    stages = cursor.fetchall()
    
    # Fetch leads with BD assignments based on role
    if current_user.role == 'bd_sales':
        # BD Sales sees only leads assigned to them
        cursor.execute('''
            SELECT l.*, u.name as submitter_name, bd.name as bd_name
            FROM leads l
            LEFT JOIN users u ON l.submitted_by_user_id = u.id
            LEFT JOIN users bd ON l.assigned_bd_id = bd.id
            WHERE l.assigned_bd_id = %s AND l.current_stage_id IS NOT NULL
            ORDER BY l.created_at DESC
        ''', (current_user.id,))
    else:
        # Admin and EM Team Leader see all leads with BD assignments
        cursor.execute('''
            SELECT l.*, u.name as submitter_name, bd.name as bd_name
            FROM leads l
            LEFT JOIN users u ON l.submitted_by_user_id = u.id
            LEFT JOIN users bd ON l.assigned_bd_id = bd.id
            WHERE l.assigned_bd_id IS NOT NULL AND l.current_stage_id IS NOT NULL
            ORDER BY l.created_at DESC
        ''')
    
    all_leads = cursor.fetchall()
    conn.close()
    
    # Group leads by stage
    stages_with_leads = []
    for stage in stages:
        stage_leads = [lead for lead in all_leads if lead['current_stage_id'] == stage['id']]
        stages_with_leads.append({
            'stage': stage,
            'leads': stage_leads,
            'count': len(stage_leads)
        })
    
    return render_template('pipeline.html', stages=stages_with_leads)

@app.route('/pipeline/stages')
@login_required
@role_required('admin')
def manage_stages():
    """Pipeline Stage Management - Admin only"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM pipeline_stages ORDER BY position ASC')
    stages = cursor.fetchall()
    
    # Count leads in each stage
    stages_with_counts = []
    for stage in stages:
        cursor.execute('SELECT COUNT(*) as count FROM leads WHERE current_stage_id = %s', (stage['id'],))
        count_row = cursor.fetchone()
        stages_with_counts.append({
            'stage': stage,
            'lead_count': count_row['count'] if count_row else 0
        })
    
    conn.close()
    
    return render_template('stages.html', stages=stages_with_counts)

@app.route('/pipeline/stages/new', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def new_stage():
    """Create new pipeline stage"""
    form = PipelineStageForm()
    
    if form.validate_on_submit():
        conn = get_db()
        cursor = conn.cursor()
        
        # Get the next position number
        cursor.execute('SELECT MAX(position) as max_pos FROM pipeline_stages')
        max_pos_row = cursor.fetchone()
        next_position = (max_pos_row['max_pos'] or 0) + 1
        
        # Insert new stage
        cursor.execute('''
            INSERT INTO pipeline_stages (name, color, description, position)
            VALUES (%s, %s, %s, %s)
        ''', (form.name.data, form.color.data or '#6c757d', form.description.data, next_position))
        
        conn.commit()
        conn.close()
        
        flash(f'Pipeline stage "{form.name.data}" created successfully!', 'success')
        return redirect(url_for('manage_stages'))
    
    return render_template('stage_form.html', form=form, title='New Pipeline Stage')

@app.route('/pipeline/stages/<int:stage_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def edit_stage(stage_id):
    """Edit existing pipeline stage"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM pipeline_stages WHERE id = %s', (stage_id,))
    stage = cursor.fetchone()
    
    if not stage:
        conn.close()
        flash('Stage not found.', 'danger')
        return redirect(url_for('manage_stages'))
    
    form = PipelineStageForm()
    
    if form.validate_on_submit():
        cursor.execute('''
            UPDATE pipeline_stages 
            SET name = %s, color = %s, description = %s
            WHERE id = %s
        ''', (form.name.data, form.color.data or '#6c757d', form.description.data, stage_id))
        
        conn.commit()
        conn.close()
        
        flash(f'Pipeline stage "{form.name.data}" updated successfully!', 'success')
        return redirect(url_for('manage_stages'))
    
    # Pre-fill form
    if request.method == 'GET':
        form.name.data = stage['name']
        form.color.data = stage['color']
        form.description.data = stage['description']
    
    conn.close()
    return render_template('stage_form.html', form=form, title='Edit Pipeline Stage', stage=stage)

@app.route('/pipeline/stages/<int:stage_id>/delete', methods=['POST'])
@login_required
@role_required('admin')
def delete_stage(stage_id):
    """Delete pipeline stage"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Check if stage has any leads
    cursor.execute('SELECT COUNT(*) as count FROM leads WHERE current_stage_id = %s', (stage_id,))
    count_row = cursor.fetchone()
    
    if count_row and count_row['count'] > 0:
        conn.close()
        flash(f'Cannot delete stage with {count_row["count"]} lead(s). Move leads to another stage first.', 'danger')
        return redirect(url_for('manage_stages'))
    
    # Delete stage
    cursor.execute('DELETE FROM pipeline_stages WHERE id = %s', (stage_id,))
    conn.commit()
    conn.close()
    
    flash('Pipeline stage deleted successfully!', 'success')
    return redirect(url_for('manage_stages'))

@app.route('/api/pipeline/stages/reorder', methods=['POST'])
@login_required
@role_required('admin')
def reorder_stages():
    """Reorder pipeline stages via drag-and-drop"""
    from flask import jsonify
    
    data = request.get_json()
    if data is None:
        return jsonify({'success': False, 'message': 'Invalid or missing JSON payload'}), 400
    
    stage_ids = data.get('stage_ids')
    if not stage_ids or not isinstance(stage_ids, list):
        return jsonify({'success': False, 'message': 'stage_ids array is required'}), 400
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Update positions
    for index, stage_id in enumerate(stage_ids):
        cursor.execute('UPDATE pipeline_stages SET position = %s WHERE id = %s', (index + 1, stage_id))
    
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'message': 'Stages reordered successfully'}), 200

@app.route('/lead/new', methods=['GET', 'POST'])
@login_required
@role_required('marketer', 'manager')
def new_lead():
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM services ORDER BY name')
    services = cursor.fetchall()
    
    form = LeadForm()
    form.services.choices = [(s['id'], s['name']) for s in services]
    
    if form.validate_on_submit():
        attachment_path = None
        if form.attachment.data:
            file = form.attachment.data
            filename = secure_filename(file.filename)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{timestamp}_{filename}"
            file_data = file.read()
            upload_result = upload_file(file_data, filename, 'uploads')
            # upload_result may be dict (cloud) or string (local)
            if isinstance(upload_result, dict):
                attachment_path = upload_result.get('url')
            else:
                attachment_path = upload_result if upload_result else filename
        assigned_manager_id = None
        assignment_method = None
        
        if current_user.role == 'marketer':
            # Inline round-robin assignment logic to avoid nested transactions
            cursor.execute('SELECT id FROM users WHERE role = %s ORDER BY id', ('manager',))
            managers = cursor.fetchall()
            
            if managers:
                manager_ids = [m['id'] for m in managers]
                
                cursor.execute('SELECT last_assigned_manager_id, last_assigned_bd_id FROM assignment_settings WHERE id = 1')
                settings = cursor.fetchone()
                
                if settings:
                    last_assigned_id = settings['last_assigned_manager_id']
                    current_bd_id = settings['last_assigned_bd_id']
                else:
                    last_assigned_id = None
                    current_bd_id = None
                
                if last_assigned_id and last_assigned_id in manager_ids:
                    current_index = manager_ids.index(last_assigned_id)
                    next_index = (current_index + 1) % len(manager_ids)
                    assigned_manager_id = manager_ids[next_index]
                else:
                    assigned_manager_id = manager_ids[0]
                
                # Update assignment settings in same transaction
                if settings:
                    cursor.execute('''
                        UPDATE assignment_settings 
                        SET last_assigned_manager_id = %s, updated_at = CURRENT_TIMESTAMP 
                        WHERE id = 1
                    ''', (assigned_manager_id,))
                else:
                    cursor.execute('''
                        INSERT INTO assignment_settings (id, last_assigned_manager_id, last_assigned_bd_id, updated_at)
                        VALUES (1, %s, %s, CURRENT_TIMESTAMP)
                    ''', (assigned_manager_id, current_bd_id))
                
                assignment_method = 'round-robin'
                
        elif current_user.role == 'manager':
            cursor.execute('''
                SELECT id FROM users 
                WHERE role = 'manager' AND id != %s 
                ORDER BY RANDOM() 
                LIMIT 1
            ''', (current_user.id,))
            other_manager = cursor.fetchone()
            if other_manager:
                assigned_manager_id = other_manager['id']
            assignment_method = 'random'
        
        services_csv = ','.join([str(s) for s in form.services.data])
        
        cursor.execute('''
            INSERT INTO leads (submitted_by_user_id, full_name, email, phone, company, domain, 
                             industry, services_csv, country, state, city, attachment_path, status, 
                             current_manager_id, assigned_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'Pending', %s, %s)
            RETURNING id
        ''', (current_user.id, form.full_name.data, form.email.data, form.phone.data,
              form.company.data, form.domain.data, form.industry.data, services_csv, form.country.data,
              form.state.data, form.city.data, attachment_path, assigned_manager_id,
              datetime.now() if assigned_manager_id else None))
        
        lead_id = cursor.fetchone()['id']
        
        # Save social profiles if provided
        social_profiles = []
        if form.linkedin_url.data:
            social_profiles.append(('linkedin', form.linkedin_url.data))
        if form.twitter_url.data:
            social_profiles.append(('twitter', form.twitter_url.data))
        if form.facebook_url.data:
            social_profiles.append(('facebook', form.facebook_url.data))
        if form.website_url.data:
            social_profiles.append(('website', form.website_url.data))
        
        for platform, url in social_profiles:
            cursor.execute('''
                INSERT INTO lead_social_profiles (lead_id, platform, url, added_by_id)
                VALUES (%s, %s, %s, %s)
            ''', (lead_id, platform, url, current_user.id))
        
        cursor.execute('''
            INSERT INTO lead_notes (lead_id, author_user_id, note_type, message)
            VALUES (%s, %s, 'system', %s)
        ''', (lead_id, current_user.id, f'Lead created by {current_user.name}'))
        
        if assigned_manager_id:
            cursor.execute('''
                SELECT name FROM users WHERE id = %s
            ''', (assigned_manager_id,))
            assigned_manager = cursor.fetchone()
            
            assignment_note = f'Auto-assigned to {assigned_manager["name"]}'
            if assignment_method == 'round-robin':
                assignment_note += ' (round-robin distribution)'
            
            cursor.execute('''
                INSERT INTO lead_notes (lead_id, author_user_id, note_type, message)
                VALUES (%s, %s, 'system', %s)
            ''', (lead_id, current_user.id, assignment_note))
            
            cursor.execute('''
                INSERT INTO lead_assignments (lead_id, manager_id, deadline_at, is_initial_assignment)
                VALUES (%s, %s, NOW() + INTERVAL '15 hours', 1)
            ''', (lead_id, assigned_manager_id))
            
            notification_message = f'New lead from {current_user.name} has been assigned to you: {form.company.data}'
            cursor.execute('''
                INSERT INTO notifications (user_id, lead_id, message, notification_type)
                VALUES (%s, %s, %s, %s)
            ''', (assigned_manager_id, lead_id, notification_message, 'assignment'))
            
            send_realtime_notification(assigned_manager_id, notification_message, 'assignment', play_sound=True)
        
        conn.commit()
        conn.close()
        
        flash('Lead submitted successfully!', 'success')
        return redirect(url_for('dashboard'))
    
    conn.close()
    return render_template('lead_form.html', form=form, title='Submit New Lead')

@app.route('/lead/<int:lead_id>')
@login_required
def view_lead(lead_id):
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM leads WHERE id = %s', (lead_id,))
    lead = cursor.fetchone()
    
    if not lead:
        flash('Lead not found.', 'danger')
        conn.close()
        return redirect(url_for('dashboard'))
    
    if current_user.role == 'marketer' and lead['submitted_by_user_id'] != current_user.id:
        flash('You do not have permission to view this lead.', 'danger')
        conn.close()
        return redirect(url_for('dashboard'))
    
    cursor.execute('SELECT name FROM users WHERE id = %s', (lead['submitted_by_user_id'],))
    submitter = cursor.fetchone()
    
    # Parse services - handle both IDs and names in CSV
    services = []
    if lead['services_csv']:
        service_parts = [s.strip() for s in lead['services_csv'].split(',')]
        # Check if first part is numeric (IDs) or text (names)
        if service_parts and service_parts[0].isdigit():
            # CSV contains IDs
            service_ids = [int(s) for s in service_parts]
            placeholders = ','.join(['%s'] * len(service_ids))
            cursor.execute(f'SELECT name FROM services WHERE id IN ({placeholders})', service_ids)
            services = [row['name'] for row in cursor.fetchall()]
        else:
            # CSV contains names directly
            services = service_parts
    
    cursor.execute('''
        SELECT ln.*, u.name as author_name 
        FROM lead_notes ln
        JOIN users u ON ln.author_user_id = u.id
        WHERE ln.lead_id = %s
        ORDER BY ln.created_at ASC
    ''', (lead_id,))
    notes = cursor.fetchall()
    
    deadline = None
    is_overdue = False
    if lead['status'] in ['Pending', 'Resubmitted']:
        cursor.execute('''
            SELECT deadline_at FROM lead_assignments 
            WHERE lead_id = %s AND status = 'pending'
            ORDER BY assigned_at DESC LIMIT 1
        ''', (lead_id,))
        deadline_row = cursor.fetchone()
        if deadline_row and deadline_row['deadline_at']:
            deadline = deadline_row['deadline_at']
            try:
                deadline_dt = datetime.strptime(deadline, '%Y-%m-%d %H:%M:%S')
                is_overdue = deadline_dt < datetime.now()
            except:
                pass
    
    bd_sales_info = None
    current_stage = None
    bd_assignment_history = []
    
    cursor.execute('SELECT * FROM lead_social_profiles WHERE lead_id = %s', (lead_id,))
    social_profiles = cursor.fetchall()
    
    # Build unified timeline from all sources
    timeline = build_unified_timeline(lead_id, lead, cursor)
    
    if lead['assigned_bd_id']:
        cursor.execute('SELECT id, name, email FROM users WHERE id = %s', (lead['assigned_bd_id'],))
        bd_sales_info = cursor.fetchone()
        
        cursor.execute('''
            SELECT * FROM bd_assignment_history 
            WHERE lead_id = %s 
            ORDER BY reassigned_at DESC
        ''', (lead_id,))
        bd_assignment_history = cursor.fetchall()
        
        if lead['current_stage_id']:
            cursor.execute('SELECT * FROM pipeline_stages WHERE id = %s', (lead['current_stage_id'],))
            current_stage = cursor.fetchone()
    
    # Get all pipeline stages for the stage editor dropdown
    cursor.execute('SELECT id, name, position FROM pipeline_stages ORDER BY position')
    all_stages = cursor.fetchall()
    
    conn.close()
    
    # Create forms for modals
    social_profile_form = SocialProfileForm()
    deal_amount_form = DealAmountForm()
    activity_form = ActivityForm()
    if lead['deal_amount']:
        deal_amount_form.deal_amount.data = lead['deal_amount']
    
    return render_template('lead_detail.html', 
                         lead=lead, 
                         submitter_name=submitter['name'] if submitter else 'Unknown',
                         services=services,
                         notes=notes,
                         deadline=deadline,
                         is_overdue=is_overdue,
                         bd_sales_info=bd_sales_info,
                         current_stage=current_stage,
                         bd_assignment_history=bd_assignment_history,
                         social_profiles=social_profiles,
                         timeline=timeline,
                         social_profile_form=social_profile_form,
                         deal_amount_form=deal_amount_form,
                         activity_form=activity_form,
                         all_stages=all_stages)

@app.route('/lead/<int:lead_id>/social-profile/add', methods=['POST'])
@login_required
def add_social_profile(lead_id):
    """Add social profile to a lead - All users can add"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM leads WHERE id = %s', (lead_id,))
    lead = cursor.fetchone()
    
    if not lead:
        flash('Lead not found.', 'danger')
        conn.close()
        return redirect(url_for('dashboard'))
    
    form = SocialProfileForm()
    
    if form.validate_on_submit():
        cursor.execute('''
            INSERT INTO lead_social_profiles (lead_id, platform, url, added_by_id)
            VALUES (%s, %s, %s, %s)
        ''', (lead_id, form.platform.data, form.url.data, current_user.id))
        
        conn.commit()
        
        # Emit Socket.IO event
        socketio.emit('lead_updated', {
            'lead_id': lead_id,
            'update_type': 'social_profile_added',
            'updated_by': current_user.name
        })
        
        conn.close()
        flash('Social profile added successfully!', 'success')
    else:
        conn.close()
        for field, errors in form.errors.items():
            for error in errors:
                flash(f'{field}: {error}', 'danger')
    
    return redirect(url_for('view_lead', lead_id=lead_id))

@app.route('/lead/<int:lead_id>/social-profile/<int:profile_id>/delete', methods=['POST'])
@login_required
def delete_social_profile(lead_id, profile_id):
    """Delete social profile - All users can delete"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM leads WHERE id = %s', (lead_id,))
    lead = cursor.fetchone()
    
    if not lead:
        flash('Lead not found.', 'danger')
        conn.close()
        return redirect(url_for('dashboard'))
    
    cursor.execute('DELETE FROM lead_social_profiles WHERE id = %s AND lead_id = %s', (profile_id, lead_id))
    conn.commit()
    
    # Emit Socket.IO event
    socketio.emit('lead_updated', {
        'lead_id': lead_id,
        'update_type': 'social_profile_deleted',
        'updated_by': current_user.name
    })
    
    conn.close()
    flash('Social profile deleted successfully!', 'success')
    return redirect(url_for('view_lead', lead_id=lead_id))

@app.route('/lead/<int:lead_id>/deal-amount', methods=['GET', 'POST'])
@login_required
def update_deal_amount(lead_id):
    """Update deal amount - BD Sales (assigned) or Admin/Manager"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM leads WHERE id = %s', (lead_id,))
    lead = cursor.fetchone()
    
    if not lead:
        flash('Lead not found.', 'danger')
        conn.close()
        return redirect(url_for('dashboard'))
    
    # Permission check
    if current_user.role == 'bd_sales' and lead['assigned_bd_id'] != current_user.id:
        flash('You can only update deal amount for your assigned leads.', 'danger')
        conn.close()
        return redirect(url_for('view_lead', lead_id=lead_id))
    
    if current_user.role not in ['admin', 'manager', 'bd_sales']:
        flash('You do not have permission to update deal amount.', 'danger')
        conn.close()
        return redirect(url_for('view_lead', lead_id=lead_id))
    
    form = DealAmountForm()
    
    if form.validate_on_submit():
        old_amount = lead['deal_amount']
        deal_amount = float(form.deal_amount.data) if form.deal_amount.data else None
        
        cursor.execute('''
            UPDATE leads SET deal_amount = %s
            WHERE id = %s
        ''', (deal_amount, lead_id))
        
        conn.commit()
        
        # Log the deal amount change in activity timeline
        if old_amount != deal_amount:
            old_display = f'${old_amount:,.2f}' if old_amount else '$0.00'
            new_display = f'${deal_amount:,.2f}' if deal_amount else '$0.00'
            activity_description = f'Deal amount updated from {old_display} to {new_display}'
            
            cursor.execute('''
                INSERT INTO lead_activities (lead_id, activity_type, title, description, actor_id, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
            ''', (lead_id, 'note', 'Deal Amount Updated', activity_description, current_user.id, datetime.now()))
            conn.commit()
        
        # Emit Socket.IO event
        socketio.emit('lead_updated', {
            'lead_id': lead_id,
            'update_type': 'deal_amount_updated',
            'new_amount': float(deal_amount) if deal_amount else 0,
            'updated_by': current_user.name
        })
        
        conn.close()
        flash(f'Deal amount updated to ${deal_amount:,.2f}' if deal_amount else 'Deal amount cleared', 'success')
        return redirect(url_for('view_lead', lead_id=lead_id))
    
    # GET request or validation failed - show form
    if lead['deal_amount']:
        form.deal_amount.data = lead['deal_amount']
    
    conn.close()
    return render_template('deal_amount_form.html', lead=lead, form=form)

@app.route('/lead/<int:lead_id>/activity/add', methods=['POST'])
@login_required
def add_activity(lead_id):
    """Add activity - BD Sales (assigned) or Admin/Manager"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM leads WHERE id = %s', (lead_id,))
    lead = cursor.fetchone()
    
    if not lead:
        flash('Lead not found.', 'danger')
        conn.close()
        return redirect(url_for('dashboard'))
    
    # Permission check
    if current_user.role == 'bd_sales' and lead['assigned_bd_id'] != current_user.id:
        flash('You can only add activities for your assigned leads.', 'danger')
        conn.close()
        return redirect(url_for('view_lead', lead_id=lead_id))
    
    if current_user.role not in ['admin', 'manager', 'bd_sales']:
        flash('You do not have permission to add activities.', 'danger')
        conn.close()
        return redirect(url_for('view_lead', lead_id=lead_id))
    
    form = ActivityForm()
    
    if form.validate_on_submit():
        activity_type = form.activity_type.data
        title = form.title.data if form.title.data else None
        description = form.description.data
        
        # Convert IST datetime to UTC for storage
        due_at_utc = convert_ist_to_utc(form.due_at.data) if form.due_at.data else None
        reminder_at_utc = convert_ist_to_utc(form.reminder_at.data) if form.reminder_at.data else None
        
        cursor.execute('''
            INSERT INTO lead_activities 
            (lead_id, actor_id, activity_type, title, description, due_at, reminder_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        ''', (lead_id, current_user.id, activity_type, title, description, due_at_utc, reminder_at_utc))
        
        activity_id = cursor.fetchone()['id']
        conn.commit()
        
        # Emit Socket.IO event
        socketio.emit('lead_updated', {
            'lead_id': lead_id,
            'update_type': 'activity_added',
            'activity_type': activity_type,
            'updated_by': current_user.name
        })
        
        # If there's a reminder, create a notification
        if reminder_at_utc:
            socketio.emit('notification', {
                'lead_id': lead_id,
                'activity_id': activity_id,
                'type': 'reminder',
                'message': f'Reminder set for {activity_type}',
                'user_id': current_user.id
            }, room=f'user_{current_user.id}')
        
        conn.close()
        flash(f'{activity_type.replace("_", " ").title()} added successfully!', 'success')
    else:
        conn.close()
        for field, errors in form.errors.items():
            for error in errors:
                flash(f'{field}: {error}', 'danger')
    
    return redirect(url_for('view_lead', lead_id=lead_id))

@app.route('/lead/<int:lead_id>/activity/<int:activity_id>/complete', methods=['POST'])
@login_required
def complete_activity(lead_id, activity_id):
    """Mark task as complete - BD Sales (assigned) or Admin/Manager (Legacy route - redirects to toggle)"""
    return toggle_task_complete(lead_id, activity_id)

@app.route('/lead/<int:lead_id>/activity/<int:activity_id>/toggle_complete', methods=['POST'])
@login_required
def toggle_task_complete(lead_id, activity_id):
    """Toggle task completion status - BD Sales (assigned) or Admin/Manager"""
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute('SELECT * FROM leads WHERE id = %s', (lead_id,))
        lead = cursor.fetchone()
        
        if not lead:
            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'message': 'Lead not found.'}), 404
            flash('Lead not found.', 'danger')
            conn.close()
            return redirect(url_for('dashboard'))
        
        # Permission check
        if current_user.role == 'bd_sales' and lead['assigned_bd_id'] != current_user.id:
            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'message': 'Permission denied.'}), 403
            flash('You can only complete activities for your assigned leads.', 'danger')
            conn.close()
            return redirect(url_for('view_lead', lead_id=lead_id))
        
        if current_user.role not in ['admin', 'manager', 'bd_sales']:
            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'message': 'Permission denied.'}), 403
            flash('You do not have permission to complete activities.', 'danger')
            conn.close()
            return redirect(url_for('view_lead', lead_id=lead_id))
        
        # Check current completion status
        cursor.execute('SELECT completed_at FROM lead_activities WHERE id = %s AND lead_id = %s', (activity_id, lead_id))
        activity = cursor.fetchone()
        
        if not activity:
            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'message': 'Activity not found.'}), 404
            flash('Activity not found.', 'danger')
            conn.close()
            return redirect(url_for('view_lead', lead_id=lead_id))
        
        # Toggle completion status
        if activity['completed_at']:
            # Mark as incomplete
            cursor.execute('''
                UPDATE lead_activities 
                SET completed_at = NULL
                WHERE id = %s AND lead_id = %s
            ''', (activity_id, lead_id))
            update_type = 'activity_reopened'
            message = 'Task marked as incomplete!'
            is_completed = False
            completed_at = None
        else:
            # Mark as complete
            cursor.execute('''
                UPDATE lead_activities 
                SET completed_at = CURRENT_TIMESTAMP
                WHERE id = %s AND lead_id = %s
            ''', (activity_id, lead_id))
            update_type = 'activity_completed'
            message = 'Task marked as complete!'
            is_completed = True
            
            # Get the updated completed_at timestamp
            cursor.execute('SELECT completed_at FROM lead_activities WHERE id = %s', (activity_id,))
            updated = cursor.fetchone()
            completed_at = updated['completed_at'] if updated else None
        
        safe_commit(conn, context="toggle_task_complete")
        
        # Emit Socket.IO event for real-time updates
        socketio.emit('lead_updated', {
            'lead_id': lead_id,
            'update_type': update_type,
            'activity_id': activity_id,
            'is_completed': is_completed,
            'updated_by': current_user.name
        })
        
        # Return JSON for AJAX requests
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'success': True,
                'message': message,
                'is_completed': is_completed,
                'completed_at': completed_at,
                'activity_id': activity_id
            })
        
        # Traditional form submission - flash message and redirect
        flash(message, 'success')
        return redirect(url_for('view_lead', lead_id=lead_id))
        
    except Exception as e:
        print(f"Error toggling task completion: {str(e)}")
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'An error occurred.'}), 500
        flash('An error occurred while updating the task.', 'danger')
        return redirect(url_for('view_lead', lead_id=lead_id))
    finally:
        conn.close()

@app.route('/lead/<int:lead_id>/activity/<int:activity_id>/delete', methods=['POST'])
@login_required
def delete_activity(lead_id, activity_id):
    """Delete activity - BD Sales (assigned) or Admin/Manager"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM leads WHERE id = %s', (lead_id,))
    lead = cursor.fetchone()
    
    if not lead:
        flash('Lead not found.', 'danger')
        conn.close()
        return redirect(url_for('dashboard'))
    
    # Permission check
    if current_user.role == 'bd_sales' and lead['assigned_bd_id'] != current_user.id:
        flash('You can only delete activities for your assigned leads.', 'danger')
        conn.close()
        return redirect(url_for('view_lead', lead_id=lead_id))
    
    if current_user.role not in ['admin', 'manager', 'bd_sales']:
        flash('You do not have permission to delete activities.', 'danger')
        conn.close()
        return redirect(url_for('view_lead', lead_id=lead_id))
    
    cursor.execute('DELETE FROM lead_activities WHERE id = %s AND lead_id = %s', (activity_id, lead_id))
    conn.commit()
    
    # Emit Socket.IO event
    socketio.emit('lead_updated', {
        'lead_id': lead_id,
        'update_type': 'activity_deleted',
        'activity_id': activity_id,
        'updated_by': current_user.name
    })
    
    conn.close()
    flash('Activity deleted successfully!', 'success')
    return redirect(url_for('view_lead', lead_id=lead_id))

@app.route('/lead/<int:lead_id>/accept', methods=['POST'])
@login_required
@role_required('admin', 'manager')
def accept_lead(lead_id):
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM leads WHERE id = %s', (lead_id,))
    lead = cursor.fetchone()
    
    if not lead:
        flash('Lead not found.', 'danger')
        conn.close()
        return redirect(url_for('dashboard'))
    
    cursor.execute('UPDATE leads SET status = %s, accepted_at = CURRENT_TIMESTAMP WHERE id = %s', ('Accepted', lead_id))
    
    cursor.execute('''
        UPDATE lead_assignments 
        SET acted_at = CURRENT_TIMESTAMP, status = 'acted'
        WHERE lead_id = %s AND manager_id = %s AND status = 'pending'
    ''', (lead_id, current_user.id))
    
    cursor.execute('''
        INSERT INTO lead_notes (lead_id, author_user_id, note_type, message)
        VALUES (%s, %s, 'system', %s)
    ''', (lead_id, current_user.id, f'Lead accepted by {current_user.name}'))
    
    notification_message = f'Your lead for {lead["company"]} has been accepted!'
    cursor.execute('''
        INSERT INTO notifications (user_id, lead_id, message)
        VALUES (%s, %s, %s)
    ''', (lead['submitted_by_user_id'], lead_id, notification_message))
    
    send_realtime_notification(lead['submitted_by_user_id'], notification_message, 'success', play_sound=True)
    
    safe_commit(conn)
    conn.close()
    
    flash('Lead accepted successfully! Please assign to BD Sales.', 'success')
    return redirect(url_for('assign_bd_sales', lead_id=lead_id))

@app.route('/lead/<int:lead_id>/assign-bd', methods=['GET', 'POST'])
@login_required
def assign_bd_sales(lead_id):
    """Assign or reassign accepted lead to BD Sales - Admin, Manager, or BD Sales can do this"""
    # Allow Admin, Manager, and BD Sales to reassign leads
    if current_user.role not in ['admin', 'manager', 'bd_sales']:
        flash('You do not have permission to assign leads.', 'danger')
        return redirect(url_for('view_lead', lead_id=lead_id))
    
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM leads WHERE id = %s', (lead_id,))
    lead = cursor.fetchone()
    
    if not lead:
        flash('Lead not found.', 'danger')
        conn.close()
        return redirect(url_for('dashboard'))
    
    if lead['status'] != 'Accepted':
        flash('Only accepted leads can be assigned to BD Sales.', 'warning')
        conn.close()
        return redirect(url_for('view_lead', lead_id=lead_id))
    
    # Capture current assignment for reassignment tracking
    current_bd_id = lead['assigned_bd_id']
    is_reassignment = current_bd_id is not None
    
    form = BDAssignmentForm()
    
    cursor.execute('SELECT id, name, email FROM users WHERE role = %s ORDER BY name', (ROLE_BD_SALES,))
    bd_sales_users = cursor.fetchall()
    
    if not bd_sales_users:
        flash('No BD Sales representatives available. Please create BD Sales users first.', 'danger')
        conn.close()
        return redirect(url_for('view_lead', lead_id=lead_id))
    
    form.bd_sales_id.choices = [(u['id'], f"{u['name']} ({u['email']})") for u in bd_sales_users]
    
    suggested_bd_id = peek_next_bd_sales_for_assignment()
    if suggested_bd_id and request.method == 'GET':
        form.bd_sales_id.data = suggested_bd_id
    
    if form.validate_on_submit():
        bd_sales_id = form.bd_sales_id.data
        assignment_note = form.note.data
        
        cursor.execute('SELECT name FROM users WHERE id = %s', (bd_sales_id,))
        bd_user = cursor.fetchone()
        
        # Get the first pipeline stage ID
        cursor.execute('SELECT id FROM pipeline_stages ORDER BY position LIMIT 1')
        first_stage = cursor.fetchone()
        
        if not first_stage:
            conn.close()
            flash('Cannot assign lead: No pipeline stages configured. Please contact an administrator to set up pipeline stages.', 'danger')
            return redirect(url_for('view_lead', lead_id=lead_id))
        
        first_stage_id = first_stage['id']
        
        cursor.execute('''
            UPDATE leads 
            SET assigned_bd_id = %s, assigned_to_bd_at = CURRENT_TIMESTAMP, current_stage_id = %s
            WHERE id = %s
        ''', (bd_sales_id, first_stage_id, lead_id))
        
        # Log assignment/reassignment to history with from/to BDs
        cursor.execute('''
            INSERT INTO bd_assignment_history (lead_id, from_bd_id, to_bd_id, assigned_by_id, reassigned_at, reason)
            VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP, %s)
        ''', (lead_id, current_bd_id, bd_sales_id, current_user.id, assignment_note or (f'{"Reassigned" if is_reassignment else "Assigned"} by {current_user.name}')))
        
        # Log stage transition only if stage changed
        if first_stage_id and lead['current_stage_id'] != first_stage_id:
            cursor.execute('''
                INSERT INTO lead_stage_history (lead_id, from_stage_id, to_stage_id, changed_by_id, changed_at)
                VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
            ''', (lead_id, lead['current_stage_id'], first_stage_id, current_user.id))
        
        # Only update round-robin pointer if BD changed (within same transaction to avoid locks)
        if current_bd_id != bd_sales_id:
            cursor.execute('SELECT id FROM assignment_settings WHERE id = 1')
            if not cursor.fetchone():
                cursor.execute('''
                    INSERT INTO assignment_settings (id, last_assigned_manager_id, last_assigned_bd_id, updated_at)
                    VALUES (1, NULL, %s, CURRENT_TIMESTAMP)
                ''', (bd_sales_id,))
            else:
                cursor.execute('''
                    UPDATE assignment_settings 
                    SET last_assigned_bd_id = %s, updated_at = CURRENT_TIMESTAMP 
                    WHERE id = 1
                ''', (bd_sales_id,))
        
        # Create notification and activity
        action_text = 'Reassigned' if is_reassignment else 'Assigned'
        cursor.execute('''
            INSERT INTO lead_activities (lead_id, actor_id, activity_type, title, description, created_at)
            VALUES (%s, %s, 'assignment', %s, %s, CURRENT_TIMESTAMP)
        ''', (lead_id, current_user.id, f'{action_text} to BD Sales', 
              f'{current_user.name} {action_text.lower()} this lead to {bd_user["name"]}' + (f'\n\nNote: {assignment_note}' if assignment_note else '')))
        
        notification_message = f'{"New" if not is_reassignment else "Reassigned"} lead assigned to you: {lead["company"]}'
        cursor.execute('''
            INSERT INTO notifications (user_id, lead_id, message)
            VALUES (%s, %s, %s)
        ''', (bd_sales_id, lead_id, notification_message))
        
        send_realtime_notification(bd_sales_id, notification_message, 'info', play_sound=True)
        
        # Commit with retry
        try:
            safe_commit(conn)
        except sqlite3.OperationalError:
            conn.close()
            flash(f'Database is busy. Please try again.', 'warning')
            return redirect(url_for('assign_bd_sales', lead_id=lead_id))
        
        conn.close()
        
        flash(f'Lead {"reassigned" if is_reassignment else "assigned"} to {bd_user["name"]} successfully!', 'success')
        return redirect(url_for('view_lead', lead_id=lead_id))
    
    conn.close()
    return render_template('bd_assignment.html', lead=lead, form=form, bd_sales_users=bd_sales_users)

@app.route('/lead/<int:lead_id>/reject', methods=['GET', 'POST'])
@login_required
@role_required('admin', 'manager')
def reject_lead(lead_id):
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM leads WHERE id = %s', (lead_id,))
    lead = cursor.fetchone()
    
    if not lead:
        flash('Lead not found.', 'danger')
        conn.close()
        return redirect(url_for('dashboard'))
    
    form = RejectForm()
    
    if form.validate_on_submit():
        cursor.execute('UPDATE leads SET status = %s WHERE id = %s', ('Rejected', lead_id))
        
        cursor.execute('''
            INSERT INTO lead_notes (lead_id, author_user_id, note_type, message)
            VALUES (%s, %s, 'rejection', %s)
        ''', (lead_id, current_user.id, form.rejection_comment.data))
        
        notification_message = f'Your lead for {lead["company"]} has been rejected. Please review the comments.'
        cursor.execute('''
            INSERT INTO notifications (user_id, lead_id, message)
            VALUES (%s, %s, %s)
        ''', (lead['submitted_by_user_id'], lead_id, notification_message))
        
        send_realtime_notification(lead['submitted_by_user_id'], notification_message, 'warning', play_sound=True)
        
        safe_commit(conn)
        conn.close()
        
        flash('Lead rejected successfully!', 'success')
        return redirect(url_for('view_lead', lead_id=lead_id))
    
    conn.close()
    return render_template('reject_form.html', form=form, lead_id=lead_id)

@app.route('/lead/<int:lead_id>/revert', methods=['GET', 'POST'])
@login_required
@role_required('admin', 'manager')
def revert_lead(lead_id):
    """Allow managers to re-reject an accepted lead"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM leads WHERE id = %s', (lead_id,))
    lead = cursor.fetchone()
    
    if not lead:
        flash('Lead not found.', 'danger')
        conn.close()
        return redirect(url_for('dashboard'))
    
    if lead['status'] != 'Accepted':
        flash('Only accepted leads can be reverted.', 'danger')
        conn.close()
        return redirect(url_for('view_lead', lead_id=lead_id))
    
    form = RejectForm()
    
    if form.validate_on_submit():
        from datetime import timedelta
        
        cursor.execute('UPDATE leads SET status = %s, accepted_at = NULL, current_manager_id = %s WHERE id = %s', 
                      ('Rejected', current_user.id, lead_id))
        
        cursor.execute('''
            UPDATE lead_assignments 
            SET status = 'reverted'
            WHERE lead_id = %s AND status = 'acted'
        ''', (lead_id,))
        
        deadline = datetime.now() + timedelta(hours=4)
        cursor.execute('''
            INSERT INTO lead_assignments (lead_id, manager_id, assigned_at, deadline_at, status, is_initial_assignment)
            VALUES (%s, %s, CURRENT_TIMESTAMP, %s, 'pending', 0)
        ''', (lead_id, current_user.id, deadline.strftime('%Y-%m-%d %H:%M:%S')))
        
        reversion_message = f"Lead reverted from 'Accepted' to 'Rejected' by {current_user.name}.\nReason: {form.rejection_comment.data}"
        cursor.execute('''
            INSERT INTO lead_notes (lead_id, author_user_id, note_type, message)
            VALUES (%s, %s, 'reversion', %s)
        ''', (lead_id, current_user.id, reversion_message))
        
        notification_message = f'Your accepted lead for {lead["company"]} has been re-rejected by {current_user.name}. Please review the comments.'
        cursor.execute('''
            INSERT INTO notifications (user_id, lead_id, message)
            VALUES (%s, %s, %s)
        ''', (lead['submitted_by_user_id'], lead_id, notification_message))
        
        send_realtime_notification(lead['submitted_by_user_id'], notification_message, 'warning', play_sound=True)
        
        safe_commit(conn)
        conn.close()
        
        flash('Lead has been reverted to rejected status.', 'success')
        return redirect(url_for('view_lead', lead_id=lead_id))
    
    conn.close()
    return render_template('reject_form.html', form=form, lead_id=lead_id, title='Revert Accepted Lead', action='revert')

@app.route('/lead/<int:lead_id>/resubmit', methods=['GET', 'POST'])
@login_required
@role_required('marketer', 'manager')
def resubmit_lead(lead_id):
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM leads WHERE id = %s', (lead_id,))
    lead = cursor.fetchone()
    
    if not lead:
        flash('Lead not found.', 'danger')
        conn.close()
        return redirect(url_for('dashboard'))
    
    if lead['submitted_by_user_id'] != current_user.id:
        flash('You can only resubmit your own leads.', 'danger')
        conn.close()
        return redirect(url_for('dashboard'))
    
    if lead['status'] != 'Rejected':
        flash('Only rejected leads can be resubmitted.', 'danger')
        conn.close()
        return redirect(url_for('view_lead', lead_id=lead_id))
    
    form = ResubmitForm()
    
    if form.validate_on_submit():
        cursor.execute('UPDATE leads SET status = %s WHERE id = %s', ('Resubmitted', lead_id))
        
        cursor.execute('''
            INSERT INTO lead_notes (lead_id, author_user_id, note_type, message)
            VALUES (%s, %s, 'resubmission', %s)
        ''', (lead_id, current_user.id, form.rectification_comment.data))
        
        cursor.execute("SELECT id FROM users WHERE role IN ('admin', 'manager')")
        managers = cursor.fetchall()
        
        notification_message = f'Lead for {lead["company"]} has been resubmitted by {current_user.name} for re-review.'
        for manager in managers:
            cursor.execute('''
                INSERT INTO notifications (user_id, lead_id, message)
                VALUES (%s, %s, %s)
            ''', (manager['id'], lead_id, notification_message))
            
            send_realtime_notification(manager['id'], notification_message, 'info', play_sound=True)
        
        safe_commit(conn)
        conn.close()
        
        flash('Lead resubmitted successfully!', 'success')
        return redirect(url_for('view_lead', lead_id=lead_id))
    
    conn.close()
    return render_template('resubmit_form.html', form=form, lead_id=lead_id)

@app.route('/notifications')
@login_required
def notifications():
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT n.*, l.company, l.full_name
        FROM notifications n
        JOIN leads l ON n.lead_id = l.id
        WHERE n.user_id = %s
        ORDER BY n.created_at DESC
    ''', (current_user.id,))
    
    notifs = cursor.fetchall()
    
    cursor.execute('UPDATE notifications SET is_read = 1 WHERE user_id = %s', (current_user.id,))
    safe_commit(conn)
    conn.close()
    
    return render_template('notifications.html', notifications=notifs)

@app.route('/services')
@login_required
@role_required('admin', 'manager')
def manage_services():
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM services ORDER BY name')
    services = cursor.fetchall()
    conn.close()
    
    form = ServiceForm()
    return render_template('services.html', services=services, form=form)

@app.route('/services/add', methods=['POST'])
@login_required
@role_required('admin', 'manager')
def add_service():
    form = ServiceForm()
    
    if form.validate_on_submit():
        conn = get_db()
        cursor = conn.cursor()
        
        try:
            cursor.execute('INSERT INTO services (name) VALUES (%s)', (form.name.data,))
            conn.commit()
            flash(f'Service "{form.name.data}" added successfully!', 'success')
        except Exception as e:
            flash('Service already exists or error occurred.', 'danger')
        
        conn.close()
    
    return redirect(url_for('manage_services'))

@app.route('/services/<int:service_id>/delete', methods=['POST'])
@login_required
@role_required('admin')
def delete_service(service_id):
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('DELETE FROM services WHERE id = %s', (service_id,))
    conn.commit()
    conn.close()
    
    flash('Service deleted successfully!', 'success')
    return redirect(url_for('manage_services'))

@app.route('/users')
@login_required
@role_required('admin', 'manager')
def manage_users():
    conn = get_db()
    cursor = conn.cursor()
    
    if current_user.role == 'manager':
        cursor.execute('SELECT * FROM users WHERE role = %s ORDER BY created_at DESC', ('marketer',))
        users = cursor.fetchall()
    else:
        cursor.execute('SELECT * FROM users ORDER BY created_at DESC')
        users = cursor.fetchall()
    
    conn.close()
    
    return render_template('users.html', users=users)

@app.route('/users/add', methods=['GET', 'POST'])
@login_required
@role_required('admin', 'manager')
def add_user():
    form = UserForm()
    
    if current_user.role == 'manager':
        form.role.choices = [('marketer', 'Email Marketer')]
        form.role.data = 'marketer'
    
    if form.validate_on_submit():
        if current_user.role == 'manager' and form.role.data != 'marketer':
            flash('Sales Managers can only create Email Marketer accounts.', 'danger')
            return render_template('user_form.html', form=form, title='Add New User')
        
        conn = get_db()
        cursor = conn.cursor()
        
        try:
            if not form.password.data:
                flash('Password is required.', 'danger')
                conn.close()
                return render_template('user_form.html', form=form, title='Add New User')
            password_hash = generate_password_hash(form.password.data)
            cursor.execute('''
                INSERT INTO users (name, email, password_hash, role)
                VALUES (%s, %s, %s, %s)
            ''', (form.name.data, form.email.data, password_hash, form.role.data))
            conn.commit()
            flash(f'User "{form.name.data}" created successfully!', 'success')
            conn.close()
            return redirect(url_for('manage_users'))
        except Exception as e:
            flash('Email already exists or error occurred.', 'danger')
            conn.close()
    
    return render_template('user_form.html', form=form, title='Add New User')

@app.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def edit_user(user_id):
    from models import UserProfile
    from uuid import uuid4
    
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM users WHERE id = %s', (user_id,))
    user = cursor.fetchone()
    
    if not user:
        flash('User not found.', 'danger')
        conn.close()
        return redirect(url_for('manage_users'))
    
    form = UserEditForm(obj=user)
    profile = UserProfile.get_or_create(user_id)
    
    if form.validate_on_submit():
        try:
            # Update basic user info
            if form.password.data:
                password_hash = generate_password_hash(form.password.data)
                cursor.execute('''
                    UPDATE users SET name = %s, email = %s, password_hash = %s, role = %s
                    WHERE id = %s
                ''', (form.name.data, form.email.data, password_hash, form.role.data, user_id))
            else:
                cursor.execute('''
                    UPDATE users SET name = %s, email = %s, role = %s
                    WHERE id = %s
                ''', (form.name.data, form.email.data, form.role.data, user_id))
            
            conn.commit()
            
            # Handle avatar upload
            avatar_filename = None
            if form.avatar.data:
                avatar_file = form.avatar.data
                ext = avatar_file.filename.rsplit('.', 1)[1].lower()
                avatar_filename = f"{user_id}_{uuid4().hex[:8]}.{ext}"
                
                # Delete old avatar if exists
                UserProfile.delete_avatar(user_id)
                
                # Save new avatar using storage helper
                file_data = avatar_file.read()
                upload_result = upload_file(file_data, avatar_filename, 'uploads/profile')
                # If cloud returned dict, save the URL; otherwise save the filename
                avatar_to_save = upload_result['url'] if isinstance(upload_result, dict) else (upload_result if upload_result else avatar_filename)
            
            # Update profile (avatar and/or bio)
            if avatar_to_save or form.bio.data is not None:
                UserProfile.update_profile(
                    user_id, 
                    avatar_path=avatar_to_save if avatar_to_save else None,
                    bio=form.bio.data if form.bio.data is not None else None
                )
            
            flash(f'User "{form.name.data}" updated successfully!', 'success')
            conn.close()
            return redirect(url_for('manage_users'))
        except Exception as e:
            flash(f'Error updating user: {str(e)}', 'danger')
            conn.close()
    else:
        form.name.data = user['name']
        form.email.data = user['email']
        form.role.data = user['role']
        form.bio.data = UserProfile.get_bio(user_id)
    
    conn.close()
    return render_template('user_form.html', form=form, title='Edit User', edit=True)

@app.route('/users/<int:user_id>/confirm_delete', methods=['GET'])
@login_required
@role_required('admin')
def confirm_delete_user(user_id):
    if user_id == current_user.id:
        flash('You cannot delete your own account.', 'danger')
        return redirect(url_for('manage_users'))
    
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM users WHERE id = %s', (user_id,))
    user = cursor.fetchone()
    if not user:
        flash('User not found.', 'danger')
        conn.close()
        return redirect(url_for('manage_users'))
    
    if user['is_protected']:
        flash('This user is protected and cannot be deleted.', 'danger')
        conn.close()
        return redirect(url_for('manage_users'))
    
    cursor.execute('SELECT COUNT(*) as count FROM users WHERE role = %s', (user['role'],))
    total_users_in_role = cursor.fetchone()['count']
    if total_users_in_role <= 1:
        flash(f'Cannot delete the only {ROLE_LABELS.get(user["role"], user["role"])} user in the system.', 'danger')
        conn.close()
        return redirect(url_for('manage_users'))
    
    cursor.execute('SELECT COUNT(*) as count FROM leads WHERE submitted_by_user_id = %s', (user_id,))
    leads_count = cursor.fetchone()['count']
    
    cursor.execute('SELECT COUNT(*) as count FROM lead_activities WHERE actor_id = %s', (user_id,))
    activities_count = cursor.fetchone()['count']
    
    cursor.execute('SELECT COUNT(*) as count FROM leads WHERE current_manager_id = %s', (user_id,))
    assigned_leads_count = cursor.fetchone()['count']
    
    cursor.execute('SELECT COUNT(*) as count FROM leads WHERE assigned_bd_id = %s', (user_id,))
    bd_leads_count = cursor.fetchone()['count']
    
    cursor.execute('SELECT COUNT(*) as count FROM lead_targets WHERE assignee_id = %s', (user_id,))
    targets_count = cursor.fetchone()['count']
    
    cursor.execute('SELECT id, name, email FROM users WHERE role = %s AND id != %s', (user['role'], user_id))
    replacement_users = cursor.fetchall()
    
    conn.close()
    
    data_summary = {
        'leads_submitted': leads_count,
        'activities': activities_count,
        'assigned_leads': assigned_leads_count,
        'bd_leads': bd_leads_count,
        'targets': targets_count
    }
    
    return render_template('confirm_user_delete.html', 
                         user=user, 
                         replacement_users=replacement_users,
                         data_summary=data_summary,
                         role_labels=ROLE_LABELS)

@app.route('/users/<int:user_id>/delete', methods=['POST'])
@login_required
@role_required('admin')
def delete_user(user_id):
    if user_id == current_user.id:
        flash('You cannot delete your own account.', 'danger')
        return redirect(url_for('manage_users'))
    
    replacement_user_id = request.form.get('replacement_user_id')
    replacement_user = None
    
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM users WHERE id = %s', (user_id,))
    user = cursor.fetchone()
    if not user:
        flash('User not found.', 'danger')
        conn.close()
        return redirect(url_for('manage_users'))
    
    if user['is_protected']:
        flash('This user is protected and cannot be deleted.', 'danger')
        conn.close()
        return redirect(url_for('manage_users'))
    
    cursor.execute('SELECT COUNT(*) as count FROM users WHERE role = %s', (user['role'],))
    total_users_in_role = cursor.fetchone()['count']
    if total_users_in_role <= 1:
        flash(f'Cannot delete the only {ROLE_LABELS.get(user["role"], user["role"])} user in the system.', 'danger')
        conn.close()
        return redirect(url_for('manage_users'))
    
    if replacement_user_id:
        cursor.execute('SELECT * FROM users WHERE id = %s', (replacement_user_id,))
        replacement_user = cursor.fetchone()
        if not replacement_user or replacement_user['role'] != user['role']:
            flash('Invalid replacement user selected.', 'danger')
            conn.close()
            return redirect(url_for('manage_users'))
    
    try:
        if replacement_user_id:
            cursor.execute('UPDATE leads SET submitted_by_user_id = %s WHERE submitted_by_user_id = %s', (replacement_user_id, user_id))
            cursor.execute('UPDATE lead_activities SET actor_id = %s WHERE actor_id = %s', (replacement_user_id, user_id))
            cursor.execute('UPDATE leads SET current_manager_id = %s WHERE current_manager_id = %s', (replacement_user_id, user_id))
            cursor.execute('UPDATE leads SET assigned_bd_id = %s WHERE assigned_bd_id = %s', (replacement_user_id, user_id))
            cursor.execute('UPDATE lead_assignments SET manager_id = %s WHERE manager_id = %s', (replacement_user_id, user_id))
            cursor.execute('UPDATE bd_assignment_history SET to_bd_id = %s WHERE to_bd_id = %s', (replacement_user_id, user_id))
            cursor.execute('UPDATE bd_assignment_history SET from_bd_id = %s WHERE from_bd_id = %s', (replacement_user_id, user_id))
            cursor.execute('UPDATE bd_assignment_history SET assigned_by_id = %s WHERE assigned_by_id = %s', (replacement_user_id, user_id))
            cursor.execute('UPDATE lead_targets SET assignee_id = %s WHERE assignee_id = %s', (replacement_user_id, user_id))
            cursor.execute('UPDATE lead_targets SET assigned_by_id = %s WHERE assigned_by_id = %s', (replacement_user_id, user_id))
            cursor.execute('UPDATE lead_social_profiles SET added_by_id = %s WHERE added_by_id = %s', (replacement_user_id, user_id))
            cursor.execute('UPDATE lead_edit_changes SET editor_user_id = %s WHERE editor_user_id = %s', (replacement_user_id, user_id))
            cursor.execute('UPDATE lead_stage_history SET changed_by_id = %s WHERE changed_by_id = %s', (replacement_user_id, user_id))
            cursor.execute('UPDATE lead_assignment_history SET from_manager_id = %s WHERE from_manager_id = %s', (replacement_user_id, user_id))
            cursor.execute('UPDATE lead_assignment_history SET to_manager_id = %s WHERE to_manager_id = %s', (replacement_user_id, user_id))
            
            if user['role'] == 'manager':
                cursor.execute('UPDATE assignment_settings SET last_assigned_manager_id = %s WHERE last_assigned_manager_id = %s', (replacement_user_id, user_id))
            elif user['role'] == 'bd_sales':
                cursor.execute('UPDATE assignment_settings SET last_assigned_bd_id = %s WHERE last_assigned_bd_id = %s', (replacement_user_id, user_id))
        else:
            # Delete all references in correct order (child tables first, then parent tables)
            cursor.execute('UPDATE leads SET current_manager_id = NULL WHERE current_manager_id = %s', (user_id,))
            cursor.execute('UPDATE leads SET assigned_bd_id = NULL WHERE assigned_bd_id = %s', (user_id,))
            
            # Delete records where user is referenced (not just lead-based)
            cursor.execute('DELETE FROM lead_social_profiles WHERE added_by_id = %s', (user_id,))
            cursor.execute('DELETE FROM lead_edit_changes WHERE editor_user_id = %s', (user_id,))
            cursor.execute('DELETE FROM lead_stage_history WHERE changed_by_id = %s', (user_id,))
            cursor.execute('DELETE FROM lead_assignment_history WHERE from_manager_id = %s OR to_manager_id = %s', (user_id, user_id))
            cursor.execute('DELETE FROM lead_activities WHERE actor_id = %s', (user_id,))
            cursor.execute('DELETE FROM lead_assignments WHERE manager_id = %s', (user_id,))
            cursor.execute('DELETE FROM bd_assignment_history WHERE to_bd_id = %s OR from_bd_id = %s OR assigned_by_id = %s', (user_id, user_id, user_id))
            cursor.execute('DELETE FROM lead_targets WHERE assignee_id = %s OR assigned_by_id = %s', (user_id, user_id))
            
            # Now delete lead-based child records for the user's leads
            cursor.execute('DELETE FROM lead_activities WHERE lead_id IN (SELECT id FROM leads WHERE submitted_by_user_id = %s)', (user_id,))
            cursor.execute('DELETE FROM lead_social_profiles WHERE lead_id IN (SELECT id FROM leads WHERE submitted_by_user_id = %s)', (user_id,))
            cursor.execute('DELETE FROM lead_stage_history WHERE lead_id IN (SELECT id FROM leads WHERE submitted_by_user_id = %s)', (user_id,))
            cursor.execute('DELETE FROM lead_edit_changes WHERE lead_id IN (SELECT id FROM leads WHERE submitted_by_user_id = %s)', (user_id,))
            cursor.execute('DELETE FROM lead_assignments WHERE lead_id IN (SELECT id FROM leads WHERE submitted_by_user_id = %s)', (user_id,))
            cursor.execute('DELETE FROM lead_assignment_history WHERE lead_id IN (SELECT id FROM leads WHERE submitted_by_user_id = %s)', (user_id,))
            cursor.execute('DELETE FROM bd_assignment_history WHERE lead_id IN (SELECT id FROM leads WHERE submitted_by_user_id = %s)', (user_id,))
            cursor.execute('DELETE FROM notifications WHERE lead_id IN (SELECT id FROM leads WHERE submitted_by_user_id = %s)', (user_id,))
            
            # Finally delete the leads themselves
            cursor.execute('DELETE FROM leads WHERE submitted_by_user_id = %s', (user_id,))
        
        cursor.execute('DELETE FROM notifications WHERE user_id = %s', (user_id,))
        cursor.execute('DELETE FROM user_profiles WHERE user_id = %s', (user_id,))
        cursor.execute('DELETE FROM users WHERE id = %s', (user_id,))
        
        conn.commit()
        
        if replacement_user_id and replacement_user:
            flash(f'User "{user["name"]}" deleted successfully. All data transferred to {replacement_user["name"]}.', 'success')
        else:
            flash(f'User "{user["name"]}" and all related data deleted successfully!', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Error deleting user: {str(e)}', 'danger')
        app.logger.error(f'Error deleting user {user_id}: {str(e)}')
    finally:
        conn.close()
    
    return redirect(url_for('manage_users'))

@app.route('/export/leads')
@login_required
@role_required('admin', 'manager')
def export_leads():
    conn = get_db()
    cursor = conn.cursor()
    
    status_filter = request.args.get('status', '')
    service_filter = request.args.get('service', '')
    submitter_filter = request.args.get('submitter', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    
    query = '''
        SELECT l.*, u.name as submitter_name
        FROM leads l
        JOIN users u ON l.submitted_by_user_id = u.id
        WHERE 1=1
    '''
    params = []
    
    if status_filter:
        query += ' AND l.status = %s'
        params.append(status_filter)
    
    if service_filter:
        query += ' AND (l.services_csv LIKE %s OR l.services_csv LIKE %s OR l.services_csv LIKE %s OR l.services_csv = %s)'
        params.extend([f'{service_filter},%', f'%,{service_filter},%', f'%,{service_filter}', service_filter])
    
    if submitter_filter:
        query += ' AND l.submitted_by_user_id = %s'
        params.append(submitter_filter)
    
    if date_from:
        query += ' AND DATE(l.created_at) >= %s'
        params.append(date_from)
    
    if date_to:
        query += ' AND DATE(l.created_at) <= %s'
        params.append(date_to)
    
    query += ' ORDER BY l.created_at DESC'
    
    cursor.execute(query, params)
    leads = cursor.fetchall()
    
    output = StringIO()
    writer = csv.writer(output)
    
    writer.writerow(['ID', 'Submitted By', 'Created At', 'Full Name', 'Email', 'Phone', 
                    'Company', 'Domain', 'Services', 'Country', 'State', 'City', 
                    'Status', 'Attachment'])
    
    for lead in leads:
        # Parse services - handle both IDs and names in CSV
        if lead['services_csv']:
            service_parts = [s.strip() for s in lead['services_csv'].split(',')]
            if service_parts and service_parts[0].isdigit():
                service_ids = [int(s) for s in service_parts]
                placeholders = ','.join(['%s'] * len(service_ids))
                cursor.execute(f'SELECT name FROM services WHERE id IN ({placeholders})', service_ids)
                services = ', '.join([row['name'] for row in cursor.fetchall()])
            else:
                services = ', '.join(service_parts)
        else:
            services = ''
        
        writer.writerow([
            lead['id'], lead['submitter_name'], lead['created_at'], lead['full_name'],
            lead['email'], lead['phone'], lead['company'], lead['domain'], services,
            lead['country'], lead['state'], lead['city'], lead['status'],
            lead['attachment_path'] or 'N/A'
        ])
    
    conn.close()
    
    filename_suffix = []
    if status_filter:
        filename_suffix.append(status_filter.lower())
    if date_from:
        filename_suffix.append(f'from_{date_from}')
    if date_to:
        filename_suffix.append(f'to_{date_to}')
    
    filename = f'leads_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
    if filename_suffix:
        filename += '_' + '_'.join(filename_suffix)
    filename += '.csv'
    
    response = make_response(output.getvalue())
    response.headers['Content-Disposition'] = f'attachment; filename={filename}'
    response.headers['Content-Type'] = 'text/csv'
    
    return response

@app.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    from models import UserProfile
    from uuid import uuid4
    
    form = ProfileForm()
    profile = UserProfile.get_or_create(current_user.id)
    
    if form.validate_on_submit():
        if form.password.data and form.password.data != form.confirm_password.data:
            flash('Passwords do not match.', 'danger')
            return render_template('profile_edit.html', form=form, profile=profile)
        
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute('SELECT email FROM users WHERE email = %s AND id != %s', (form.email.data, current_user.id))
        if cursor.fetchone():
            flash('Email already exists.', 'danger')
            conn.close()
            return render_template('profile_edit.html', form=form, profile=profile)
        
        try:
            # Update user basic info
            if form.password.data:
                password_hash = generate_password_hash(form.password.data)
                cursor.execute('''
                    UPDATE users SET name = %s, email = %s, password_hash = %s
                    WHERE id = %s
                ''', (form.name.data, form.email.data, password_hash, current_user.id))
            else:
                cursor.execute('''
                    UPDATE users SET name = %s, email = %s
                    WHERE id = %s
                ''', (form.name.data, form.email.data, current_user.id))
            
            conn.commit()
            current_user.name = form.name.data
            current_user.email = form.email.data
            
            # Handle avatar upload
            avatar_filename = None
            if form.avatar.data:
                avatar_file = form.avatar.data
                ext = avatar_file.filename.rsplit('.', 1)[1].lower()
                avatar_filename = f"{current_user.id}_{uuid4().hex[:8]}.{ext}"
                
                # Delete old avatar if exists
                UserProfile.delete_avatar(current_user.id)
                
                # Save new avatar using storage helper
                file_data = avatar_file.read()
                upload_result = upload_file(file_data, avatar_filename, 'uploads/profile')
                avatar_to_save = upload_result['url'] if isinstance(upload_result, dict) else (upload_result if upload_result else avatar_filename)
            
            # Update profile (avatar and/or bio)
            if avatar_to_save or form.bio.data is not None:
                UserProfile.update_profile(
                    current_user.id, 
                    avatar_path=avatar_to_save if avatar_to_save else None,
                    bio=form.bio.data if form.bio.data is not None else None
                )
            
            flash('Profile updated successfully!', 'success')
            conn.close()
            return redirect(url_for('dashboard'))
        except Exception as e:
            flash(f'Error updating profile: {str(e)}', 'danger')
            conn.close()
    else:
        form.name.data = current_user.name
        form.email.data = current_user.email
        form.bio.data = UserProfile.get_bio(current_user.id)
    
    return render_template('profile_edit.html', form=form, profile=profile)

@app.route('/uploads/profile/<filename>')
def uploaded_profile(filename):
    """Serve uploaded profile pictures"""
    file_data = download_file(filename, 'uploads/profile')
    if file_data:
        return send_file(
            BytesIO(file_data),
            mimetype=get_mime_type(filename),
            download_name=filename
        )
    return send_from_directory('uploads/profile', filename)

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    """Serve uploaded lead attachments"""
    file_data = download_file(filename, 'uploads')
    if file_data:
        return send_file(
            BytesIO(file_data),
            mimetype=get_mime_type(filename),
            as_attachment=True,
            download_name=filename
        )
    # Try local filesystem as fallback
    local_path = os.path.join('uploads', filename)
    if os.path.exists(local_path):
        return send_from_directory('uploads', filename, as_attachment=True)
    # File not found in any storage
    flash('File not found. It may have been uploaded before cloud storage was enabled.', 'warning')
    return redirect(request.referrer or url_for('dashboard'))

@app.route('/uploads/view/<filename>')
def view_uploaded_file(filename):
    """View uploaded lead attachments inline (for preview)"""
    # If filename is a full URL (external storage), redirect to it so browser can preview
    if isinstance(filename, str) and filename.startswith('http'):
        return redirect(filename)

    file_data = download_file(filename, 'uploads')
    if file_data:
        return send_file(
            BytesIO(file_data),
            mimetype=get_mime_type(filename),
            download_name=filename
        )
    # Try local filesystem as fallback
    local_path = os.path.join('uploads', filename)
    if os.path.exists(local_path):
        return send_from_directory('uploads', filename)
    # Return a simple error message for preview iframe
    return '<div style="padding: 20px; font-family: Arial; color: #666;"><h3>File Not Available</h3><p>This file was uploaded before cloud storage was enabled and is no longer available. Please re-upload the attachment.</p></div>', 404


from urllib.parse import urlparse


@app.route('/uploads/download_external')
def download_external():
    """Redirect external file URLs (e.g., Cloudinary) to a download-friendly URL.

    For Cloudinary URLs this inserts the `fl_attachment` transformation so the
    browser will download the file instead of attempting an inline preview.
    """
    url = request.args.get('url')
    if not url:
        abort(400)

    parsed = urlparse(url)
    netloc = parsed.netloc or ''
    # Only allow Cloudinary domains (simple safety check to avoid open redirects)
    if 'cloudinary.com' in netloc:
        # Insert the fl_attachment flag after the /upload/ segment
        if '/upload/' in url:
            download_url = url.replace('/upload/', '/upload/fl_attachment/', 1)
            return redirect(download_url)
    # Fall back to redirecting to the original URL
    return redirect(url)

@app.route('/lead/<int:lead_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('admin', 'manager', 'marketer')
def edit_lead(lead_id):
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM leads WHERE id = %s', (lead_id,))
    lead = cursor.fetchone()
    
    if not lead:
        flash('Lead not found.', 'danger')
        conn.close()
        return redirect(url_for('dashboard'))
    
    if current_user.role == 'marketer':
        if lead['submitted_by_user_id'] != current_user.id:
            flash('You can only edit your own leads.', 'danger')
            conn.close()
            return redirect(url_for('dashboard'))
        
        if lead['status'] not in ['Rejected', 'Resubmitted']:
            flash('Only rejected leads can be edited.', 'danger')
            conn.close()
            return redirect(url_for('view_lead', lead_id=lead_id))
    
    cursor.execute('SELECT * FROM services ORDER BY name')
    services = cursor.fetchall()
    form = LeadEditForm()
    form.services.choices = [(s['id'], s['name']) for s in services]
    
    if form.validate_on_submit():
        changes = []
        
        if lead['full_name'] != form.full_name.data:
            changes.append(('full_name', lead['full_name'], form.full_name.data))
        if lead['email'] != form.email.data:
            changes.append(('email', lead['email'], form.email.data))
        if lead['phone'] != form.phone.data:
            changes.append(('phone', lead['phone'], form.phone.data))
        if lead['company'] != form.company.data:
            changes.append(('company', lead['company'], form.company.data))
        if lead['domain'] != form.domain.data:
            changes.append(('domain', lead['domain'], form.domain.data))
        if lead['industry'] != form.industry.data:
            changes.append(('industry', lead['industry'], form.industry.data))
        if lead['country'] != form.country.data:
            changes.append(('country', lead['country'], form.country.data))
        if lead['state'] != form.state.data:
            changes.append(('state', lead['state'], form.state.data))
        if lead['city'] != form.city.data:
            changes.append(('city', lead['city'], form.city.data))
        
        new_services_csv = ','.join([str(s) for s in (form.services.data or [])])
        if lead['services_csv'] != new_services_csv:
            # Parse old services - handle both IDs and names
            old_service_parts = [s.strip() for s in lead['services_csv'].split(',')]
            if old_service_parts and old_service_parts[0].isdigit():
                old_service_ids = [int(s) for s in old_service_parts]
                placeholders = ','.join(['%s'] * len(old_service_ids))
                cursor.execute(f'SELECT name FROM services WHERE id IN ({placeholders})', old_service_ids)
                old_services = ', '.join([row['name'] for row in cursor.fetchall()])
            else:
                old_services = ', '.join(old_service_parts)
            
            service_data = form.services.data or []
            if len(service_data) > 0:
                placeholders = ','.join(['%s'] * len(service_data))
                cursor.execute(f'SELECT name FROM services WHERE id IN ({placeholders})', service_data)
                new_services = ', '.join([row['name'] for row in cursor.fetchall()])
            else:
                new_services = ''
            
            changes.append(('services', old_services, new_services))
        
        attachment_path = lead['attachment_path']
        if form.attachment.data:
            file = form.attachment.data
            filename = secure_filename(file.filename)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{timestamp}_{filename}"
            file_data = file.read()
            upload_result = upload_file(file_data, filename, 'uploads')
            # Normalize stored value to a URL or local filename
            if isinstance(upload_result, dict):
                new_attachment_value = upload_result.get('url')
            else:
                new_attachment_value = upload_result if upload_result else filename

            if lead['attachment_path']:
                changes.append(('attachment', lead['attachment_path'], new_attachment_value))
            else:
                changes.append(('attachment', 'None', new_attachment_value))
            attachment_path = new_attachment_value
        
        for field_name, old_val, new_val in changes:
            cursor.execute('''
                INSERT INTO lead_edit_changes (lead_id, editor_user_id, field_name, old_value, new_value)
                VALUES (%s, %s, %s, %s, %s)
            ''', (lead_id, current_user.id, field_name, old_val, new_val))
        
        change_details = '\n'.join([f"• {field}: '{old}' → '{new}'" for field, old, new in changes])
        edit_note = f"Lead edited by {current_user.name}:\n{change_details}\n\nSummary: {form.change_summary.data}"
        
        cursor.execute('''
            INSERT INTO lead_notes (lead_id, author_user_id, note_type, message)
            VALUES (%s, %s, 'edit', %s)
        ''', (lead_id, current_user.id, edit_note))
        
        # Handle social profile updates
        cursor.execute('SELECT platform, url FROM lead_social_profiles WHERE lead_id = %s', (lead_id,))
        existing_profiles = {row['platform']: row['url'] for row in cursor.fetchall()}
        
        new_profiles = {}
        if form.linkedin_url.data:
            new_profiles['linkedin'] = form.linkedin_url.data
        if form.twitter_url.data:
            new_profiles['twitter'] = form.twitter_url.data
        if form.facebook_url.data:
            new_profiles['facebook'] = form.facebook_url.data
        if form.website_url.data:
            new_profiles['website'] = form.website_url.data
        
        # Track social profile changes
        for platform in ['linkedin', 'twitter', 'facebook', 'website']:
            old_url = existing_profiles.get(platform, '')
            new_url = new_profiles.get(platform, '')
            if old_url != new_url:
                if old_url and new_url:
                    changes.append((f'{platform}_url', old_url, new_url))
                elif new_url:
                    changes.append((f'{platform}_url', 'None', new_url))
                elif old_url:
                    changes.append((f'{platform}_url', old_url, 'Removed'))
        
        # Delete all existing social profiles and add new ones
        cursor.execute('DELETE FROM lead_social_profiles WHERE lead_id = %s', (lead_id,))
        for platform, url in new_profiles.items():
            cursor.execute('''
                INSERT INTO lead_social_profiles (lead_id, platform, url, added_by_id)
                VALUES (%s, %s, %s, %s)
            ''', (lead_id, platform, url, current_user.id))
        
        cursor.execute('''
            UPDATE leads SET full_name = %s, email = %s, phone = %s, company = %s, domain = %s, industry = %s,
                           services_csv = %s, country = %s, state = %s, city = %s, attachment_path = %s
            WHERE id = %s
        ''', (form.full_name.data, form.email.data, form.phone.data, form.company.data,
              form.domain.data, form.industry.data, new_services_csv, form.country.data, form.state.data,
              form.city.data, attachment_path, lead_id))
        
        safe_commit(conn)
        conn.close()
        
        flash('Lead updated successfully! You can now resubmit it.', 'success')
        return redirect(url_for('view_lead', lead_id=lead_id))
    else:
        form.full_name.data = lead['full_name']
        form.email.data = lead['email']
        form.phone.data = lead['phone']
        form.company.data = lead['company']
        form.domain.data = lead['domain']
        form.industry.data = lead['industry']
        form.services.data = [int(s) for s in lead['services_csv'].split(',')]
        form.country.data = lead['country']
        form.state.data = lead['state']
        form.city.data = lead['city']
        
        # Load existing social profiles
        cursor.execute('SELECT platform, url FROM lead_social_profiles WHERE lead_id = %s', (lead_id,))
        social_profiles = cursor.fetchall()
        for profile in social_profiles:
            if profile['platform'] == 'linkedin':
                form.linkedin_url.data = profile['url']
            elif profile['platform'] == 'twitter':
                form.twitter_url.data = profile['url']
            elif profile['platform'] == 'facebook':
                form.facebook_url.data = profile['url']
            elif profile['platform'] == 'website':
                form.website_url.data = profile['url']
    
    conn.close()
    return render_template('lead_edit.html', form=form, lead_id=lead_id, title='Edit Lead')

@app.route('/analytics')
@login_required
@role_required('admin', 'manager')
def analytics():
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) as count FROM leads')
    total_leads = cursor.fetchone()['count']
    cursor.execute('SELECT COUNT(*) as count FROM leads WHERE status = %s', ('Pending',))
    pending_leads = cursor.fetchone()['count']
    cursor.execute('SELECT COUNT(*) as count FROM leads WHERE status = %s', ('Accepted',))
    accepted_leads = cursor.fetchone()['count']
    cursor.execute('SELECT COUNT(*) as count FROM leads WHERE status = %s', ('Rejected',))
    rejected_leads = cursor.fetchone()['count']
    cursor.execute('SELECT COUNT(*) as count FROM leads WHERE status = %s', ('Resubmitted',))
    resubmitted_leads = cursor.fetchone()['count']
    
    conversion_rate = (accepted_leads / total_leads * 100) if total_leads > 0 else 0
    
    cursor.execute('''
        SELECT u.name, COUNT(l.id) as count
        FROM users u
        LEFT JOIN leads l ON u.id = l.submitted_by_user_id
        WHERE u.role = 'marketer'
        GROUP BY u.id, u.name
        ORDER BY count DESC
    ''')
    leads_by_marketer = cursor.fetchall()
    
    cursor.execute('''
        SELECT DATE(created_at) as date, COUNT(*) as count
        FROM leads
        WHERE created_at >= CURRENT_DATE - INTERVAL '30 days'
        GROUP BY DATE(created_at)
        ORDER BY date
    ''')
    leads_over_time = cursor.fetchall()
    
    cursor.execute('''
        SELECT s.name, COUNT(*) as count
        FROM services s
        LEFT JOIN leads l ON l.services_csv LIKE '%' || s.id || '%'
        GROUP BY s.id, s.name
        ORDER BY count DESC
        LIMIT 10
    ''')
    leads_by_service = cursor.fetchall()
    
    conn.close()
    
    return render_template('analytics.html',
                         total_leads=total_leads,
                         pending_leads=pending_leads,
                         accepted_leads=accepted_leads,
                         rejected_leads=rejected_leads,
                         resubmitted_leads=resubmitted_leads,
                         conversion_rate=conversion_rate,
                         leads_by_marketer=leads_by_marketer,
                         leads_over_time=leads_over_time,
                         leads_by_service=leads_by_service)

@app.route('/api/dismiss-targets-banner', methods=['POST'])
@login_required
def dismiss_targets_banner():
    """Dismiss the targets banner for the current session"""
    session[f'hide_targets_banner_{current_user.id}'] = date.today().isoformat()
    return {'success': True}, 200

@app.route('/api/lead/<int:lead_id>/stage', methods=['PATCH'])
@login_required
@role_required('admin', 'manager', 'bd_sales')
def update_lead_stage(lead_id):
    """Update lead's pipeline stage via drag-and-drop"""
    from flask import jsonify
    
    data = request.get_json()
    if data is None:
        return jsonify({'success': False, 'message': 'Invalid or missing JSON payload'}), 400
    
    new_stage_id = data.get('stage_id')
    if not new_stage_id:
        return jsonify({'success': False, 'message': 'Stage ID is required'}), 400
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Verify stage exists
    cursor.execute('SELECT id, name FROM pipeline_stages WHERE id = %s', (new_stage_id,))
    stage = cursor.fetchone()
    if not stage:
        conn.close()
        return jsonify({'success': False, 'message': 'Invalid stage ID'}), 404
    
    # Fetch lead
    cursor.execute('SELECT * FROM leads WHERE id = %s', (lead_id,))
    lead = cursor.fetchone()
    if not lead:
        conn.close()
        return jsonify({'success': False, 'message': 'Lead not found'}), 404
    
    # Permission check: BD Sales can only update their own leads
    if current_user.role == 'bd_sales' and lead['assigned_bd_id'] != current_user.id:
        conn.close()
        return jsonify({'success': False, 'message': 'You can only update your assigned leads'}), 403
    
    # Get old stage name for history
    old_stage_id = lead['current_stage_id']
    old_stage_name = None
    if old_stage_id:
        cursor.execute('SELECT name FROM pipeline_stages WHERE id = %s', (old_stage_id,))
        old_stage_row = cursor.fetchone()
        if old_stage_row:
            old_stage_name = old_stage_row['name']
    
    # Update lead stage
    cursor.execute('''
        UPDATE leads 
        SET current_stage_id = %s 
        WHERE id = %s
    ''', (new_stage_id, lead_id))
    
    # Record stage history
    cursor.execute('''
        INSERT INTO lead_stage_history (lead_id, from_stage_id, to_stage_id, changed_by_id, note, changed_at)
        VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
    ''', (lead_id, old_stage_id, new_stage_id, current_user.id, 
          f'Stage changed from {old_stage_name or "None"} to {stage["name"]}'))
    
    # Commit with retry logic
    try:
        safe_commit(conn, context="update_lead_stage")
    except sqlite3.OperationalError as e:
        conn.close()
        return jsonify({'success': False, 'message': 'Database is busy. Please try again.'}), 500
    
    # Emit Socket.IO event for real-time updates (broadcast to all clients by default)
    socketio.emit('lead_stage_updated', {
        'lead_id': lead_id,
        'new_stage_id': new_stage_id,
        'new_stage_name': stage['name'],
        'old_stage_id': old_stage_id,
        'old_stage_name': old_stage_name,
        'changed_by': current_user.name,
        'timestamp': datetime.now().isoformat()
    })
    
    # Notify BD Sales if someone else moved their lead
    if lead['assigned_bd_id'] and lead['assigned_bd_id'] != current_user.id:
        cursor.execute('''
            INSERT INTO notifications (user_id, lead_id, message, notification_type, is_read, sound_enabled)
            VALUES (%s, %s, %s, 'info', 0, 0)
        ''', (lead['assigned_bd_id'], 
              lead_id,
              f'{current_user.name} moved lead "{lead["company"] or lead["full_name"]}" to {stage["name"]}'))
        
        try:
            safe_commit(conn, context="update_lead_stage_notification")
        except sqlite3.OperationalError:
            pass  # If notification fails, don't block the main operation
        
        socketio.emit('new_notification', {
            'message': f'{current_user.name} moved lead "{lead["company"] or lead["full_name"]}" to {stage["name"]}',
            'type': 'stage_change',
            'lead_id': lead_id,
            'timestamp': datetime.now().isoformat()
        }, room=f'user_{lead["assigned_bd_id"]}')
    
    conn.close()
    
    return jsonify({
        'success': True, 
        'message': f'Lead moved to {stage["name"]}',
        'new_stage_name': stage['name']
    }), 200

@app.route('/targets')
@login_required
@role_required('admin', 'manager')
def manage_targets():
    conn = get_db()
    cursor = conn.cursor()
    
    if current_user.role == 'admin':
        cursor.execute('''
            SELECT t.*, u1.name as assigner_name, u2.name as assignee_name, u2.role as assignee_role
            FROM lead_targets t
            JOIN users u1 ON t.assigned_by_id = u1.id
            JOIN users u2 ON t.assignee_id = u2.id
            ORDER BY t.period_start DESC, t.created_at DESC
        ''')
    else:
        cursor.execute('''
            SELECT t.*, u1.name as assigner_name, u2.name as assignee_name, u2.role as assignee_role
            FROM lead_targets t
            JOIN users u1 ON t.assigned_by_id = u1.id
            JOIN users u2 ON t.assignee_id = u2.id
            WHERE t.assigned_by_id = %s OR t.assignee_id = %s
            ORDER BY t.period_start DESC, t.created_at DESC
        ''', (current_user.id, current_user.id))
    
    targets = cursor.fetchall()
    conn.close()
    
    targets_with_progress = []
    for target in targets:
        progress = compute_target_progress(target)
        targets_with_progress.append({
            **dict(target),
            'actual_count': progress['actual'],
            'progress_percent': progress['percent'],
            'can_edit': current_user.role == 'admin' or target['assigned_by_id'] == current_user.id
        })
    
    return render_template('targets.html', targets=targets_with_progress)

@app.route('/targets/new', methods=['GET', 'POST'])
@login_required
@role_required('admin', 'manager')
def new_target():
    form = TargetForm()
    
    conn = get_db()
    cursor = conn.cursor()
    
    if current_user.role == 'admin':
        cursor.execute('SELECT id, name FROM users WHERE role = %s ORDER BY name', ('manager',))
    else:
        cursor.execute('SELECT id, name FROM users WHERE role = %s ORDER BY name', ('marketer',))
    
    assignees = cursor.fetchall()
    form.assignee.choices = [(u['id'], u['name']) for u in assignees]
    
    if form.validate_on_submit():
        if form.period_end.data and form.period_start.data and form.period_end.data <= form.period_start.data:
            flash('Period end must be after period start.', 'danger')
        elif has_period_overlap(form.assignee.data, form.period_start.data, form.period_end.data):
            flash('This period overlaps with an existing target for the selected user.', 'danger')
        else:
            cursor.execute('''
                INSERT INTO lead_targets (assigned_by_id, assignee_id, target_count, 
                                         period_start, period_end, target_type)
                VALUES (%s, %s, %s, %s, %s, %s)
            ''', (current_user.id, form.assignee.data, form.target_count.data,
                  form.period_start.data, form.period_end.data, form.target_type.data))
            
            conn.commit()
            conn.close()
            
            flash('Target created successfully!', 'success')
            return redirect(url_for('manage_targets'))
    
    conn.close()
    return render_template('target_form.html', form=form, title='Create New Target')

@app.route('/targets/<int:target_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('admin', 'manager')
def edit_target(target_id):
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM lead_targets WHERE id = %s', (target_id,))
    target = cursor.fetchone()
    
    if not target:
        flash('Target not found.', 'danger')
        conn.close()
        return redirect(url_for('manage_targets'))
    
    if current_user.role != 'admin' and target['assigned_by_id'] != current_user.id:
        flash('You do not have permission to edit this target.', 'danger')
        conn.close()
        return redirect(url_for('manage_targets'))
    
    form = TargetForm(obj=target)
    
    cursor.execute('SELECT role FROM users WHERE id = %s', (target['assignee_id'],))
    assignee_role = cursor.fetchone()['role']
    
    if current_user.role == 'admin':
        cursor.execute('SELECT id, name FROM users WHERE role = %s ORDER BY name', ('manager',))
    else:
        cursor.execute('SELECT id, name FROM users WHERE role = %s ORDER BY name', ('marketer',))
    
    assignees = cursor.fetchall()
    form.assignee.choices = [(u['id'], u['name']) for u in assignees]
    
    if form.validate_on_submit():
        if form.period_end.data and form.period_start.data and form.period_end.data <= form.period_start.data:
            flash('Period end must be after period start.', 'danger')
        elif has_period_overlap(form.assignee.data, form.period_start.data, form.period_end.data, exclude_id=target_id):
            flash('This period overlaps with an existing target for the selected user.', 'danger')
        else:
            cursor.execute('''
                UPDATE lead_targets 
                SET assignee_id = %s, target_count = %s, period_start = %s, period_end = %s, target_type = %s
                WHERE id = %s
            ''', (form.assignee.data, form.target_count.data, form.period_start.data,
                  form.period_end.data, form.target_type.data, target_id))
            
            conn.commit()
            conn.close()
            
            flash('Target updated successfully!', 'success')
            return redirect(url_for('manage_targets'))
    else:
        form.assignee.data = target['assignee_id']
        form.target_count.data = target['target_count']
        form.period_start.data = datetime.strptime(target['period_start'], '%Y-%m-%d').date()
        form.period_end.data = datetime.strptime(target['period_end'], '%Y-%m-%d').date()
        form.target_type.data = target['target_type']
    
    conn.close()
    return render_template('target_form.html', form=form, title='Edit Target', target_id=target_id)

@app.route('/targets/<int:target_id>/delete', methods=['POST'])
@login_required
@role_required('admin', 'manager')
def delete_target(target_id):
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM lead_targets WHERE id = %s', (target_id,))
    target = cursor.fetchone()
    
    if not target:
        flash('Target not found.', 'danger')
    elif current_user.role != 'admin' and target['assigned_by_id'] != current_user.id:
        flash('You do not have permission to delete this target.', 'danger')
    else:
        cursor.execute('DELETE FROM lead_targets WHERE id = %s', (target_id,))
        conn.commit()
        flash('Target deleted successfully!', 'success')
    
    conn.close()
    return redirect(url_for('manage_targets'))

def backfill_acceptance_timestamps():
    """Backfill acted_at and status for existing accepted leads"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT l.id, l.current_manager_id 
        FROM leads l
        WHERE l.status = 'Accepted' AND l.accepted_at IS NULL
    ''')
    accepted_leads = cursor.fetchall()
    
    for lead in accepted_leads:
        cursor.execute('''
            UPDATE leads 
            SET accepted_at = created_at
            WHERE id = %s
        ''', (lead['id'],))
        
        if lead['current_manager_id']:
            cursor.execute('''
                UPDATE lead_assignments 
                SET acted_at = (SELECT created_at FROM leads WHERE id = %s),
                    status = 'acted'
                WHERE lead_id = %s AND manager_id = %s AND status = 'pending'
            ''', (lead['id'], lead['id'], lead['current_manager_id']))
    
    conn.commit()
    conn.close()
    print(f'Backfilled {len(accepted_leads)} accepted leads with timestamps')

def migrate_activity_timestamps_to_utc():
    """Migrate existing activity timestamps from IST to UTC (with idempotency guard)"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Check if migration has already run (idempotency guard) - skip table creation for PostgreSQL
    if not USE_POSTGRES:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS migration_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                migration_name TEXT UNIQUE NOT NULL,
                run_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
    
    cursor.execute('''
        SELECT id FROM migration_log WHERE migration_name = 'activity_timestamps_ist_to_utc_v1'
    ''')
    if cursor.fetchone():
        print('Migration activity_timestamps_ist_to_utc_v1 already run, skipping...')
        conn.close()
        return
    
    # Get all activities with due_at or reminder_at
    cursor.execute('''
        SELECT id, due_at, reminder_at
        FROM lead_activities
        WHERE due_at IS NOT NULL OR reminder_at IS NOT NULL
    ''')
    activities = cursor.fetchall()
    
    indian_tz = pytz.timezone('Asia/Kolkata')
    utc_tz = pytz.UTC
    updated_count = 0
    
    for activity in activities:
        due_at_utc = None
        reminder_at_utc = None
        
        # Convert due_at from IST to UTC
        if activity['due_at']:
            try:
                # Parse the IST datetime string
                dt_ist_naive = datetime.strptime(activity['due_at'], '%Y-%m-%d %H:%M:%S')
                # Localize as IST
                dt_ist = indian_tz.localize(dt_ist_naive)
                # Convert to UTC
                dt_utc = dt_ist.astimezone(utc_tz)
                due_at_utc = dt_utc.strftime('%Y-%m-%d %H:%M:%S')
            except Exception as e:
                print(f"Error converting due_at for activity {activity['id']}: {e}")
                continue
        
        # Convert reminder_at from IST to UTC
        if activity['reminder_at']:
            try:
                # Parse the IST datetime string
                dt_ist_naive = datetime.strptime(activity['reminder_at'], '%Y-%m-%d %H:%M:%S')
                # Localize as IST
                dt_ist = indian_tz.localize(dt_ist_naive)
                # Convert to UTC
                dt_utc = dt_ist.astimezone(utc_tz)
                reminder_at_utc = dt_utc.strftime('%Y-%m-%d %H:%M:%S')
            except Exception as e:
                print(f"Error converting reminder_at for activity {activity['id']}: {e}")
                continue
        
        # Update the activity with UTC timestamps
        cursor.execute('''
            UPDATE lead_activities
            SET due_at = %s, reminder_at = %s
            WHERE id = %s
        ''', (due_at_utc if due_at_utc else activity['due_at'],
              reminder_at_utc if reminder_at_utc else activity['reminder_at'],
              activity['id']))
        updated_count += 1
    
    # Mark migration as complete
    cursor.execute('''
        INSERT INTO migration_log (migration_name) VALUES ('activity_timestamps_ist_to_utc_v1')
    ''')
    
    conn.commit()
    conn.close()
    print(f'Migrated {updated_count} activity timestamps from IST to UTC')

def fix_double_converted_timestamps():
    """Fix timestamps that were converted twice (IST→UTC→UTC) by adding back 11 hours"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Ensure migration_log table exists (skip for PostgreSQL as it's already created)
    if not USE_POSTGRES:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS migration_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                migration_name TEXT UNIQUE NOT NULL,
                run_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)
        ''')
    
    # Check if this corrective migration has already run
    cursor.execute('''
        SELECT id FROM migration_log WHERE migration_name = 'fix_double_converted_timestamps_v1'
    ''')
    if cursor.fetchone():
        print('Corrective migration fix_double_converted_timestamps_v1 already run, skipping...')
        conn.close()
        return
    
    # Get all activities with due_at or reminder_at
    cursor.execute('''
        SELECT id, due_at, reminder_at
        FROM lead_activities
        WHERE due_at IS NOT NULL OR reminder_at IS NOT NULL
    ''')
    activities = cursor.fetchall()
    
    updated_count = 0
    
    for activity in activities:
        due_at_fixed = None
        reminder_at_fixed = None
        
        # Fix due_at by adding back 11 hours (2 x 5.5 hours that were incorrectly subtracted)
        if activity['due_at']:
            try:
                dt = datetime.strptime(activity['due_at'], '%Y-%m-%d %H:%M:%S')
                # Add back 11 hours
                dt_fixed = dt + timedelta(hours=11)
                due_at_fixed = dt_fixed.strftime('%Y-%m-%d %H:%M:%S')
            except Exception as e:
                print(f"Error fixing due_at for activity {activity['id']}: {e}")
                continue
        
        # Fix reminder_at by adding back 11 hours
        if activity['reminder_at']:
            try:
                dt = datetime.strptime(activity['reminder_at'], '%Y-%m-%d %H:%M:%S')
                # Add back 11 hours
                dt_fixed = dt + timedelta(hours=11)
                reminder_at_fixed = dt_fixed.strftime('%Y-%m-%d %H:%M:%S')
            except Exception as e:
                print(f"Error fixing reminder_at for activity {activity['id']}: {e}")
                continue
        
        # Update the activity with fixed timestamps
        if due_at_fixed or reminder_at_fixed:
            cursor.execute('''
                UPDATE lead_activities
                SET due_at = %s, reminder_at = %s
                WHERE id = %s
            ''', (due_at_fixed if due_at_fixed else activity['due_at'],
                  reminder_at_fixed if reminder_at_fixed else activity['reminder_at'],
                  activity['id']))
            updated_count += 1
    
    # Mark corrective migration as complete
    cursor.execute('''
        INSERT INTO migration_log (migration_name) VALUES ('fix_double_converted_timestamps_v1')
    ''')
    
    conn.commit()
    conn.close()
    print(f'Fixed {updated_count} double-converted activity timestamps by adding back 11 hours')

def add_protected_users_column():
    """Migration to add is_protected column to users table and mark one user per role as protected"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT migration_name FROM migration_log WHERE migration_name = 'add_is_protected_to_users_v1'")
    if cursor.fetchone():
        print('Migration add_is_protected_to_users_v1 already run, skipping...')
        conn.close()
        return
    
    cursor.execute("PRAGMA table_info(users)")
    columns = [row[1] for row in cursor.fetchall()]
    
    if 'is_protected' not in columns:
        cursor.execute('ALTER TABLE users ADD COLUMN is_protected INTEGER DEFAULT 0')
        print('Added is_protected column to users table')
    
    protected_count = 0
    for role in ['admin', 'manager', 'marketer', 'bd_sales']:
        execute_query(cursor, 'SELECT id FROM users WHERE role = %s ORDER BY id ASC LIMIT 1', (role,))
        user = cursor.fetchone()
        if user:
            execute_query(cursor, 'UPDATE users SET is_protected = 1 WHERE id = %s', (user['id'],))
            protected_count += 1
            print(f'Marked user ID {user["id"]} as protected ({role})')
    
    cursor.execute("INSERT INTO migration_log (migration_name) VALUES ('add_is_protected_to_users_v1')")
    conn.commit()
    conn.close()
    print(f'Protected users migration completed. Marked {protected_count} users as protected.')

with app.app_context():
    init_db()

with app.app_context():
    backfill_acceptance_timestamps()

# Step 1: Fix corrupted data from double migration
with app.app_context():
    fix_double_converted_timestamps()

# Step 2: Run main migration (with guard, safe to enable)
with app.app_context():
    migrate_activity_timestamps_to_utc()

# Step 3: Add protected users column and mark one user per role as protected
with app.app_context():
    add_protected_users_column()

scheduler = BackgroundScheduler()

# Job 1: Check and reassign overdue leads (every 30 minutes instead of 15)
scheduler.add_job(
    func=check_and_reassign_overdue_leads,
    trigger=IntervalTrigger(minutes=30),
    id='check_overdue_leads',
    name='Check and reassign overdue leads every 30 minutes',
    replace_existing=True
)

# Job 2: Check and send activity reminders (every hour instead of 30 minutes)
scheduler.add_job(
    func=check_and_send_activity_reminders,
    trigger=IntervalTrigger(hours=1),
    id='check_activity_reminders',
    name='Check and send activity reminders every hour',
    replace_existing=True
)

scheduler.start()
print('APScheduler started:')
print('  - Checking for overdue leads every 30 minutes')
print('  - Checking for activity reminders every hour')

@app.after_request
def add_cache_headers(response):
    if request.path.startswith('/static/'):
        response.headers['Cache-Control'] = 'public, max-age=86400'  # 24 hours
    return response

@app.errorhandler(500)
def internal_error(error):
    import traceback
    print("500 Error:", error)
    print(traceback.format_exc())
    return "Internal Server Error", 500

if __name__ == '__main__':
    try:
        socketio.run(app, host='0.0.0.0', port=5000, debug=False, use_reloader=False, log_output=True)
    finally:
        scheduler.shutdown()
        print('APScheduler shutdown')
