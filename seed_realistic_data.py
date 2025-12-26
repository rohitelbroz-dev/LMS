from models import get_db
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta
import random

def clear_and_seed():
    """Clear existing data and seed comprehensive realistic data"""
    conn = get_db()
    cursor = conn.cursor()
    
    print("Clearing existing data...")
    # Clear in correct order to respect foreign keys
    tables = [
        'lead_activities', 'lead_social_profiles', 'lead_stage_history',
        'bd_assignment_history', 'lead_assignment_history', 'lead_assignments',
        'lead_notes', 'notifications', 'lead_targets', 'leads',
        'user_profiles', 'pipeline_stages', 'assignment_settings', 'users', 'services'
    ]
    for table in tables:
        cursor.execute(f'DELETE FROM {table}')
    
    conn.commit()
    print("✓ Cleared all tables")
    
    # 1. Create Users
    print("\nSeeding users...")
    users_data = [
        # Admin
        ('Admin User', 'admin@example.com', generate_password_hash('admin123'), 'admin'),
        
        # EM Team Leaders (Managers)
        ('Sarah Johnson', 'sarah@elbroz.com', generate_password_hash('manager123'), 'manager'),
        ('Michael Chen', 'michael@elbroz.com', generate_password_hash('manager123'), 'manager'),
        
        # Email Marketers
        ('Emma Wilson', 'emma@elbroz.com', generate_password_hash('marketer123'), 'marketer'),
        ('David Park', 'david@elbroz.com', generate_password_hash('marketer123'), 'marketer'),
        ('Lisa Martinez', 'lisa@elbroz.com', generate_password_hash('marketer123'), 'marketer'),
        
        # BD Sales
        ('Alex Thompson', 'alex@elbroz.com', generate_password_hash('sales123'), 'bd_sales'),
        ('Rachel Green', 'rachel@elbroz.com', generate_password_hash('sales123'), 'bd_sales'),
        ('James Rodriguez', 'james@elbroz.com', generate_password_hash('sales123'), 'bd_sales'),
    ]
    
    cursor.executemany('INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, ?)', users_data)
    conn.commit()
    print(f"✓ Created {len(users_data)} users")
    
    # Get user IDs
    cursor.execute('SELECT id, role FROM users')
    users = cursor.fetchall()
    admin_id = [u['id'] for u in users if u['role'] == 'admin'][0]
    manager_ids = [u['id'] for u in users if u['role'] == 'manager']
    marketer_ids = [u['id'] for u in users if u['role'] == 'marketer']
    bd_sales_ids = [u['id'] for u in users if u['role'] == 'bd_sales']
    
    # 2. Create User Profiles
    print("Seeding user profiles...")
    profiles = [
        (admin_id, 'System administrator managing the Elbroz Lead Dashboard'),
        (manager_ids[0], 'EM Team Leader focused on enterprise clients and team growth'),
        (manager_ids[1], 'Senior EM Team Leader specializing in technology sector leads'),
        (marketer_ids[0], 'Email marketing specialist with 5+ years experience in B2B'),
        (marketer_ids[1], 'Growth marketer focused on cold outreach campaigns'),
        (marketer_ids[2], 'Lead generation expert specializing in SaaS companies'),
        (bd_sales_ids[0], 'Senior BD Sales closing enterprise deals'),
        (bd_sales_ids[1], 'Mid-market specialist with strong negotiation skills'),
        (bd_sales_ids[2], 'Technical sales expert for development services'),
    ]
    
    cursor.executemany('INSERT INTO user_profiles (user_id, bio) VALUES (?, ?)', profiles)
    conn.commit()
    print(f"✓ Created {len(profiles)} user profiles")
    
    # 3. Create Services
    print("Seeding services...")
    services_data = [
        ('Design & Development',),
        ('SEO Services',),
        ('Social Media Marketing',),
        ('PPC Advertising',),
        ('Content Marketing',),
        ('Mobile App Development',),
        ('E-commerce Solutions',),
        ('Digital Strategy',)
    ]
    
    cursor.executemany('INSERT INTO services (name) VALUES (?)', services_data)
    conn.commit()
    
    cursor.execute('SELECT id FROM services')
    service_ids = [s['id'] for s in cursor.fetchall()]
    print(f"✓ Created {len(services_data)} services")
    
    # 4. Create Pipeline Stages
    print("Seeding pipeline stages...")
    stages_data = [
        ('New Lead', 1, '#6366f1', 0, admin_id),
        ('Contacted', 2, '#8b5cf6', 0, admin_id),
        ('Qualified', 3, '#06b6d4', 0, admin_id),
        ('Proposal Sent', 4, '#f59e0b', 0, admin_id),
        ('Negotiation', 5, '#f97316', 0, admin_id),
        ('Won', 6, '#10b981', 1, admin_id),
        ('Lost', 7, '#ef4444', 0, admin_id),
    ]
    
    cursor.executemany(
        'INSERT INTO pipeline_stages (name, position, color_code, is_default, created_by_id) VALUES (?, ?, ?, ?, ?)',
        stages_data
    )
    conn.commit()
    
    cursor.execute('SELECT id, name, position FROM pipeline_stages ORDER BY position')
    stages = cursor.fetchall()
    stage_map = {s['name']: s['id'] for s in stages}
    print(f"✓ Created {len(stages_data)} pipeline stages")
    
    # 5. Create Leads with various statuses
    print("Seeding leads...")
    companies = [
        ('TechVision Inc', 'John Smith', 'john@techvision.com', '+1-555-0101', 'www.techvision.com', 'United States', 'CA', 'San Francisco'),
        ('Global Solutions Ltd', 'Sarah Brown', 'sarah@globalsol.com', '+44-20-1234-5678', 'www.globalsolutions.co.uk', 'United Kingdom', 'England', 'London'),
        ('InnovateCorp', 'Michael Lee', 'michael@innovatecorp.com', '+1-555-0202', 'www.innovatecorp.com', 'United States', 'NY', 'New York'),
        ('Digital Dynamics', 'Emily White', 'emily@digitaldyn.com', '+1-555-0303', 'www.digitaldynamics.com', 'United States', 'TX', 'Austin'),
        ('Smart Systems GmbH', 'Hans Mueller', 'hans@smartsys.de', '+49-30-12345678', 'www.smartsystems.de', 'Germany', 'Berlin', 'Berlin'),
        ('NextGen Software', 'Lisa Chen', 'lisa@nextgen.com', '+1-555-0404', 'www.nextgensoftware.com', 'United States', 'WA', 'Seattle'),
        ('CloudFirst Solutions', 'David Kumar', 'david@cloudfirst.com', '+91-11-2345-6789', 'www.cloudfirst.in', 'India', 'Delhi', 'New Delhi'),
        ('DataFlow Inc', 'Rachel Adams', 'rachel@dataflow.com', '+1-555-0505', 'www.dataflow.com', 'United States', 'MA', 'Boston'),
        ('MarketPro Agency', 'Tom Wilson', 'tom@marketpro.com', '+1-555-0606', 'www.marketpro.com', 'United States', 'FL', 'Miami'),
        ('WebWorks Studios', 'Anna Martinez', 'anna@webworks.com', '+34-91-123-4567', 'www.webworks.es', 'Spain', 'Madrid', 'Madrid'),
        ('FinTech Innovations', 'Robert Taylor', 'robert@fintech-inn.com', '+1-555-0707', 'www.fintechinnovations.com', 'United States', 'IL', 'Chicago'),
        ('EcoGreen Solutions', 'Jennifer Lopez', 'jennifer@ecogreen.com', '+1-555-0808', 'www.ecogreensolutions.com', 'United States', 'CO', 'Denver'),
        ('MobileFirst Apps', 'Kevin Brown', 'kevin@mobilefirst.com', '+1-555-0909', 'www.mobilefirstapps.com', 'United States', 'GA', 'Atlanta'),
        ('SaaS Ventures', 'Michelle Zhang', 'michelle@saasventures.com', '+1-555-1010', 'www.saasventures.com', 'United States', 'OR', 'Portland'),
        ('Enterprise Plus', 'Chris Johnson', 'chris@enterpriseplus.com', '+1-555-1111', 'www.enterpriseplus.com', 'United States', 'NC', 'Charlotte'),
    ]
    
    now = datetime.now()
    leads_created = []
    
    # Get service names for CSV
    cursor.execute('SELECT id, name FROM services')
    services_lookup = {s['id']: s['name'] for s in cursor.fetchall()}
    
    for idx, (company, contact, email, phone, domain, country, state, city) in enumerate(companies):
        # Pick 1-3 services
        num_services = random.randint(1, 3)
        selected_services = random.sample(list(services_lookup.values()), num_services)
        services_csv = ', '.join(selected_services)
        
        submitter_id = random.choice(marketer_ids)
        
        # Vary statuses - some pending, some accepted, some rejected
        if idx < 5:
            status = 'Accepted'
            manager_id = random.choice(manager_ids)
            bd_id = random.choice(bd_sales_ids)
            stage_id = random.choice([stage_map['New Lead'], stage_map['Contacted'], stage_map['Qualified'], stage_map['Proposal Sent']])
            deal_amount = random.choice([5000, 10000, 15000, 25000, 50000, None])
        elif idx < 8:
            status = 'Pending'
            manager_id = random.choice(manager_ids)
            bd_id = None
            stage_id = None
            deal_amount = None
        elif idx < 10:
            status = 'Rejected'
            manager_id = random.choice(manager_ids)
            bd_id = None
            stage_id = None
            deal_amount = None
        elif idx < 12:
            status = 'Resubmitted'
            manager_id = random.choice(manager_ids)
            bd_id = None
            stage_id = None
            deal_amount = None
        else:
            status = 'Accepted'
            manager_id = random.choice(manager_ids)
            bd_id = random.choice(bd_sales_ids)
            stage_id = random.choice([stage_map['Negotiation'], stage_map['Won'], stage_map['Lost']])
            if stage_id == stage_map['Won']:
                deal_amount = random.choice([30000, 50000, 75000, 100000])
            else:
                deal_amount = random.choice([20000, 35000, None])
        
        created_at = now - timedelta(days=random.randint(1, 30))
        assigned_at = created_at + timedelta(hours=2)
        
        cursor.execute('''
            INSERT INTO leads (
                company, full_name, email, phone, domain, country, state, city,
                services_csv, status, submitted_by_user_id, current_manager_id,
                assigned_bd_id, current_stage_id, deal_amount, created_at, assigned_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (company, contact, email, phone, domain, country, state, city,
              services_csv, status, submitter_id, manager_id, bd_id, stage_id, deal_amount,
              created_at.strftime('%Y-%m-%d %H:%M:%S'),
              assigned_at.strftime('%Y-%m-%d %H:%M:%S')))
        
        lead_id = cursor.lastrowid
        leads_created.append({
            'id': lead_id,
            'company': company,
            'status': status,
            'manager_id': manager_id,
            'bd_id': bd_id,
            'stage_id': stage_id,
            'submitter_id': submitter_id
        })
    
    conn.commit()
    print(f"✓ Created {len(companies)} leads")
    
    # 6. Create Lead Assignments for accepted/pending/resubmitted leads
    print("Seeding lead assignments...")
    assignments = 0
    for lead in leads_created:
        if lead['status'] in ['Pending', 'Accepted', 'Resubmitted']:
            deadline_hours = 15 if lead['status'] == 'Pending' else 4
            deadline_at = now + timedelta(hours=deadline_hours)
            
            # For accepted leads, set acted_at and status to 'acted'
            if lead['status'] == 'Accepted':
                acted_at = now - timedelta(hours=random.randint(1, 24))
                assignment_status = 'acted'
            else:
                acted_at = None
                assignment_status = 'pending'
            
            cursor.execute('''
                INSERT INTO lead_assignments (
                    lead_id, manager_id, assigned_at, deadline_at, acted_at, status
                ) VALUES (?, ?, ?, ?, ?, ?)
            ''', (lead['id'], lead['manager_id'], now.strftime('%Y-%m-%d %H:%M:%S'),
                  deadline_at.strftime('%Y-%m-%d %H:%M:%S'),
                  acted_at.strftime('%Y-%m-%d %H:%M:%S') if acted_at else None,
                  assignment_status))
            assignments += 1
    
    conn.commit()
    print(f"✓ Created {assignments} lead assignments")
    
    # 7. Create Lead Notes for rejected/resubmitted leads
    print("Seeding lead notes...")
    rejection_reasons = [
        "Budget constraints - client not ready to invest at this time",
        "Already working with another agency",
        "Looking for different services than what we offer",
        "Timeline doesn't match - need immediate start",
        "Company size too small for our services"
    ]
    
    notes_created = 0
    for lead in leads_created:
        if lead['status'] in ['Rejected', 'Resubmitted']:
            reason = random.choice(rejection_reasons)
            note_time = now - timedelta(days=random.randint(1, 10))
            
            cursor.execute('''
                INSERT INTO lead_notes (lead_id, message, note_type, author_user_id, created_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (lead['id'], reason, 'rejection', lead['manager_id'],
                  note_time.strftime('%Y-%m-%d %H:%M:%S')))
            notes_created += 1
            
            if lead['status'] == 'Resubmitted':
                resubmit_note = "Updated proposal with revised pricing and timeline"
                resubmit_time = note_time + timedelta(days=3)
                cursor.execute('''
                    INSERT INTO lead_notes (lead_id, message, note_type, author_user_id, created_at)
                    VALUES (?, ?, ?, ?, ?)
                ''', (lead['id'], resubmit_note, 'resubmission', lead['submitter_id'],
                      resubmit_time.strftime('%Y-%m-%d %H:%M:%S')))
                notes_created += 1
    
    conn.commit()
    print(f"✓ Created {notes_created} lead notes")
    
    # 8. Create Social Profiles for accepted leads
    print("Seeding social profiles...")
    social_profiles = 0
    social_platforms = ['linkedin', 'twitter', 'facebook', 'website']
    
    for lead in leads_created:
        if lead['status'] == 'Accepted' and random.random() > 0.3:
            num_profiles = random.randint(1, 3)
            platforms = random.sample(social_platforms, num_profiles)
            
            for platform in platforms:
                if platform == 'linkedin':
                    url = f"https://linkedin.com/company/{lead['company'].lower().replace(' ', '-')}"
                elif platform == 'twitter':
                    url = f"https://twitter.com/{lead['company'].lower().replace(' ', '')}"
                elif platform == 'facebook':
                    url = f"https://facebook.com/{lead['company'].lower().replace(' ', '')}"
                else:
                    url = f"https://www.{lead['company'].lower().replace(' ', '')}.com"
                
                cursor.execute('''
                    INSERT INTO lead_social_profiles (lead_id, platform, url, added_by_id)
                    VALUES (?, ?, ?, ?)
                ''', (lead['id'], platform, url, lead['bd_id']))
                social_profiles += 1
    
    conn.commit()
    print(f"✓ Created {social_profiles} social profiles")
    
    # 9. Create Activities for accepted leads with BD assignment
    print("Seeding activities...")
    activities_created = 0
    
    activity_templates = {
        'note': [
            "Client expressed interest in expanding to mobile platform",
            "Discussed pricing models and payment terms",
            "Shared case studies from similar industry clients",
            "Client requested additional references",
            "Followed up on technical requirements discussion"
        ],
        'task': [
            "Prepare detailed proposal with timeline",
            "Schedule demo call with technical team",
            "Send contract draft for review",
            "Follow up on pricing discussion",
            "Compile competitor analysis"
        ],
        'follow_up': [
            "Follow up on proposal sent last week",
            "Check if technical questions were answered",
            "Confirm meeting scheduled for next week",
            "Touch base on contract review status",
            "Follow up on decision timeline"
        ],
        'call_log': [
            "Initial discovery call - 45 mins",
            "Technical requirements discussion - 30 mins",
            "Pricing negotiation call - 60 mins",
            "Contract review meeting - 40 mins",
            "Final walkthrough call - 50 mins"
        ],
        'email_log': [
            "Sent proposal with detailed breakdown",
            "Shared case study portfolio",
            "Forwarded contract for legal review",
            "Answered technical questions via email",
            "Sent meeting recap and next steps"
        ]
    }
    
    for lead in leads_created:
        if lead['status'] == 'Accepted' and lead['bd_id']:
            # Create 3-7 activities per accepted lead
            num_activities = random.randint(3, 7)
            
            for i in range(num_activities):
                activity_type = random.choice(['note', 'task', 'follow_up', 'call_log', 'email_log'])
                title = random.choice(activity_templates[activity_type])
                
                # Some activities have descriptions
                description = None
                if random.random() > 0.5:
                    description = f"Additional details about: {title[:30]}..."
                
                activity_date = now - timedelta(days=random.randint(1, 20))
                
                # Some tasks and follow-ups have due dates
                due_at = None
                completed_at = None
                
                if activity_type in ['task', 'follow_up']:
                    if random.random() > 0.4:  # 60% have due dates
                        days_ahead = random.randint(-5, 10)  # Some overdue, some upcoming
                        due_at = (now + timedelta(days=days_ahead)).strftime('%Y-%m-%d %H:%M:%S')
                        # Completed if overdue or randomly completed
                        if days_ahead < 0 or random.random() > 0.5:
                            completed_at = (now - timedelta(days=random.randint(1, 5))).strftime('%Y-%m-%d %H:%M:%S')
                
                cursor.execute('''
                    INSERT INTO lead_activities (
                        lead_id, activity_type, title, description, actor_id,
                        due_at, completed_at, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (lead['id'], activity_type, title, description, lead['bd_id'],
                      due_at, completed_at, activity_date.strftime('%Y-%m-%d %H:%M:%S')))
                
                activities_created += 1
    
    conn.commit()
    print(f"✓ Created {activities_created} activities")
    
    # 10. Create Lead Stage History
    print("Seeding stage history...")
    history_entries = 0
    
    for lead in leads_created:
        if lead['stage_id']:
            # Create history of stage progressions
            current_stage_position = next(s['position'] for s in stages if s['id'] == lead['stage_id'])
            
            for pos in range(1, current_stage_position + 1):
                stage = next(s for s in stages if s['position'] == pos)
                moved_at = now - timedelta(days=(current_stage_position - pos) * 3)
                
                cursor.execute('''
                    INSERT INTO lead_stage_history (
                        lead_id, from_stage_id, to_stage_id, changed_by_id, changed_at
                    ) VALUES (?, ?, ?, ?, ?)
                ''', (lead['id'], None if pos == 1 else stages[pos-2]['id'],
                      stage['id'], lead['bd_id'], moved_at.strftime('%Y-%m-%d %H:%M:%S')))
                
                history_entries += 1
    
    conn.commit()
    print(f"✓ Created {history_entries} stage history entries")
    
    # 11. Create Targets
    print("Seeding targets...")
    
    # Admin assigns targets to managers
    target_month_start = datetime(now.year, now.month, 1)
    target_month_end = datetime(now.year, now.month + 1, 1) - timedelta(days=1)
    
    for manager_id in manager_ids:
        cursor.execute('''
            INSERT INTO lead_targets (
                assigned_by_id, assignee_id, target_type, target_count,
                period_start, period_end
            ) VALUES (?, ?, ?, ?, ?, ?)
        ''', (admin_id, manager_id, 'monthly', random.choice([10, 15, 20]),
              target_month_start.strftime('%Y-%m-%d'),
              target_month_end.strftime('%Y-%m-%d')))
    
    # Managers assign targets to marketers
    for marketer_id in marketer_ids:
        manager = random.choice(manager_ids)
        cursor.execute('''
            INSERT INTO lead_targets (
                assigned_by_id, assignee_id, target_type, target_count,
                period_start, period_end
            ) VALUES (?, ?, ?, ?, ?, ?)
        ''', (manager, marketer_id, 'monthly', random.choice([5, 8, 12]),
              target_month_start.strftime('%Y-%m-%d'),
              target_month_end.strftime('%Y-%m-%d')))
    
    conn.commit()
    print(f"✓ Created {len(manager_ids) + len(marketer_ids)} targets")
    
    # 12. Create Notifications
    print("Seeding notifications...")
    notification_messages = [
        "New lead assigned to you",
        "Lead deadline approaching in 2 hours",
        "Lead successfully accepted by manager",
        "Task due tomorrow",
        "Follow-up overdue",
    ]
    
    notifications_created = 0
    
    # Get some leads for notifications
    cursor.execute('SELECT id FROM leads LIMIT 5')
    sample_lead_ids = [r['id'] for r in cursor.fetchall()]
    
    for user_id in marketer_ids + manager_ids + bd_sales_ids:
        num_notifications = random.randint(2, 4)
        for i in range(num_notifications):
            msg = random.choice(notification_messages)
            lead_id = random.choice(sample_lead_ids)
            notif_time = now - timedelta(hours=random.randint(1, 72))
            is_read = random.random() > 0.4
            
            cursor.execute('''
                INSERT INTO notifications (
                    user_id, lead_id, message, is_read, created_at
                ) VALUES (?, ?, ?, ?, ?)
            ''', (user_id, lead_id, msg, is_read,
                  notif_time.strftime('%Y-%m-%d %H:%M:%S')))
            
            notifications_created += 1
    
    conn.commit()
    print(f"✓ Created {notifications_created} notifications")
    
    # 13. Set up assignment settings for round-robin
    cursor.execute('''
        INSERT INTO assignment_settings (id, last_assigned_manager_id, last_assigned_bd_id)
        VALUES (1, ?, ?)
    ''', (manager_ids[0], bd_sales_ids[0]))
    conn.commit()
    print("✓ Initialized assignment settings")
    
    conn.close()
    
    print("\n" + "="*60)
    print("🎉 DATABASE SEEDED SUCCESSFULLY!")
    print("="*60)
    print("\nDemo User Credentials:")
    print("-" * 60)
    print("Admin:           admin@example.com / admin123")
    print("\nEM Team Leaders (Managers):")
    print("  Sarah Johnson: sarah@elbroz.com / manager123")
    print("  Michael Chen:  michael@elbroz.com / manager123")
    print("\nEmail Marketers:")
    print("  Emma Wilson:   emma@elbroz.com / marketer123")
    print("  David Park:    david@elbroz.com / marketer123")
    print("  Lisa Martinez: lisa@elbroz.com / marketer123")
    print("\nBD Sales:")
    print("  Alex Thompson:   alex@elbroz.com / sales123")
    print("  Rachel Green:    rachel@elbroz.com / sales123")
    print("  James Rodriguez: james@elbroz.com / sales123")
    print("\n" + "="*60)
    print(f"Summary: {len(users_data)} users, {len(companies)} leads,")
    print(f"         {activities_created} activities, {social_profiles} social profiles")
    print("="*60)

if __name__ == '__main__':
    clear_and_seed()
