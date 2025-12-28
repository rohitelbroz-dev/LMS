#!/usr/bin/env python
"""Test script to verify edit target functionality"""

from app import app, get_db, execute_query
from datetime import date
import sys

def test_edit_target():
    """Test the edit target route"""
    with app.app_context():
        conn = get_db()
        cursor = conn.cursor()
        
        # Get first admin user
        execute_query(cursor, 'SELECT id FROM users WHERE role = %s LIMIT 1', ('admin',))
        admin = cursor.fetchone()
        
        if not admin:
            print("❌ No admin user found")
            conn.close()
            return False
        
        # Get the test target we created
        execute_query(cursor, 'SELECT * FROM lead_targets WHERE id = 3')
        target = cursor.fetchone()
        
        if not target:
            print("❌ Test target ID 3 not found")
            conn.close()
            return False
        
        print(f"✅ Found target: {target}")
        
        # Try to simulate what the edit_target route does
        try:
            # Check assignee exists
            execute_query(cursor, 'SELECT role FROM users WHERE id = %s', (target['assignee_id'],))
            assignee_user = cursor.fetchone()
            
            if not assignee_user:
                print(f"❌ Assignee user with ID {target['assignee_id']} not found")
                conn.close()
                return False
            
            print(f"✅ Assignee user found: {assignee_user}")
            
            # Get the choices for the form
            if admin['id'] == 1:  # Assuming admin
                execute_query(cursor, 'SELECT id, name FROM users WHERE role = %s ORDER BY name', ('manager',))
            else:
                execute_query(cursor, 'SELECT id, name FROM users WHERE role = %s ORDER BY name', ('marketer',))
            
            assignees = cursor.fetchall()
            print(f"✅ Found {len(assignees)} assignee choices")
            
            # Test update
            execute_query(cursor, '''
                UPDATE lead_targets 
                SET assignee_id = %s, target_count = %s, period_start = %s, period_end = %s, target_type = %s
                WHERE id = %s
            ''', (target['assignee_id'], 100, target['period_start'], target['period_end'], target['target_type'], 3))
            
            conn.commit()
            print("✅ Target updated successfully")
            
            conn.close()
            return True
            
        except Exception as e:
            print(f"❌ Error during edit: {e}")
            import traceback
            traceback.print_exc()
            conn.close()
            return False

if __name__ == '__main__':
    success = test_edit_target()
    sys.exit(0 if success else 1)
