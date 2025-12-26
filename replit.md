# Elbroz Cold Email Lead Dashboard

## Overview
The Elbroz Cold Email Lead Dashboard is a Flask + PostgreSQL role-based lead management system designed for cold email campaigns. It facilitates lead submission, review, distribution, and tracking through a sales pipeline. The system supports four primary user roles: Admin, EM Team Leader (Manager), Email Marketer, and BD Sales, each with tailored functionalities. The application is branded with Elbroz's signature pink-purple-blue gradient theme and features a modern vertical sidebar design. Its purpose is to streamline lead workflows, from initial submission by marketers to deal closure by BD Sales, with robust user and service management capabilities.

## Production Status
**Production-Ready** - The application has been prepared for live deployment (November 12, 2025):
- Demo accounts section removed from login page for security
- Database cleaned: All test/demo lead data purged (2 leads, 16 related records total)
- Assignment round-robin state reset for fresh production start
- Test lead attachment files cleaned from uploads directory
- System configuration preserved: 4 user accounts, 8 services, 7 pipeline stages, 9 user profiles intact
- Critical bug fixes implemented: Fixed FOREIGN KEY constraint errors in user deletion (15+ FK relationships), fixed APScheduler errors for reassignment and reminder checks
- User deletion system now production-ready: Comprehensive 6-phase deletion strategy handling all foreign key dependencies (lead_social_profiles, lead_edit_changes, lead_stage_history, lead_assignment_history, lead_activities, notifications, etc.) with both replacement and non-replacement scenarios
- Application verified running without errors after cleanup (no scheduler errors, no constraint violations)

## User Preferences
None specified yet.

## System Architecture
The application is built with Flask 3.0.0, utilizing PostgreSQL (Neon-backed via Replit integration) as its database. Frontend development leverages Bootstrap 5, Jinja2 templates, and custom CSS for Elbroz branding, including a vertical sidebar navigation. Real-time features are powered by Flask-SocketIO with WebSockets, enabling instant notifications and activity updates. Background tasks, such as lead reassignment and activity reminders, are managed by APScheduler.

### PostgreSQL Migration (November 13-14, 2025)
The application was successfully migrated from SQLite to PostgreSQL for production deployment:
- **Database**: Replit-managed PostgreSQL (Neon-backed) with automatic connection management
- **Schema Migration**: All 17 tables migrated using IDENTITY columns instead of AUTOINCREMENT
- **Data Migration**: 62 rows successfully migrated across all tables with proper FK dependency handling
- **Code Updates**: 406 SQL placeholder conversions (? → %s), psycopg2 RealDictCursor implementation, comprehensive error handling
- **Production Ready**: Database cleaned of test data, preserving 6 user accounts, 8 services, 7 pipeline stages
- **Migration Scripts**: `create_postgres_schema.py` and `migrate_data_to_postgres.py` for reusable migrations

#### PostgreSQL Compatibility Fixes (November 14, 2025)
Additional SQLite-specific functions replaced with PostgreSQL equivalents to fix runtime errors:
- **datetime() functions** (3 instances): `datetime('now', '+X hours')` → `NOW() + INTERVAL 'X hours'`; `datetime(column)` → column comparison with `NOW()`
- **date() functions** (2 instances): `date('now')` → `CURRENT_DATE`; `date('now', '-30 days')` → `CURRENT_DATE - INTERVAL '30 days'`
- **cursor.lastrowid** (3 instances): Replaced with PostgreSQL `RETURNING id` clause for lead submission, activity creation, and assignment tracking
- **f-string SQL formatting** (4 instances): Fixed `f'...IN ({",".join("%s"...)})'` → `placeholders = ','.join(['%s']...); f'...IN ({placeholders})'` in view_lead, export_leads, and edit_lead routes
- **Template datetime slicing** (1 instance): Fixed `lead.assigned_to_bd_at[:16]` → `format_indian_datetime(lead.assigned_to_bd_at, 'datetime')` in lead_detail.html (PostgreSQL returns datetime objects, not strings)
- **Impact**: Fixed lead submission errors, APScheduler reminder check failures, analytics queries, CSV export, lead detail viewing, and lead editing
- **Verification**: All scheduled jobs run without errors; all routes functional; comprehensive template datetime formatting verified

### UI/UX Decisions
- **Elbroz Branding**: A consistent pink-purple-blue gradient theme is applied across all pages, including gradient text, badges, and interactive elements.
- **Navigation**: A modern vertical sidebar provides primary navigation, responsive for mobile.
- **User Profiles**: Users can upload avatars and manage bios, displayed prominently in the sidebar. Default avatar placeholder provided for users without custom avatars.
- **Dashboard**: Features date filters (Current Month, Last Month, This Week, All Time) and a dismissible top bar for active target progress.
- **Sales Pipeline**: Modern HubSpot-style interactive Kanban board with premium scrollable layout showing 3-4 stages at a time with optimal readability (280-340px responsive columns). Features include: smooth horizontal scrolling enabled on ALL screen sizes (mobile to 4K), smart navigation arrows that reveal hidden stages, prominent bottom scrollbar with gradient design, pipeline stage statistics cards, premium card design with deal badges and assignee avatars, text truncation with tooltips, smooth drag-and-drop animations, mouse drag scrolling support, touch-friendly mobile scrolling, and gradient-based visual feedback. Horizontal scroll explicitly enabled across all breakpoints with overflow-x: auto !important. Multiple scroll methods available: arrow buttons, mouse drag, bottom scrollbar, mouse wheel, or keyboard.
- **Lead Detail Page**: Professional HubSpot-style layout with Quick Actions positioned in the main content area (left column) displayed as horizontal 3-button layout with solid colors (Email: blue #3b82f6, WhatsApp: green #10b981, Call: cyan #06b6d4). Activity management features 3 separate scrollable boxes (Notes, Tasks, Reminders) each with 400px height, dedicated Add buttons, and color-coded headers (blue for Notes, orange for Tasks, green for Reminders). All datetime badges (due dates, reminders) feature comprehensive text overflow protection with multi-line wrapping support (white-space: normal, word-break: break-word, overflow-wrap: anywhere, max-width: 100%) ensuring full datetime visibility without truncation. Right sidebar features a sticky Unified Activity Timeline that displays all timeline events (activities, status changes, assignments, deal changes) with professional icons, badges, and 3-line text truncation. Timeline becomes fixed when scrolling with independent scroll behavior and auto-disables sticky positioning on mobile (<992px).
- **Social Media Icons**: Official brand colors applied throughout - LinkedIn (#0077B5), Twitter (#1DA1F2), Facebook (#1877F2), Website (#6B7280) with 1.5rem font size for enhanced visibility.
- **Notifications**: Real-time toast notifications with optional audio alerts (800Hz beep) for critical updates, enhanced with gradient backgrounds and slide-in animations.

### Technical Implementations
- **Role-Based Access Control**: Granular permissions are enforced on all routes.
- **Lead Workflow**: Supports pending, accepted, rejected, resubmitted, and re-rejected states with detailed timelines.
- **Automated Lead Distribution**: Marketer-submitted leads are distributed to managers using a round-robin algorithm. BD Sales assignments also support round-robin.
- **Time-Based Reassignment**: An APScheduler job reassigns overdue leads based on defined deadlines (15hr initial, 4hr subsequent).
- **Monthly Targets System**: Comprehensive CRUD for targets, with progress tracking (Admin assigns to Managers, Managers assign to Marketers) and overlap prevention.
- **Activity Tracking**: A robust system for logging notes, tasks, follow-ups, call logs, and email logs, complete with due dates and automated reminders. All activities support IST timezone for datetime fields with automatic conversion to UTC for storage. Tasks and reminders feature interactive checkboxes for mark as done/undone functionality with smooth fade animations and real-time Socket.IO updates.
- **File Handling**: Secure file uploads (avatars, lead attachments) with UUID naming and size limits. Uses Replit Object Storage in production for file persistence across deployments (local filesystem in development).
- **Database Schema**: Includes tables for users, services, leads, lead_notes, notifications, lead_assignments, assignment_history, bd_assignment_history, assignment_settings, pipeline_stages, lead_stage_history, lead_activities, lead_social_profiles, lead_targets, and user_profiles.
- **API Endpoints**: PATCH endpoint for updating lead stages via drag-and-drop with Socket.IO broadcasts.

### Feature Specifications
- **Lead Center**: Centralized dashboard for lead management with role-based filtering, deadline visibility, and export options.
- **Profile Management**: Users can update their avatar and bio.
- **User Management**: Admin-only page displaying all users in a table with profile pictures (40x40px circular avatars with gradient fallback showing user initials), name, email, role badges, status (Protected/Active), creation timestamps, and action buttons. Full profile editing capability allows admins to modify any user's name, email, role, password, avatar, and bio through a comprehensive edit form with file upload validation and multipart form handling. **Protected User Deletion System**: At least one user per role is marked as non-deletable (protected) to ensure system continuity. Protected users display a shield badge and have disabled delete buttons. For unprotected users, deletion requires admin confirmation via dedicated confirmation page showing data summary (leads, activities, assignments, targets). Admins can optionally transfer all user data to a replacement user from the same role before deletion, or permanently delete all data. System prevents deletion of: current logged-in user, protected users, and the last remaining unprotected user in any role. All deletions are transactional with automatic rollback on error.
- **Advanced Export**: Modal dialog for CSV export with extensive filtering options (status, service, submitter, date range).
- **Manager Tooling**: Managers can edit any lead, re-reject accepted leads, and submit leads that auto-assign to peers.
- **BD Sales Workflow**: BD Sales users manage leads through a Kanban pipeline, track deal amounts, and log activities. Deal amount updates are automatically logged in the Unified Activity Timeline with full change tracking (old amount → new amount).
- **Pipeline Management**: Admins can CRUD pipeline stages, reorder them, customize colors, and protect stages from deletion.
- **Enhanced Lead Detail**: Professional HubSpot-style comprehensive view including industry badge, social profiles with official brand colors (LinkedIn, Twitter, Facebook, Website), deal amount, attachment preview (images and PDFs). Quick Actions displayed as horizontal 3-button layout in main content area with solid colors (Email: blue #3b82f6, WhatsApp: green #10b981, Call: cyan #06b6d4). Activity management via 3 separate 400px scrollable boxes (Notes, Tasks, Reminders) with dedicated Add buttons and automatic filtering by type. Tasks and Reminders feature interactive checkboxes (20x20px) for mark as done/undone functionality with "Done" badge, smooth fade animations (0.15s ease transition), and real-time updates via Socket.IO. Right sidebar features sticky Unified Activity Timeline showing all events (activities, status changes, assignments, deal changes) with icon badges and 3-line text truncation, fixed positioning on scroll. IST timezone support for all datetime fields with automatic IST→UTC conversion on input and UTC→IST conversion on display.
- **Reminder Notifications**: APScheduler triggers real-time, deduplicated notifications for upcoming activity deadlines.
- **Lead Submission Form**: Features industry dropdown (20 industries), service selection via checkboxes, and optional social profile URLs (LinkedIn, Twitter, Facebook, Website) with URL validation.
- **Lead Edit Form**: Full feature parity with submission form - includes industry dropdown, service checkboxes, and social profile management. Supports adding, updating, and removing social profiles. All changes are tracked in edit history with detailed change logs.

## External Dependencies
- **Flask-Login**: User session management.
- **Flask-WTF**: Form handling and validation.
- **Flask-SocketIO**: Real-time communication via WebSockets.
- **APScheduler**: Scheduling background jobs.
- **psycopg2**: PostgreSQL database adapter with RealDictCursor for dict-like row access.
- **Bootstrap 5**: Frontend framework for UI components.
- **SortableJS**: JavaScript library for drag-and-drop functionality in the Kanban board.
- **Font Awesome**: Icon library.
- **Werkzeug**: Secure file uploads.
- **Web Audio API**: For audio notifications.