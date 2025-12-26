"""
Application-wide constants for Elbroz Lead Management System
"""

# Role constants (database values)
ROLE_ADMIN = 'admin'
ROLE_MANAGER = 'manager'  # EM Team Leader
ROLE_MARKETER = 'marketer'
ROLE_BD_SALES = 'bd_sales'

# Role display labels
ROLE_LABELS = {
    ROLE_ADMIN: 'Admin',
    ROLE_MANAGER: 'EM Team Leader',
    ROLE_MARKETER: 'Email Marketer',
    ROLE_BD_SALES: 'BD Sales'
}

# Role badge colors (Bootstrap classes)
ROLE_BADGE_COLORS = {
    ROLE_ADMIN: 'danger',
    ROLE_MANAGER: 'primary',
    ROLE_MARKETER: 'secondary',
    ROLE_BD_SALES: 'info'
}

# Pipeline stage colors
STAGE_COLORS = {
    'New Qualified Lead': '#17a2b8',
    'Lead Contacted / Discovery Call': '#007bff',
    'Needs Identified / Proposal': '#ffc107',
    'Negotiation / Follow-Up': '#fd7e14',
    'Closed – Won': '#28a745',
    'Closed – Lost': '#dc3545'
}

# Activity types
ACTIVITY_NOTE = 'note'
ACTIVITY_TASK = 'task'
ACTIVITY_FOLLOW_UP = 'follow_up'
ACTIVITY_REMINDER = 'reminder'
ACTIVITY_CALL_LOG = 'call_log'
ACTIVITY_EMAIL_LOG = 'email_log'
ACTIVITY_STAGE_CHANGE = 'stage_change'
ACTIVITY_ASSIGNMENT = 'assignment'

ACTIVITY_LABELS = {
    ACTIVITY_NOTE: 'Note',
    ACTIVITY_TASK: 'Task',
    ACTIVITY_FOLLOW_UP: 'Follow-up',
    ACTIVITY_REMINDER: 'Reminder',
    ACTIVITY_CALL_LOG: 'Call Log',
    ACTIVITY_EMAIL_LOG: 'Email Log',
    ACTIVITY_STAGE_CHANGE: 'Stage Change',
    ACTIVITY_ASSIGNMENT: 'Assignment'
}

# Social platforms
SOCIAL_LINKEDIN = 'linkedin'
SOCIAL_TWITTER = 'twitter'
SOCIAL_FACEBOOK = 'facebook'
SOCIAL_INSTAGRAM = 'instagram'
SOCIAL_WEBSITE = 'website'
SOCIAL_OTHER = 'other'

SOCIAL_PLATFORMS = [
    (SOCIAL_LINKEDIN, 'LinkedIn'),
    (SOCIAL_TWITTER, 'Twitter'),
    (SOCIAL_FACEBOOK, 'Facebook'),
    (SOCIAL_INSTAGRAM, 'Instagram'),
    (SOCIAL_WEBSITE, 'Website'),
    (SOCIAL_OTHER, 'Other')
]

# Industry options for leads
INDUSTRIES = [
    ('technology', 'Technology'),
    ('healthcare', 'Healthcare'),
    ('finance', 'Finance & Banking'),
    ('ecommerce', 'E-commerce'),
    ('retail', 'Retail'),
    ('manufacturing', 'Manufacturing'),
    ('real_estate', 'Real Estate'),
    ('education', 'Education'),
    ('consulting', 'Consulting'),
    ('marketing', 'Marketing & Advertising'),
    ('hospitality', 'Hospitality & Tourism'),
    ('automotive', 'Automotive'),
    ('construction', 'Construction'),
    ('legal', 'Legal Services'),
    ('nonprofit', 'Non-profit'),
    ('media', 'Media & Entertainment'),
    ('telecom', 'Telecommunications'),
    ('logistics', 'Logistics & Transportation'),
    ('energy', 'Energy & Utilities'),
    ('other', 'Other')
]
