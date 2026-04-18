from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.models import db, User
from app.utils import require_roles
from datetime import datetime

users_bp = Blueprint("users", __name__, url_prefix="/users")


@users_bp.route("/")
@login_required
@require_roles("owner")
def users_list():
    company_id = current_user.company_id
    users = User.query.filter_by(company_id=company_id).order_by(User.username).all()
    return render_template("users/list.html", users=users)


@users_bp.route("/add", methods=["GET", "POST"])
@login_required
@require_roles("owner")
def add_user():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        role = request.form.get("role", "manager")

        if not username or not password:
            flash("Username and password are required.", "danger")
            return redirect(url_for("users.add_user"))

        if User.query.filter_by(username=username).first():
            flash("Username already exists.", "danger")
            return redirect(url_for("users.add_user"))

        try:
            user = User(
                company_id=current_user.company_id,
                username=username,
                is_active=True,
                role=role,
            )
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            flash("User added successfully.", "success")
            return redirect(url_for("users.users_list"))
        except Exception as e:
            db.session.rollback()
            flash(f"Failed to add user: {e}", "danger")
            return redirect(url_for("users.add_user"))

    return render_template("users/add.html")


@users_bp.route("/<int:user_id>/edit", methods=["GET", "POST"])
@login_required
@require_roles("owner")
def edit_user(user_id):
    user = User.query.get(user_id)
    if not user or user.company_id != current_user.company_id:
        flash("User not found.", "danger")
        return redirect(url_for("users.users_list"))

    if request.method == "POST":
        user.username = request.form.get("username", user.username)
        role = request.form.get("role", user.role)
        user.role = role
        password = request.form.get("password")
        if password:
            user.set_password(password)
        user.updated_date = datetime.utcnow()
        try:
            db.session.commit()
            flash("User updated.", "success")
            return redirect(url_for("users.users_list"))
        except Exception as e:
            db.session.rollback()
            flash(f"Failed to update user: {e}", "danger")
            return redirect(url_for("users.edit_user", user_id=user_id))

    return render_template("users/edit.html", user=user)


@users_bp.route("/<int:user_id>/delete", methods=["POST"])
@login_required
@require_roles("owner")
def delete_user(user_id):
    user = User.query.get(user_id)
    if not user or user.company_id != current_user.company_id:
        flash("User not found.", "danger")
        return redirect(url_for("users.users_list"))

    # Prevent deleting self
    if user.id == current_user.id:
        flash("You cannot delete your own account.", "danger")
        return redirect(url_for("users.users_list"))

    try:
        db.session.delete(user)
        db.session.commit()
        flash("User deleted.", "success")
        return redirect(url_for("users.users_list"))
    except Exception as e:
        db.session.rollback()
        flash(f"Failed to delete user: {e}", "danger")
        return redirect(url_for("users.users_list"))
