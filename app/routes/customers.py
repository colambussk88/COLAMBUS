from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app.utils import require_roles
from app.models import db, Customer, Sale
from datetime import datetime
from sqlalchemy import and_, func

customers_bp = Blueprint("customers", __name__, url_prefix="/customers")


@customers_bp.route("/")
@login_required
def customers_list():
    """List all customers"""
    company_id = current_user.company_id
    page = request.args.get("page", 1, type=int)
    search = request.args.get("search", "")

    query = Customer.query.filter(
        and_(Customer.company_id == company_id, Customer.is_active == True)
    )

    if search:
        query = query.filter(
            db.or_(
                Customer.customer_name.ilike(f"%{search}%"),
                Customer.phone.ilike(f"%{search}%"),
                Customer.email.ilike(f"%{search}%"),
            )
        )

    customers = query.order_by(Customer.customer_name).paginate(page=page, per_page=20)

    return render_template(
        "customers/customers_list.html", customers=customers, search=search
    )


@customers_bp.route("/add", methods=["GET", "POST"])
@login_required
def add_customer():
    """Add new customer"""
    if request.method == "POST":
        try:
            # Check for duplicate phone
            if Customer.query.filter_by(phone=request.form.get("phone")).first():
                flash("Phone number already exists.", "danger")
                return redirect(url_for("customers.add_customer"))

            # Check for duplicate email
            email = request.form.get("email")
            if email and Customer.query.filter_by(email=email).first():
                flash("Email already exists.", "danger")
                return redirect(url_for("customers.add_customer"))

            customer = Customer(
                company_id=current_user.company_id,
                customer_name=request.form.get("customer_name"),
                phone=request.form.get("phone"),
                email=email,
                address=request.form.get("address"),
                gst_number=request.form.get("gst_number"),
                credit_limit=float(request.form.get("credit_limit", 0)),
                current_balance=0,
            )

            db.session.add(customer)
            db.session.commit()

            flash("Customer added successfully.", "success")
            return redirect(
                url_for("customers.customer_detail", customer_id=customer.id)
            )

        except Exception as e:
            db.session.rollback()
            flash(f"Failed to add customer: {str(e)}", "danger")
            return redirect(url_for("customers.add_customer"))

    return render_template("customers/add_customer.html")


@customers_bp.route("/<int:customer_id>")
@login_required
def customer_detail(customer_id):
    """Customer detail view"""
    customer = Customer.query.get(customer_id)
    if not customer or customer.company_id != current_user.company_id:
        flash("Customer not found.", "danger")
        return redirect(url_for("customers.customers_list"))

    # Get purchase history (sales visible to both owner and manager)
    sales = (
        Sale.query.filter_by(customer_id=customer_id)
        .order_by(Sale.invoice_date.desc())
        .limit(20)
        .all()
    )

    return render_template(
        "customers/customer_detail.html", customer=customer, sales=sales
    )


@customers_bp.route("/<int:customer_id>/edit", methods=["GET", "POST"])
@login_required
def edit_customer(customer_id):
    """Edit customer"""
    customer = Customer.query.get(customer_id)
    if not customer or customer.company_id != current_user.company_id:
        flash("Customer not found.", "danger")
        return redirect(url_for("customers.customers_list"))

    if request.method == "POST":
        try:
            customer.customer_name = request.form.get(
                "customer_name", customer.customer_name
            )
            customer.phone = request.form.get("phone", customer.phone)
            customer.email = request.form.get("email", customer.email)
            customer.address = request.form.get("address", customer.address)
            customer.gst_number = request.form.get("gst_number", customer.gst_number)
            customer.credit_limit = float(
                request.form.get("credit_limit", customer.credit_limit)
            )
            customer.updated_date = datetime.utcnow()

            db.session.commit()

            flash("Customer updated successfully.", "success")
            return redirect(
                url_for("customers.customer_detail", customer_id=customer_id)
            )

        except Exception as e:
            db.session.rollback()
            flash(f"Failed to update customer: {str(e)}", "danger")
            return redirect(url_for("customers.edit_customer", customer_id=customer_id))

    return render_template("customers/edit_customer.html", customer=customer)


@customers_bp.route("/<int:customer_id>/record-payment", methods=["POST"])
@login_required
@require_roles("owner")
def record_payment(customer_id):
    """Record payment from customer"""
    customer = Customer.query.get(customer_id)
    if not customer or customer.company_id != current_user.company_id:
        return jsonify({"success": False, "message": "Customer not found"}), 404

    try:
        payment_amount = float(request.json.get("amount", 0))

        if payment_amount <= 0:
            return jsonify({"success": False, "message": "Invalid payment amount"}), 400

        if payment_amount > customer.current_balance:
            return (
                jsonify(
                    {"success": False, "message": "Payment exceeds outstanding balance"}
                ),
                400,
            )

        customer.current_balance -= payment_amount
        customer.updated_date = datetime.utcnow()
        db.session.commit()

        return jsonify(
            {
                "success": True,
                "message": "Payment recorded successfully",
                "new_balance": customer.current_balance,
            }
        )

    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500


@customers_bp.route("/<int:customer_id>/delete", methods=["POST"])
@login_required
def delete_customer(customer_id):
    """Soft delete customer"""
    customer = Customer.query.get(customer_id)
    if not customer or customer.company_id != current_user.company_id:
        flash("Customer not found.", "danger")
        return redirect(url_for("customers.customers_list"))

    try:
        customer.is_active = False
        customer.updated_date = datetime.utcnow()
        db.session.commit()

        flash("Customer deleted successfully.", "success")
        return redirect(url_for("customers.customers_list"))

    except Exception as e:
        db.session.rollback()
        flash(f"Failed to delete customer: {str(e)}", "danger")
        return redirect(url_for("customers.customer_detail", customer_id=customer_id))


@customers_bp.route("/ledger")
@login_required
@require_roles("owner")
def customer_ledger():
    """Customer ledger report"""
    company_id = current_user.company_id

    # Get all customers with their balances and purchase history
    customers = Customer.query.filter(
        and_(Customer.company_id == company_id, Customer.is_active == True)
    ).all()

    return render_template("customers/ledger.html", customers=customers)
