from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.models import Company, User, db, AdminLog
from app.utils import require_roles
from flask_login import login_user, current_user, logout_user, login_required
from datetime import datetime

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


# ---------------------------------------------------
# ADMIN LOGIN (SECURE - DATABASE BASED)
# ---------------------------------------------------
@admin_bp.route("/login", methods=["GET", "POST"])
def admin_login():

    if current_user.is_authenticated and current_user.role == "owner":
        return redirect(url_for("admin.companies_list"))

    if request.method == "POST":

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if not username or not password:
            flash("Username and password required", "danger")
            return redirect(url_for("admin.admin_login"))

        user = User.query.filter_by(username=username).first()

        # ✅ CHECK USER + PASSWORD + ROLE
        if user and user.check_password(password) and user.role == "owner":

            login_user(user, remember=True)

            user.last_login = datetime.utcnow()
            db.session.commit()

            flash("Admin login successful", "success")
            return redirect(url_for("admin.companies_list"))

        flash("Invalid admin credentials", "danger")

    return render_template("admin/login.html")


# ---------------------------------------------------
# ADMIN LOGOUT
# ---------------------------------------------------
@admin_bp.route("/logout")
@login_required
def admin_logout():
    logout_user()
    flash("Logged out successfully", "info")
    return redirect(url_for("admin.admin_login"))


# ---------------------------------------------------
# COMPANY LIST (ADMIN PANEL)
# ---------------------------------------------------
@admin_bp.route("/companies")
@require_roles("owner")
def companies_list():
    companies = Company.query.order_by(Company.created_date.desc()).all()
    return render_template("admin/companies_list.html", companies=companies)


# ---------------------------------------------------
# EDIT COMPANY LOGIN CREDENTIALS
# ---------------------------------------------------
@admin_bp.route("/companies/<int:company_id>/edit", methods=["GET", "POST"])
@require_roles("owner")
def edit_company_login(company_id):

    company = Company.query.get_or_404(company_id)
    user = User.query.filter_by(company_id=company.id).first()

    logs = (
        AdminLog.query.filter_by(company_id=company.id)
        .order_by(AdminLog.created_date.desc())
        .limit(50)
        .all()
    )

    if request.method == "POST":

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if not username:
            flash("Username is required", "danger")
            return redirect(url_for("admin.edit_company_login", company_id=company.id))

        # ✅ CHECK DUPLICATE USERNAME
        existing = User.query.filter(User.username == username).first()
        if existing and (not user or existing.id != user.id):
            flash("Username already taken", "danger")
            return redirect(url_for("admin.edit_company_login", company_id=company.id))

        # ✅ CREATE OR UPDATE USER
        if not user:
            user = User(company_id=company.id, username=username, role="owner")
            if password:
                user.set_password(password)
            db.session.add(user)
        else:
            user.username = username
            if password:
                user.set_password(password)

        db.session.commit()

        # ✅ ADMIN LOG
        try:
            log = AdminLog(
                company_id=company.id,
                performed_by=current_user.id,
                action="update_credentials",
                details=f"username={username}",
            )
            db.session.add(log)
            db.session.commit()
        except:
            db.session.rollback()

        flash("Login credentials updated successfully", "success")
        return redirect(url_for("admin.companies_list"))

    return render_template(
        "admin/edit_company.html",
        company=company,
        user=user,
        logs=logs
    )