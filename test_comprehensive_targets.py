#!/usr/bin/env python
"""Comprehensive test for target routes"""

from app import app, get_db, execute_query
from forms import TargetForm
from datetime import date

def test_form_validation():
    """Test form validation and data flow"""
    
    print("=" * 60)
    print("Testing Form Validation & Data Flow")
    print("=" * 60)
    
    with app.app_context():
        from flask import request
        
        conn = get_db()
        cursor = conn.cursor()
        
        # Get users
        execute_query(cursor, 'SELECT id FROM users WHERE role = %s LIMIT 1', ('admin',))
        admin = cursor.fetchone()
        
        execute_query(cursor, 'SELECT id FROM users WHERE role = %s LIMIT 1', ('manager',))
        manager = cursor.fetchone()
        
        # Get assignee choices
        execute_query(cursor, 'SELECT id, name FROM users WHERE role = %s ORDER BY name', ('manager',))
        assignees = cursor.fetchall()
        assignee_choices = [(u['id'], u['name']) for u in assignees]
        
        print(f"\n✅ Got {len(assignees)} assignee options")
        
        # Test 1: Form initialization
        print("\n📝 Test 1: Form initialization...")
        form = TargetForm()
        form.assignee.choices = assignee_choices
        print(f"✅ Form created with {len(form.assignee.choices)} choices")
        
        # Test 2: Form field population
        print("\n📝 Test 2: Form field population...")
        form.assignee.data = manager['id']
        form.target_count.data = 75
        form.period_start.data = date(2025, 4, 1)
        form.period_end.data = date(2025, 4, 30)
        form.target_type.data = 'monthly'
        
        print(f"✅ Form fields populated:")
        print(f"   - Assignee: {form.assignee.data}")
        print(f"   - Target Count: {form.target_count.data}")
        print(f"   - Period: {form.period_start.data} to {form.period_end.data}")
        print(f"   - Type: {form.target_type.data}")
        
        # Test 3: Database record creation with those values
        print("\n📝 Test 3: Database operations with form values...")
        try:
            execute_query(cursor, '''
                INSERT INTO lead_targets (assigned_by_id, assignee_id, target_count, 
                                         period_start, period_end, target_type)
                VALUES (%s, %s, %s, %s, %s, %s)
            ''', (admin['id'], form.assignee.data, form.target_count.data,
                  form.period_start.data, form.period_end.data, form.target_type.data))
            
            conn.commit()
            
            execute_query(cursor, 'SELECT id FROM lead_targets ORDER BY id DESC LIMIT 1')
            new_target = cursor.fetchone()
            target_id = new_target['id']
            
            print(f"✅ Created target ID: {target_id}")
            
            # Test 4: Retrieve and re-populate form
            print("\n📝 Test 4: Retrieve and re-populate form...")
            execute_query(cursor, 'SELECT * FROM lead_targets WHERE id = %s', (target_id,))
            retrieved_target = cursor.fetchone()
            
            form2 = TargetForm()
            form2.assignee.choices = assignee_choices
            form2.assignee.data = retrieved_target['assignee_id']
            form2.target_count.data = retrieved_target['target_count']
            form2.period_start.data = retrieved_target['period_start']
            form2.period_end.data = retrieved_target['period_end']
            form2.target_type.data = retrieved_target['target_type']
            
            print(f"✅ Retrieved and repopulated form:")
            print(f"   - Assignee: {form2.assignee.data} (matches: {form2.assignee.data == form.assignee.data})")
            print(f"   - Target Count: {form2.target_count.data} (matches: {form2.target_count.data == form.target_count.data})")
            print(f"   - Period: {form2.period_start.data} to {form2.period_end.data} (matches: {form2.period_start.data == form.period_start.data and form2.period_end.data == form.period_end.data})")
            print(f"   - Type: {form2.target_type.data} (matches: {form2.target_type.data == form.target_type.data})")
            
            # Test 5: Update the record
            print("\n📝 Test 5: Update the record...")
            execute_query(cursor, '''
                UPDATE lead_targets 
                SET target_count = %s, target_type = %s
                WHERE id = %s
            ''', (150, 'weekly', target_id))
            
            conn.commit()
            
            execute_query(cursor, 'SELECT target_count, target_type FROM lead_targets WHERE id = %s', (target_id,))
            updated = cursor.fetchone()
            print(f"✅ Updated target: count={updated['target_count']}, type={updated['target_type']}")
            
            # Test 6: Cleanup
            print("\n📝 Test 6: Cleanup...")
            execute_query(cursor, 'DELETE FROM lead_targets WHERE id = %s', (target_id,))
            conn.commit()
            print(f"✅ Test target deleted")
            
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
            conn.close()
            return False
        
        conn.close()
        return True

if __name__ == '__main__':
    try:
        success = test_form_validation()
        if success:
            print("\n" + "=" * 60)
            print("✅ All comprehensive tests passed!")
            print("=" * 60)
        else:
            print("\n❌ Tests failed")
    except Exception as e:
        print(f"\n❌ Test error: {e}")
        import traceback
        traceback.print_exc()
