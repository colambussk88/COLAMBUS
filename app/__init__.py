from flask import Flask
from flask_login import LoginManager
from config import config
from app.models import db, User
import os


def create_app(config_name="development"):
    """Application factory"""
    app = Flask(__name__)

    # Create instance directory if possible (not at import time)
    try:
        instance_dir = app.config.from_object(config[config_name]) if False else None
    except Exception:
        instance_dir = None

    # Load configuration
    app.config.from_object(config[config_name])
    # Ensure instance folder exists (if writable) and set config key
    instance_dir = app.config.get("INSTANCE_DIR")
    if instance_dir:
        try:
            os.makedirs(instance_dir, exist_ok=True)
        except PermissionError:
            # Running in an environment where the process cannot create the instance folder.
            # Fall back to using the repo directory for DB (read-only scenario will still fail later).
            print(
                f"Warning: cannot create instance dir {instance_dir}; continuing without creating it."
            )

    # Ensure upload folder exists (may raise if not writable)
    try:
        os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    except PermissionError:
        print(f"Warning: cannot create upload folder {app.config.get('UPLOAD_FOLDER')}")

    # Initialize extensions
    db.init_app(app)

    # Setup Flask-Login
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please log in to access this page."
    login_manager.login_message_category = "info"

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Register blueprints
    from app.routes.auth import auth_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.inventory import inventory_bp
    from app.routes.sales import sales_bp
    from app.routes.users import users_bp
    from app.routes.purchases import purchases_bp
    from app.routes.customers import customers_bp
    from app.routes.suppliers import suppliers_bp
    from app.routes.doctors import doctors_bp
    from app.routes.accounting import accounting_bp
    from app.routes.reports import reports_bp
    from app.routes.alerts import alerts_bp
    from app.routes.master import master_bp
    from app.routes.admin import admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(inventory_bp)
    app.register_blueprint(sales_bp)
    app.register_blueprint(purchases_bp)
    app.register_blueprint(customers_bp)
    app.register_blueprint(suppliers_bp)
    app.register_blueprint(doctors_bp)
    app.register_blueprint(accounting_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(alerts_bp)
    app.register_blueprint(master_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(users_bp)

    # Create database tables
    with app.app_context():
        db.create_all()

    return app, login_manager
