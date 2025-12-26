from flask import Flask
from config import Config
from flask_migrate import Migrate
from flask_login import LoginManager
from .routes import attachments as attachments_bp  # add near other route imports

# ...existing code...

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # ...existing app factory code...

    # Register blueprints
    app.register_blueprint(attachments_bp.bp)

    return app