from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, PasswordField, SelectField, SelectMultipleField, TextAreaField, DateField, DateTimeField, IntegerField, DecimalField, FieldList, FormField
from wtforms.validators import DataRequired, Email, Length, Optional, NumberRange, URL
from constants import ROLE_ADMIN, ROLE_MANAGER, ROLE_MARKETER, ROLE_BD_SALES, ROLE_LABELS, SOCIAL_PLATFORMS, INDUSTRIES

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])

class LeadForm(FlaskForm):
    full_name = StringField('Full Name', validators=[DataRequired(), Length(max=200)])
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=200)])
    phone = StringField('Phone Number', validators=[DataRequired(), Length(max=50)])
    company = StringField('Company Name', validators=[DataRequired(), Length(max=200)])
    domain = StringField('Domain Name', validators=[DataRequired(), Length(max=200)])
    industry = SelectField('Industry', validators=[DataRequired()], choices=INDUSTRIES)
    services = SelectMultipleField('Services Pitched', validators=[DataRequired()], coerce=int)
    country = StringField('Country', validators=[DataRequired(), Length(max=100)])
    state = StringField('State', validators=[DataRequired(), Length(max=100)])
    city = StringField('City', validators=[DataRequired(), Length(max=100)])
    attachment = FileField('Attachment', validators=[
        Optional(),
        FileAllowed(['pdf', 'doc', 'docx', 'txt', 'jpg', 'jpeg', 'png'], 'Only documents and images allowed!')
    ])
    linkedin_url = StringField('LinkedIn URL', validators=[Optional(), URL(message='Please enter a valid URL'), Length(max=500)])
    twitter_url = StringField('Twitter URL', validators=[Optional(), URL(message='Please enter a valid URL'), Length(max=500)])
    facebook_url = StringField('Facebook URL', validators=[Optional(), URL(message='Please enter a valid URL'), Length(max=500)])
    website_url = StringField('Website URL', validators=[Optional(), URL(message='Please enter a valid URL'), Length(max=500)])

class RejectForm(FlaskForm):
    rejection_comment = TextAreaField('Rejection Comment', validators=[DataRequired(), Length(min=10, max=1000)])

class ResubmitForm(FlaskForm):
    rectification_comment = TextAreaField('Rectification Comment', validators=[DataRequired(), Length(min=10, max=1000)])

class ServiceForm(FlaskForm):
    name = StringField('Service Name', validators=[DataRequired(), Length(max=200)])

class UserForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired(), Length(max=200)])
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=200)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    role = SelectField('Role', validators=[DataRequired()], 
                      choices=[
                          (ROLE_ADMIN, ROLE_LABELS[ROLE_ADMIN]),
                          (ROLE_MANAGER, ROLE_LABELS[ROLE_MANAGER]),
                          (ROLE_MARKETER, ROLE_LABELS[ROLE_MARKETER]),
                          (ROLE_BD_SALES, ROLE_LABELS[ROLE_BD_SALES])
                      ])

class UserEditForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired(), Length(max=200)])
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=200)])
    password = PasswordField('Password (leave blank to keep current)', validators=[Optional(), Length(min=6)])
    role = SelectField('Role', validators=[DataRequired()], 
                      choices=[
                          (ROLE_ADMIN, ROLE_LABELS[ROLE_ADMIN]),
                          (ROLE_MANAGER, ROLE_LABELS[ROLE_MANAGER]),
                          (ROLE_MARKETER, ROLE_LABELS[ROLE_MARKETER]),
                          (ROLE_BD_SALES, ROLE_LABELS[ROLE_BD_SALES])
                      ])
    avatar = FileField('Profile Picture', validators=[
        Optional(),
        FileAllowed(['jpg', 'jpeg', 'png', 'gif'], 'Only image files (JPG, PNG, GIF) are allowed!')
    ])
    bio = TextAreaField('Bio', validators=[Optional(), Length(max=500)])

class ProfileForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired(), Length(max=200)])
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=200)])
    password = PasswordField('New Password (leave blank to keep current)', validators=[Optional(), Length(min=6)])
    confirm_password = PasswordField('Confirm Password', validators=[Optional()])
    avatar = FileField('Profile Picture', validators=[
        Optional(),
        FileAllowed(['jpg', 'jpeg', 'png', 'gif'], 'Only image files (JPG, PNG, GIF) are allowed!')
    ])
    bio = TextAreaField('Bio', validators=[Optional(), Length(max=500)])

class LeadEditForm(FlaskForm):
    full_name = StringField('Full Name', validators=[DataRequired(), Length(max=200)])
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=200)])
    phone = StringField('Phone Number', validators=[DataRequired(), Length(max=50)])
    company = StringField('Company Name', validators=[DataRequired(), Length(max=200)])
    domain = StringField('Domain Name', validators=[DataRequired(), Length(max=200)])
    industry = SelectField('Industry', validators=[DataRequired()], choices=INDUSTRIES)
    services = SelectMultipleField('Services Pitched', validators=[DataRequired()], coerce=int)
    country = StringField('Country', validators=[DataRequired(), Length(max=100)])
    state = StringField('State', validators=[DataRequired(), Length(max=100)])
    city = StringField('City', validators=[DataRequired(), Length(max=100)])
    attachment = FileField('Attachment', validators=[
        Optional(),
        FileAllowed(['pdf', 'doc', 'docx', 'txt', 'jpg', 'jpeg', 'png'], 'Only documents and images allowed!')
    ])
    linkedin_url = StringField('LinkedIn URL', validators=[Optional(), URL(message='Please enter a valid URL'), Length(max=500)])
    twitter_url = StringField('Twitter URL', validators=[Optional(), URL(message='Please enter a valid URL'), Length(max=500)])
    facebook_url = StringField('Facebook URL', validators=[Optional(), URL(message='Please enter a valid URL'), Length(max=500)])
    website_url = StringField('Website URL', validators=[Optional(), URL(message='Please enter a valid URL'), Length(max=500)])
    change_summary = TextAreaField('Summary of Changes', validators=[DataRequired(), Length(min=10, max=500)])

class TargetForm(FlaskForm):
    assignee = SelectField('Assign To', validators=[DataRequired()], coerce=int)
    target_count = IntegerField('Target Count', validators=[DataRequired(), NumberRange(min=1, max=1000)])
    period_start = DateField('Period Start', validators=[DataRequired()])
    period_end = DateField('Period End', validators=[DataRequired()])
    target_type = SelectField('Target Type', validators=[DataRequired()],
                            choices=[('monthly', 'Monthly'), ('weekly', 'Weekly')])

class BDAssignmentForm(FlaskForm):
    bd_sales_id = SelectField('Assign to BD Sales', validators=[DataRequired()], coerce=int)
    note = TextAreaField('Assignment Note (Optional)', validators=[Optional(), Length(max=500)])

class SocialProfileForm(FlaskForm):
    platform = SelectField('Platform', validators=[DataRequired()], choices=SOCIAL_PLATFORMS)
    url = StringField('URL', validators=[DataRequired(), URL(message='Please enter a valid URL'), Length(max=500)])

class ActivityForm(FlaskForm):
    activity_type = SelectField('Activity Type', validators=[DataRequired()],
                              choices=[
                                  ('note', 'Note'),
                                  ('task', 'Task'),
                                  ('follow_up', 'Follow-up'),
                                  ('call_log', 'Call Log'),
                                  ('email_log', 'Email Log')
                              ])
    title = StringField('Title', validators=[Optional(), Length(max=200)])
    description = TextAreaField('Description', validators=[DataRequired(), Length(max=2000)])
    due_at = DateTimeField('Due Date & Time (IST)', validators=[Optional()], format='%Y-%m-%dT%H:%M')
    reminder_at = DateTimeField('Reminder Date & Time (IST)', validators=[Optional()], format='%Y-%m-%dT%H:%M')

class DealAmountForm(FlaskForm):
    deal_amount = DecimalField('Deal Amount ($)', validators=[Optional(), NumberRange(min=0)])

class PipelineStageForm(FlaskForm):
    name = StringField('Stage Name', validators=[DataRequired(), Length(max=100)])
    color = StringField('Color (hex code)', validators=[Optional(), Length(max=7)])
    description = TextAreaField('Description', validators=[Optional(), Length(max=500)])
