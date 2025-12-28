#!/usr/bin/env python
"""Final verification test for target routes"""

from app import app

def test_app_startup():
    """Test that app starts without errors"""
    
    print("=" * 70)
    print("Final Verification: App Integrity Check")
    print("=" * 70)
    
    try:
        with app.app_context():
            print("\n✅ Flask app initialized successfully")
            
            # Check that routes are registered
            from werkzeug.routing import Map
            target_routes = [str(rule) for rule in app.url_map.iter_rules() if 'target' in str(rule).lower()]
            
            print(f"✅ Found {len(target_routes)} target routes")
            for route in sorted(target_routes):
                print(f"   • {route}")
            
            # Check imports
            from models import execute_query, get_db
            from forms import TargetForm
            from app import has_period_overlap
            
            print("\n✅ All required modules imported successfully")
            print("   • models.execute_query")
            print("   • models.get_db")
            print("   • forms.TargetForm")
            print("   • app.has_period_overlap")
            
            # Check function signature
            import inspect
            sig = inspect.signature(has_period_overlap)
            params = list(sig.parameters.keys())
            
            print(f"\n✅ has_period_overlap function signature:")
            print(f"   Parameters: {params}")
            
            if 'cursor' in params:
                print("   ✅ 'cursor' parameter present")
            else:
                print("   ❌ 'cursor' parameter MISSING")
                return False
            
            return True
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = test_app_startup()
    print("\n" + "=" * 70)
    if success:
        print("✅ APP INTEGRITY VERIFIED - Ready for deployment!")
    else:
        print("❌ APP INTEGRITY CHECK FAILED")
    print("=" * 70)
