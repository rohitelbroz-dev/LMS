# Elbroz Lead Dashboard - Hostinger Cloud Deployment Guide

## Important Note
Flask apps require **VPS/Cloud hosting** (not shared hosting) because they need root access to install Python and run background services.

---

## Prerequisites
- Hostinger Cloud/VPS plan with Ubuntu (22.04 or 24.04 recommended)
- SSH access to your server
- A subdomain configured (e.g., `leads.elbroz.com`)
- PostgreSQL database (either on the same server or external like Neon)

---

## Part 1: Initial Server Setup

### Step 1: Connect to Your Server via SSH
```bash
ssh root@your_server_ip
```
Or use Hostinger's Terminal feature in the dashboard.

### Step 2: Update System & Install Required Packages
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install python3 python3-pip python3-venv nginx git -y
```

### Step 3: Install PostgreSQL (If hosting database locally)
```bash
sudo apt install postgresql postgresql-contrib -y

# Start PostgreSQL
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Create database and user
sudo -u postgres psql
```

Inside PostgreSQL:
```sql
CREATE DATABASE elbroz_leads;
CREATE USER elbroz_user WITH ENCRYPTED PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE elbroz_leads TO elbroz_user;
\q
```

---

## Part 2: Upload Your Application

### Step 4: Create Application Directory
```bash
mkdir -p /var/www/elbroz-leads
cd /var/www/elbroz-leads
```

### Step 5: Upload Files
**Option A: Using SCP from your local machine:**
```bash
# Run this on your LOCAL machine (not server)
scp -r /path/to/your/replit/project/* root@your_server_ip:/var/www/elbroz-leads/
```

**Option B: Using SFTP/FileZilla:**
1. Connect to your server using FileZilla with your SSH credentials
2. Navigate to `/var/www/elbroz-leads/`
3. Upload all project files

**Option C: Download from Replit:**
1. In Replit, click the three dots menu → Download as ZIP
2. Extract and upload to server

### Files to Upload:
```
app.py
models.py
forms.py
requirements.txt
templates/          (entire folder)
static/             (entire folder)
uploads/            (entire folder - for attachments)
```

---

## Part 3: Configure Python Environment

### Step 6: Create Virtual Environment
```bash
cd /var/www/elbroz-leads
python3 -m venv venv
source venv/bin/activate
```

### Step 7: Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
pip install gunicorn
```

If requirements.txt doesn't exist, install manually:
```bash
pip install flask flask-login flask-wtf flask-socketio psycopg2-binary gunicorn eventlet apscheduler werkzeug email-validator
```

### Step 8: Create requirements.txt (if missing)
```bash
pip freeze > requirements.txt
```

---

## Part 4: Configure Environment Variables

### Step 9: Create Environment File
```bash
nano /var/www/elbroz-leads/.env
```

Add these variables:
```env
DATABASE_URL=postgresql://elbroz_user:your_secure_password@localhost:5432/elbroz_leads
SECRET_KEY=your_very_long_random_secret_key_here
FLASK_ENV=production
```

**For external database (like Neon):**
```env
DATABASE_URL=postgresql://user:password@host:5432/database?sslmode=require
```

### Step 10: Load Environment in App
Make sure your `app.py` loads the `.env` file. Add at the top if not present:
```python
from dotenv import load_dotenv
load_dotenv()
```

Install python-dotenv:
```bash
pip install python-dotenv
```

---

## Part 5: Create WSGI Entry Point

### Step 11: Create wsgi.py
```bash
nano /var/www/elbroz-leads/wsgi.py
```

Add this content:
```python
from app import app, socketio

if __name__ == "__main__":
    socketio.run(app)
```

---

## Part 6: Configure Gunicorn as System Service

### Step 12: Create Systemd Service File
```bash
sudo nano /etc/systemd/system/elbroz-leads.service
```

Add this configuration:
```ini
[Unit]
Description=Gunicorn instance for Elbroz Lead Dashboard
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/elbroz-leads
Environment="PATH=/var/www/elbroz-leads/venv/bin"
EnvironmentFile=/var/www/elbroz-leads/.env
ExecStart=/var/www/elbroz-leads/venv/bin/gunicorn --worker-class eventlet -w 1 --bind unix:elbroz-leads.sock -m 007 wsgi:app

[Install]
WantedBy=multi-user.target
```

**Note:** Using `eventlet` worker for Socket.IO support with 1 worker.

### Step 13: Set Permissions
```bash
sudo chown -R www-data:www-data /var/www/elbroz-leads
sudo chmod -R 755 /var/www/elbroz-leads
```

### Step 14: Start the Service
```bash
sudo systemctl daemon-reload
sudo systemctl start elbroz-leads
sudo systemctl enable elbroz-leads
sudo systemctl status elbroz-leads
```

---

## Part 7: Configure Nginx

### Step 15: Create Nginx Configuration
```bash
sudo nano /etc/nginx/sites-available/elbroz-leads
```

Add this configuration:
```nginx
server {
    listen 80;
    server_name leads.elbroz.com;  # Replace with your subdomain

    client_max_body_size 16M;  # For file uploads

    location / {
        include proxy_params;
        proxy_pass http://unix:/var/www/elbroz-leads/elbroz-leads.sock;
    }

    location /socket.io {
        include proxy_params;
        proxy_http_version 1.1;
        proxy_buffering off;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "Upgrade";
        proxy_pass http://unix:/var/www/elbroz-leads/elbroz-leads.sock;
    }

    location /static {
        alias /var/www/elbroz-leads/static;
        expires 30d;
    }

    location /uploads {
        alias /var/www/elbroz-leads/uploads;
        expires 7d;
    }
}
```

### Step 16: Enable the Site
```bash
sudo ln -s /etc/nginx/sites-available/elbroz-leads /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

---

## Part 8: Configure DNS (Hostinger Panel)

### Step 17: Point Subdomain to Server
1. Go to Hostinger → Domains → elbroz.com → DNS Zone
2. Add an **A Record**:
   - Type: A
   - Name: leads (or your subdomain prefix)
   - Points to: Your server IP address
   - TTL: 14400

Wait 5-15 minutes for DNS propagation.

---

## Part 9: Add SSL Certificate (HTTPS)

### Step 18: Install Certbot
```bash
sudo apt install certbot python3-certbot-nginx -y
```

### Step 19: Get SSL Certificate
```bash
sudo certbot --nginx -d leads.elbroz.com
```

Follow the prompts. Certbot will automatically configure HTTPS.

### Step 20: Auto-Renewal (Automatic)
Certbot sets up auto-renewal by default. Verify with:
```bash
sudo certbot renew --dry-run
```

---

## Part 10: Initialize Database

### Step 21: Run Database Setup
```bash
cd /var/www/elbroz-leads
source venv/bin/activate
python create_postgres_schema.py
```

If you have existing data to migrate:
```bash
python migrate_data_to_postgres.py
```

---

## Updating Your Application (When You Add New Features)

### Method 1: Manual Update via SFTP

1. **Make changes in Replit**
2. **Download changed files** from Replit
3. **Upload to server** via FileZilla/SFTP to `/var/www/elbroz-leads/`
4. **Restart the service:**
```bash
sudo systemctl restart elbroz-leads
```

### Method 2: Using Git (Recommended for Regular Updates)

**Initial Setup (one time):**
```bash
cd /var/www/elbroz-leads
git init
git remote add origin https://github.com/yourusername/elbroz-leads.git
```

**Each time you update:**
1. Push changes from Replit to GitHub
2. On server:
```bash
cd /var/www/elbroz-leads
source venv/bin/activate
git pull origin main
pip install -r requirements.txt  # If new packages added
sudo systemctl restart elbroz-leads
```

### Method 3: Quick Update Script

Create an update script:
```bash
nano /var/www/elbroz-leads/update.sh
```

Add:
```bash
#!/bin/bash
cd /var/www/elbroz-leads
source venv/bin/activate
git pull origin main
pip install -r requirements.txt
sudo systemctl restart elbroz-leads
echo "Update complete!"
```

Make executable:
```bash
chmod +x /var/www/elbroz-leads/update.sh
```

Run updates with:
```bash
./update.sh
```

---

## Troubleshooting Commands

### Check Service Status
```bash
sudo systemctl status elbroz-leads
```

### View Application Logs
```bash
sudo journalctl -u elbroz-leads -f
```

### View Nginx Logs
```bash
sudo tail -f /var/log/nginx/error.log
sudo tail -f /var/log/nginx/access.log
```

### Restart Services
```bash
sudo systemctl restart elbroz-leads
sudo systemctl restart nginx
```

### Check if Socket is Created
```bash
ls -la /var/www/elbroz-leads/*.sock
```

### Test Nginx Configuration
```bash
sudo nginx -t
```

---

## Database Backup

### Create Backup
```bash
pg_dump -U elbroz_user elbroz_leads > backup_$(date +%Y%m%d).sql
```

### Restore Backup
```bash
psql -U elbroz_user elbroz_leads < backup_20241209.sql
```

---

## Security Checklist

- [ ] Change default passwords
- [ ] Configure firewall (UFW)
- [ ] Enable SSL/HTTPS
- [ ] Set up regular backups
- [ ] Keep system updated

### Basic Firewall Setup
```bash
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw enable
```

---

## Quick Reference

| Task | Command |
|------|---------|
| Start app | `sudo systemctl start elbroz-leads` |
| Stop app | `sudo systemctl stop elbroz-leads` |
| Restart app | `sudo systemctl restart elbroz-leads` |
| View logs | `sudo journalctl -u elbroz-leads -f` |
| Check status | `sudo systemctl status elbroz-leads` |

---

## Support

If you encounter issues:
1. Check service logs: `sudo journalctl -u elbroz-leads -n 50`
2. Check Nginx logs: `sudo tail -f /var/log/nginx/error.log`
3. Verify database connection: `psql -U elbroz_user -d elbroz_leads -c "SELECT 1;"`
