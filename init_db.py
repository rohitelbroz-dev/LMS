from models import init_db, get_db
from werkzeug.security import generate_password_hash

def seed_data():
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) as count FROM users')
    if cursor.fetchone()['count'] > 0:
        print("Database already seeded. Skipping...")
        conn.close()
        return
    
    users = [
        ('Admin User', 'admin@example.com', generate_password_hash('admin123'), 'admin'),
        ('Sales Manager', 'manager@example.com', generate_password_hash('manager123'), 'manager'),
        ('Email Marketer', 'marketer@example.com', generate_password_hash('marketer123'), 'marketer')
    ]
    
    cursor.executemany('INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, ?)', users)
    
    services = [
        ('Design & Development',),
        ('SEO',),
        ('SMO',),
        ('PPC',),
        ('Digital Marketing',),
        ('Mobile App',)
    ]
    
    cursor.executemany('INSERT INTO services (name) VALUES (?)', services)
    
    conn.commit()
    conn.close()
    print("Database seeded successfully!")
    print("\nDemo Users:")
    print("  Admin: admin@example.com / admin123")
    print("  Sales Manager: manager@example.com / manager123")
    print("  Email Marketer: marketer@example.com / marketer123")

if __name__ == '__main__':
    print("Initializing database...")
    init_db()
    seed_data()
