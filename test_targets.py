
import unittest
import os
from app import app
from models import get_db, init_db, close_db, USE_POSTGRES
from werkzeug.security import generate_password_hash
from datetime import date
import warnings

class TestTargets(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        """Set up for all tests in this class."""
        # Suppress the ResourceWarning that may occur in test environments
        warnings.simplefilter('ignore', ResourceWarning)

    def setUp(self):
        """Set up for each test method."""
        self.app = app.test_client()
        self.app_context = app.app_context()
        self.app_context.push()

        with self.app_context:
            init_db() # Ensure tables exist
            conn = get_db()
            cursor = conn.cursor()
            
            # Create a test admin user
            password_hash = generate_password_hash('password')
            cursor.execute('''
                INSERT INTO users (name, email, password_hash, role)
                VALUES (?, ?, ?, ?)
            ''', ('testadmin', 'testadmin@example.com', password_hash, 'admin'))
            self.admin_id = cursor.lastrowid
            
            # Create a test marketer user to be assigned a target
            cursor.execute('''
                INSERT INTO users (name, email, password_hash, role)
                VALUES (?, ?, ?, ?)
            ''', ('testmarketer', 'testmarketer@example.com', password_hash, 'marketer'))
            self.marketer_id = cursor.lastrowid
            
            # Create a test target
            self.target_data = {
                'assigned_by_id': self.admin_id,
                'assignee_id': self.marketer_id,
                'target_count': 10,
                'period_start': date(2025, 1, 1),
                'period_end': date(2025, 1, 31),
                'target_type': 'monthly'
            }
            cursor.execute('''
                INSERT INTO lead_targets (assigned_by_id, assignee_id, target_count, period_start, period_end, target_type)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                self.target_data['assigned_by_id'],
                self.target_data['assignee_id'],
                self.target_data['target_count'],
                self.target_data['period_start'],
                self.target_data['period_end'],
                self.target_data['target_type']
            ))
            self.target_id = cursor.lastrowid
            conn.commit()

    def tearDown(self):
        """Tear down after each test method."""
        with self.app_context:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute('DELETE FROM lead_targets WHERE id = ?', (self.target_id,))
            cursor.execute('DELETE FROM users WHERE id = ?', (self.admin_id,))
            cursor.execute('DELETE FROM users WHERE id = ?', (self.marketer_id,))
            conn.commit()
        self.app_context.pop()

    def login(self, email, password):
        return self.app.post('/login', data=dict(
            email=email,
            password=password
        ), follow_redirects=True)

    def test_edit_target_get_request(self):
        """
        Tests if the edit target page loads correctly for a GET request.
        This will fail if the date handling logic is incorrect.
        """
        # Login as admin
        rv = self.login('testadmin@example.com', 'password')
        self.assertEqual(rv.status_code, 200)
        
        # Try to access the edit page
        response = self.app.get(f'/targets/{self.target_id}/edit')
        
        # Check if the page loads successfully
        self.assertEqual(response.status_code, 200)
        
        # Check for content that should be on the page
        self.assertIn(b'Edit Target', response.data)
        # The assignee name is dynamically loaded, so check for form values
        self.assertIn(b'value="2025-01-01"', response.data)
        self.assertIn(b'value="2025-01-31"', response.data)

if __name__ == '__main__':
    unittest.main()
