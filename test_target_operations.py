#!/usr/bin/env python
"""Test script to verify target creation and update functionality"""

from app import app, get_db, execute_query
from datetime import date
import json

def test_target_operations():
    """Test create and update target operations"""
    
    print("=" * 60)
    print("Testing Target Operations (Create & Update)")
    print("=" * 60)
    
    with app.app_context():
        conn = get_db()
        cursor = conn.cursor()
        
        # Get admin and manager
        execute_query(cursor, 'SELECT id FROM users WHERE role = %s LIMIT 1', ('admin',))
        admin = cursor.fetchone()
        
        execute_query(cursor, 'SELECT id FROM users WHERE role = %s LIMIT 1', ('manager',))
        manager = cursor.fetchone()
        
        if not admin or not manager:
            print("❌ Missing admin or manager user")
            conn.close()
            return False
        
        print(f"\n👤 Admin ID: {admin['id']}")
        print(f"👤 Manager ID: {manager['id']}")
        
        # Test 1: Create a new target
        print("\n📝 Test 1: Creating a new target...")
        try:
            execute_query(cursor, '''
                INSERT INTO lead_targets (assigned_by_id, assignee_id, target_count, 
                                         period_start, period_end, target_type)
                VALUES (%s, %s, %s, %s, %s, %s)
            ''', (admin['id'], manager['id'], 50, date(2025, 3, 1), date(2025, 3, 31), 'monthly'))
            
            conn.commit()
            
            execute_query(cursor, 'SELECT id FROM lead_targets ORDER BY id DESC LIMIT 1')
            new_target = cursor.fetchone()
            target_id = new_target['id']
            
            print(f"✅ Target created successfully with ID: {target_id}")
        except Exception as e:
            print(f"❌ Failed to create target: {e}")
            conn.close()
            return False
        
        # Test 2: Update the target
        print(f"\n📝 Test 2: Updating target ID {target_id}...")
        try:
            execute_query(cursor, '''
                UPDATE lead_targets 
                SET target_count = %s, target_type = %s
                WHERE id = %s
            ''', (100, 'weekly', target_id))
            
            conn.commit()
            print(f"✅ Target updated successfully")
        except Exception as e:
            print(f"❌ Failed to update target: {e}")
            conn.close()
            return False
        
        # Test 3: Verify the update
        print(f"\n📝 Test 3: Verifying target update...")
        try:
            execute_query(cursor, 'SELECT target_count, target_type FROM lead_targets WHERE id = %s', (target_id,))
            result = cursor.fetchone()
            
            if result['target_count'] == 100 and result['target_type'] == 'weekly':
                print(f"✅ Target verified: count={result['target_count']}, type={result['target_type']}")
            else:
                print(f"❌ Target data mismatch: count={result['target_count']}, type={result['target_type']}")
                conn.close()
                return False
        except Exception as e:
            print(f"❌ Failed to verify target: {e}")
            conn.close()
            return False
        
        # Test 4: Delete the test target
        print(f"\n📝 Test 4: Deleting test target ID {target_id}...")
        try:
            execute_query(cursor, 'DELETE FROM lead_targets WHERE id = %s', (target_id,))
            conn.commit()
            print(f"✅ Target deleted successfully")
        except Exception as e:
            print(f"❌ Failed to delete target: {e}")
            conn.close()
            return False
        
        conn.close()
        return True

if __name__ == '__main__':
    try:
        success = test_target_operations()
        if success:
            print("\n" + "=" * 60)
            print("✅ All tests passed!")
            print("=" * 60)
        else:
            print("\n❌ Some tests failed")
    except Exception as e:
        print(f"\n❌ Test error: {e}")
        import traceback
        traceback.print_exc()
