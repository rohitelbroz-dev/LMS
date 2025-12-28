#!/usr/bin/env python
"""Test target creation workflow with form validation"""

from app import app, get_db, execute_query, has_period_overlap, safe_commit
from datetime import date
from forms import TargetForm

def test_new_target_workflow():
    """Test the complete new_target workflow"""
    
    print("=" * 70)
    print("Testing New Target Workflow (Simulating POST /targets/new)")
    print("=" * 70)
    
    with app.app_context():
        conn = get_db()
        cursor = conn.cursor()
        
        try:
            # Get admin and manager
            execute_query(cursor, 'SELECT id FROM users WHERE role = %s LIMIT 1', ('admin',))
            admin = cursor.fetchone()
            
            execute_query(cursor, 'SELECT id FROM users WHERE role = %s LIMIT 1', ('manager',))
            manager = cursor.fetchone()
            
            print(f"\n👤 Admin ID: {admin['id']}, Manager ID: {manager['id']}")
            
            # Step 1: Get assignees (what new_target does on GET)
            print("\n1️⃣ Step 1: Get assignee choices...")
            execute_query(cursor, 'SELECT id, name FROM users WHERE role = %s ORDER BY name', ('manager',))
            assignees = cursor.fetchall()
            print(f"   ✅ Got {len(assignees)} assignees")
            
            # Step 2: Simulate form validation (POST)
            print("\n2️⃣ Step 2: Form data received...")
            form_assignee = manager['id']
            form_count = 60
            form_start = date(2025, 6, 1)
            form_end = date(2025, 6, 30)
            form_type = 'monthly'
            print(f"   ✅ Form data: assignee={form_assignee}, count={form_count}, type={form_type}")
            
            # Step 3: Check date validation
            print("\n3️⃣ Step 3: Validate dates...")
            if form_end <= form_start:
                print("   ❌ Period end must be after period start")
                return False
            print(f"   ✅ Dates valid: {form_start} to {form_end}")
            
            # Step 4: Check overlap (THIS WAS THE BUG - need to pass cursor!)
            print("\n4️⃣ Step 4: Check period overlap (cursor-aware)...")
            overlap = has_period_overlap(form_assignee, form_start, form_end, cursor=cursor)
            if overlap:
                print("   ❌ Period overlaps with existing target")
                return False
            print(f"   ✅ No overlap detected")
            
            # Step 5: Verify cursor still works after overlap check
            print("\n5️⃣ Step 5: Verify cursor is still usable...")
            execute_query(cursor, 'SELECT COUNT(*) as count FROM lead_targets')
            count_result = cursor.fetchone()
            print(f"   ✅ Cursor works! Current target count: {count_result['count']}")
            
            # Step 6: Insert the target
            print("\n6️⃣ Step 6: Insert new target...")
            execute_query(cursor, '''
                INSERT INTO lead_targets (assigned_by_id, assignee_id, target_count, 
                                         period_start, period_end, target_type)
                VALUES (%s, %s, %s, %s, %s, %s)
            ''', (admin['id'], form_assignee, form_count, form_start, form_end, form_type))
            
            # Step 7: Commit the change
            print("\n7️⃣ Step 7: Commit transaction...")
            safe_commit(conn, context="test_new_target")
            print(f"   ✅ Committed successfully")
            
            # Step 8: Verify insertion
            print("\n8️⃣ Step 8: Verify target was created...")
            execute_query(cursor, 'SELECT id, target_count FROM lead_targets ORDER BY id DESC LIMIT 1')
            new_target = cursor.fetchone()
            print(f"   ✅ Created target ID: {new_target['id']}, count: {new_target['target_count']}")
            
            # Step 9: Cleanup
            print("\n9️⃣ Step 9: Cleanup test data...")
            execute_query(cursor, 'DELETE FROM lead_targets WHERE id = %s', (new_target['id'],))
            conn.commit()
            print(f"   ✅ Deleted test target")
            
            conn.close()
            return True
            
        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()
            conn.close()
            return False

if __name__ == '__main__':
    success = test_new_target_workflow()
    print("\n" + "=" * 70)
    if success:
        print("✅ NEW TARGET WORKFLOW TEST PASSED!")
        print("=" * 70)
    else:
        print("❌ NEW TARGET WORKFLOW TEST FAILED")
        print("=" * 70)
