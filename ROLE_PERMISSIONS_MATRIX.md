# 🔐 Role Permissions Matrix

## Quick Reference Guide

| Feature | Admin | EM Team Leader | Email Marketer | BD Sales |
|---------|-------|----------------|----------------|----------|
| **Dashboard Access** | All Leads (15) | Assigned Leads (8) | Submitted Leads (4) | Assigned Leads (1) |
| **View All Leads** | ✅ Yes | ❌ No | ❌ No | ❌ No |
| **Submit Leads** | ✅ Yes | ✅ Yes | ✅ Yes | ❌ No |
| **Review Leads** | ✅ Yes | ✅ Yes | ❌ No | ❌ No |
| **Resubmit Rejected** | ❌ No | ❌ No | ✅ Yes | ❌ No |
| **Assign to BD Sales** | ✅ Yes | ✅ Yes | ❌ No | ❌ No |
| **Sales Pipeline** | ✅ View | ✅ View | ❌ No | ✅ Manage |
| **Drag-Drop Stages** | ✅ Yes | ❌ No | ❌ No | ✅ Yes |
| **Manage Activities** | ✅ View All | ✅ View All | ❌ Limited | ✅ Full |
| **Social Profiles** | ✅ View All | ✅ View All | ❌ Limited | ✅ Manage |
| **User Management** | ✅ Full CRUD | ✅ View Only | ❌ No | ❌ No |
| **Service Management** | ✅ Full CRUD | ✅ Full CRUD | ✅ View Only | ✅ View Only |
| **Target Management** | ✅ Create & Assign | ✅ Receive & Assign | ✅ View Only | ❌ No |
| **Pipeline Stages** | ✅ Full CRUD | ❌ No | ❌ No | ❌ No |
| **Analytics** | ✅ Yes | ✅ Yes | ❌ No | ❌ No |
| **Notifications** | ✅ Yes (0) | ✅ Yes (4) | ✅ Yes (4) | ✅ Yes (2) |

---

## Feature Access Summary

### 🔴 Admin Only
- Pipeline Stage Management (Create, Edit, Delete, Reorder)
- User Creation & Deletion
- System-wide Statistics
- Full Database Access

### 🟡 Admin + Manager
- Lead Review & Approval
- Service Management (CRUD)
- Analytics Dashboard
- Team Management
- Target Creation

### 🟢 Admin + Manager + Marketer
- Lead Submission
- View Services
- Receive Notifications

### 🔵 BD Sales Only
- Sales Pipeline Drag-and-Drop
- Activity Management (Full CRUD)
- Social Profile Management
- Deal Amount Tracking

---

## Typical User Journey

### Email Marketer Journey:
```
1. Login → Dashboard (See my 4 submitted leads)
2. Click "Submit Lead" → Fill form → Submit
3. Check notifications → Lead accepted by manager
4. View targets → 60% complete (3/5 leads)
5. Check rejected lead → Add notes → Resubmit
```

### EM Team Leader Journey:
```
1. Login → Dashboard (See 8 assigned leads)
2. Review 3 pending leads → Accept 2, Reject 1
3. Click "Assign to BD" on accepted leads
4. Go to Targets → Assign monthly target to marketer
5. Check analytics → Team performance dashboard
```

### BD Sales Journey:
```
1. Login → Dashboard (See 1 assigned lead)
2. Go to Sales Pipeline → Kanban view with 7 stages
3. Drag lead from "New Lead" to "Contacted"
4. Click lead → Add activity (Call log)
5. Add social profile (LinkedIn URL)
6. Update deal amount → $25,000
7. Create follow-up task with due date
```

### Admin Journey:
```
1. Login → Dashboard (See all 15 leads)
2. Go to Users → Add new BD Sales user
3. Go to Pipeline Stages → Create new stage "Demo Scheduled"
4. Go to Services → Add new service "Content Marketing"
5. Go to Targets → Assign monthly target to managers
6. View system-wide analytics
```

---

## Permission Logic

### Dashboard Filtering:
```python
# Admin: No filter
SELECT * FROM leads

# Manager: Filter by assigned manager
SELECT * FROM leads WHERE current_manager_id = user_id

# Marketer: Filter by submitter
SELECT * FROM leads WHERE submitted_by_user_id = user_id

# BD Sales: Filter by BD assignment
SELECT * FROM leads WHERE assigned_bd_id = user_id
```

### Navigation Menu (Sidebar):
```
Admin Sees:
├── Lead Center
├── Sales Pipeline
├── Analytics
├── Services
├── Users
├── Targets
├── Pipeline Stages (Admin Only)
└── Notifications

Manager Sees:
├── Lead Center
├── Sales Pipeline
├── Analytics
├── Services
├── Users (View)
├── Targets
└── Notifications

Marketer Sees:
├── Lead Center
├── Submit Lead
├── Targets (View)
└── Notifications

BD Sales Sees:
├── Lead Center
├── Sales Pipeline (with drag-drop)
└── Notifications
```

---

## Data Ownership

### Who Can Edit What:

**Leads:**
- Admin: All leads
- Manager: Assigned leads (can edit, accept, reject, re-reject)
- Marketer: Own submitted leads (can resubmit if rejected)
- BD Sales: Assigned leads (stage, activities, social profiles, deal amount)

**Activities:**
- Admin: View all
- Manager: View all
- Marketer: Limited view
- BD Sales: Full CRUD on own activities

**Social Profiles:**
- Admin: View all
- Manager: View all
- Marketer: Limited view
- BD Sales: Full CRUD on assigned leads

**Targets:**
- Admin: Create for managers
- Manager: Create for marketers, view own
- Marketer: View own
- BD Sales: None

**Pipeline Stages:**
- Admin: Full CRUD
- All others: Read-only

---

## Security & Permissions

### Authentication:
- All routes protected by `@login_required`
- Role-based access control via decorators
- Session management via Flask-Login
- Secure password hashing (Werkzeug)

### Authorization Checks:
```python
# Example permission checks in code

@app.route('/stages')
@login_required
def manage_stages():
    if current_user.role != 'admin':
        abort(403)  # Forbidden
    # Admin-only feature
    
@app.route('/pipeline')
@login_required
def pipeline():
    if current_user.role not in ['admin', 'manager', 'bd_sales']:
        abort(403)  # Only these roles can access
    # Filter data by role...
```

### Data Isolation:
- Marketers only see their own submitted leads
- BD Sales only see their assigned leads
- Managers only see leads they're managing
- Admin sees everything (audit purposes)

---

## Test Credentials Summary

| Role | Email | Password | Leads | Features |
|------|-------|----------|-------|----------|
| Admin | admin@example.com | admin123 | 15 (all) | Full Access |
| Manager | sarah@elbroz.com | manager123 | 8 (assigned) | Lead Review, BD Assign |
| Manager | michael@elbroz.com | manager123 | 8 (assigned) | Lead Review, BD Assign |
| Marketer | emma@elbroz.com | marketer123 | 4 (submitted) | Submit & Resubmit |
| Marketer | david@elbroz.com | marketer123 | 4 (submitted) | Submit & Resubmit |
| Marketer | lisa@elbroz.com | marketer123 | 4 (submitted) | Submit & Resubmit |
| BD Sales | alex@elbroz.com | sales123 | 1 (assigned) | Pipeline & Activities |
| BD Sales | rachel@elbroz.com | sales123 | Variable | Pipeline & Activities |
| BD Sales | james@elbroz.com | sales123 | Variable | Pipeline & Activities |

---

**Last Updated:** November 9, 2025  
**Status:** ✅ All permissions verified and working
