from flask import (
    Blueprint,
    current_app,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    jsonify,
)
from flask_login import login_required, current_user
from app.utils import require_roles
from werkzeug.utils import secure_filename
from app.models import (
    db,
    Expense,
    Sale,
    Purchase,
    Customer,
    Supplier,
    SalesReturn,
    PurchaseReturn,
)
from datetime import datetime
import os

accounting_bp = Blueprint("accounting", __name__, url_prefix="/accounting")


ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "pdf"}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@accounting_bp.route("/")
@login_required
@require_roles("owner")
def accounting_dashboard():
    """Accounting dashboard"""
    company_id = current_user.company_id
    today = datetime.utcnow().date()
    month_start = datetime.utcnow().replace(day=1).date()

    # Today's sales
    today_sales = (
        db.session.query(db.func.sum(Sale.total_amount))
        .filter(
            db.and_(
                Sale.company_id == company_id,
                db.func.date(Sale.invoice_date) == today,
                Sale.is_cancelled == False,
            )
        )
        .scalar()
        or 0
    )

    # Today's expenses
    today_expenses = (
        db.session.query(db.func.sum(Expense.amount))
        .filter(
            db.and_(
                Expense.company_id == company_id,
                db.func.date(Expense.expense_date) == today,
            )
        )
        .scalar()
        or 0
    )

    # Today's profit
    today_profit = today_sales - today_expenses

    # Monthly figures
    month_sales = (
        db.session.query(db.func.sum(Sale.total_amount))
        .filter(
            db.and_(
                Sale.company_id == company_id,
                db.func.date(Sale.invoice_date) >= month_start,
                Sale.is_cancelled == False,
            )
        )
        .scalar()
        or 0
    )

    month_expenses = (
        db.session.query(db.func.sum(Expense.amount))
        .filter(
            db.and_(
                Expense.company_id == company_id,
                db.func.date(Expense.expense_date) >= month_start,
            )
        )
        .scalar()
        or 0
    )

    month_profit = month_sales - month_expenses

    return render_template(
        "accounting/dashboard.html",
        today_sales=today_sales,
        today_expenses=today_expenses,
        today_profit=today_profit,
        month_sales=month_sales,
        month_expenses=month_expenses,
        month_profit=month_profit,
    )


@accounting_bp.route("/expenses")
@login_required
@require_roles("owner")
def expenses_list():
    """List all expenses"""
    company_id = current_user.company_id
    page = request.args.get("page", 1, type=int)
    category = request.args.get("category", "")
    start_date = request.args.get("start_date", "")
    end_date = request.args.get("end_date", "")

    query = Expense.query.filter_by(company_id=company_id)

    if category:
        query = query.filter_by(expense_category=category)

    if start_date and end_date:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        query = query.filter(
            db.and_(Expense.expense_date >= start, Expense.expense_date <= end)
        )

    expenses = query.order_by(Expense.expense_date.desc()).paginate(
        page=page, per_page=20
    )

    # Get categories
    categories = (
        db.session.query(Expense.expense_category)
        .filter_by(company_id=company_id)
        .distinct()
        .all()
    )
    categories = [c[0] for c in categories if c[0]]

    return render_template(
        "accounting/expenses_list.html",
        expenses=expenses,
        category=category,
        start_date=start_date,
        end_date=end_date,
        categories=categories,
    )


@accounting_bp.route("/expenses/add", methods=["GET", "POST"])
@login_required
@require_roles("owner")
def add_expense():
    """Add new expense"""
    if request.method == "POST":
        try:
            receipt_image = None
            if "receipt_image" in request.files:
                file = request.files["receipt_image"]
                if file and file.filename and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    filename = f"{datetime.utcnow().timestamp()}_{filename}"
                    upload_folder = current_app.config.get(
                        "UPLOAD_FOLDER"
                    ) or os.path.join(current_app.root_path, "static", "uploads")
                    try:
                        os.makedirs(upload_folder, exist_ok=True)
                    except PermissionError:
                        upload_folder = os.path.join(
                            current_app.root_path, "static", "uploads"
                        )
                        os.makedirs(upload_folder, exist_ok=True)
                    file.save(os.path.join(upload_folder, filename))
                    receipt_image = f"uploads/{filename}"

            expense_date = datetime.strptime(
                request.form.get("expense_date"), "%Y-%m-%d"
            )

            expense = Expense(
                company_id=current_user.company_id,
                expense_category=request.form.get("expense_category"),
                description=request.form.get("description"),
                amount=float(request.form.get("amount")),
                receipt_image=receipt_image,
                expense_date=expense_date,
            )

            db.session.add(expense)
            db.session.commit()

            flash("Expense added successfully.", "success")
            return redirect(url_for("accounting.expenses_list"))

        except Exception as e:
            db.session.rollback()
            flash(f"Failed to add expense: {str(e)}", "danger")
            return redirect(url_for("accounting.add_expense"))

    return render_template("accounting/add_expense.html")


@accounting_bp.route("/expenses/<int:expense_id>/edit", methods=["GET", "POST"])
@login_required
@require_roles("owner")
def edit_expense(expense_id):
    """Edit expense"""
    expense = Expense.query.get(expense_id)
    if not expense or expense.company_id != current_user.company_id:
        flash("Expense not found.", "danger")
        return redirect(url_for("accounting.expenses_list"))

    if request.method == "POST":
        try:
            expense.expense_category = request.form.get("expense_category")
            expense.description = request.form.get("description")
            expense.amount = float(request.form.get("amount"))
            expense.expense_date = datetime.strptime(
                request.form.get("expense_date"), "%Y-%m-%d"
            )

            if "receipt_image" in request.files:
                file = request.files["receipt_image"]
                if file and file.filename and allowed_file(file.filename):
                    # Delete old image
                    if expense.receipt_image:
                        old_file = os.path.join(
                            current_app.root_path, "static", expense.receipt_image
                        )
                        if os.path.exists(old_file):
                            try:
                                os.remove(old_file)
                            except PermissionError:
                                pass

                    filename = secure_filename(file.filename)
                    filename = f"{datetime.utcnow().timestamp()}_{filename}"
                    upload_folder = current_app.config.get(
                        "UPLOAD_FOLDER"
                    ) or os.path.join(current_app.root_path, "static", "uploads")
                    try:
                        os.makedirs(upload_folder, exist_ok=True)
                    except PermissionError:
                        upload_folder = os.path.join(
                            current_app.root_path, "static", "uploads"
                        )
                        os.makedirs(upload_folder, exist_ok=True)
                    file.save(os.path.join(upload_folder, filename))
                    expense.receipt_image = f"uploads/{filename}"

            db.session.commit()

            flash("Expense updated successfully.", "success")
            return redirect(url_for("accounting.expenses_list"))

        except Exception as e:
            db.session.rollback()
            flash(f"Failed to update expense: {str(e)}", "danger")
            return redirect(url_for("accounting.edit_expense", expense_id=expense_id))

    return render_template("accounting/edit_expense.html", expense=expense)


@accounting_bp.route("/expenses/<int:expense_id>/delete", methods=["POST"])
@login_required
@require_roles("owner")
def delete_expense(expense_id):
    """Delete expense"""
    expense = Expense.query.get(expense_id)
    if not expense or expense.company_id != current_user.company_id:
        flash("Expense not found.", "danger")
        return redirect(url_for("accounting.expenses_list"))

    try:
        # Delete receipt image if exists
        if expense.receipt_image:
            old_file = os.path.join(
                current_app.root_path, "static", expense.receipt_image
            )
            if os.path.exists(old_file):
                try:
                    os.remove(old_file)
                except PermissionError:
                    pass

        db.session.delete(expense)
        db.session.commit()

        flash("Expense deleted successfully.", "success")
        return redirect(url_for("accounting.expenses_list"))

    except Exception as e:
        db.session.rollback()
        flash(f"Failed to delete expense: {str(e)}", "danger")
        return redirect(url_for("accounting.expenses_list"))


@accounting_bp.route("/cash-summary")
@login_required
@require_roles("owner")
def cash_summary():
    """Daily cash summary"""
    company_id = current_user.company_id
    date = request.args.get("date")

    if date:
        summary_date = datetime.strptime(date, "%Y-%m-%d").date()
    else:
        summary_date = datetime.utcnow().date()

    # Sales on date
    sales = Sale.query.filter(
        db.and_(
            Sale.company_id == company_id,
            db.func.date(Sale.invoice_date) == summary_date,
            Sale.is_cancelled == False,
        )
    ).all()

    # Expenses on date
    expenses = Expense.query.filter(
        db.and_(
            Expense.company_id == company_id,
            db.func.date(Expense.expense_date) == summary_date,
        )
    ).all()

    total_sales = sum(s.total_amount for s in sales)
    total_expenses = sum(e.amount for e in expenses)
    cash_in_hand = total_sales - total_expenses

    return render_template(
        "accounting/cash_summary.html",
        summary_date=summary_date,
        sales=sales,
        expenses=expenses,
        total_sales=total_sales,
        total_expenses=total_expenses,
        cash_in_hand=cash_in_hand,
    )


@accounting_bp.route("/sales-register")
@login_required
def sales_register():
    """Sales register"""
    company_id = current_user.company_id
    start_date = request.args.get("start_date", "")
    end_date = request.args.get("end_date", "")

    query = Sale.query.filter(
        db.and_(Sale.company_id == company_id, Sale.is_cancelled == False)
    )

    if start_date and end_date:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        query = query.filter(
            db.and_(Sale.invoice_date >= start, Sale.invoice_date <= end)
        )

    sales = query.order_by(Sale.invoice_date.desc()).all()

    return render_template(
        "accounting/sales_register.html",
        sales=sales,
        start_date=start_date,
        end_date=end_date,
    )


@accounting_bp.route("/purchase-register")
@login_required
@require_roles("owner")
def purchase_register():
    """Purchase register"""
    company_id = current_user.company_id
    start_date = request.args.get("start_date", "")
    end_date = request.args.get("end_date", "")

    query = Purchase.query.filter_by(company_id=company_id)

    if start_date and end_date:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        query = query.filter(
            db.and_(Purchase.purchase_date >= start, Purchase.purchase_date <= end)
        )

    purchases = query.order_by(Purchase.purchase_date.desc()).all()

    return render_template(
        "accounting/purchase_register.html",
        purchases=purchases,
        start_date=start_date,
        end_date=end_date,
    )
