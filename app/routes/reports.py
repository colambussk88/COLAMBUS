from flask import Blueprint, render_template, request, send_file
from flask_login import login_required, current_user
from app.utils import require_roles
from app.models import db, Sale, Purchase, Product, Customer, Supplier, Expense, SalesReturn, PurchaseReturn
from datetime import datetime, timedelta
from sqlalchemy import and_, func
import csv
import io

reports_bp = Blueprint('reports', __name__, url_prefix='/reports')

@reports_bp.route('/')
@login_required
def reports_home():
    """Reports home"""
    return render_template('reports/index.html')

# ---------------- SALES REPORT ---------------- #

@reports_bp.route('/sales')
@login_required
def sales_report():

    company_id = current_user.company_id

    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    customer_id = request.args.get('customer_id', type=int)
    export_format = request.args.get('export', '').lower()
    page = request.args.get('page', 1, type=int)

    query = Sale.query.filter_by(company_id=company_id, is_cancelled=False)

    # Date filter
    if start_date and end_date:
        start = datetime.strptime(start_date, '%Y-%m-%d')
        end = datetime.strptime(end_date, '%Y-%m-%d')
        end = end.replace(hour=23, minute=59, second=59)

        query = query.filter(
            Sale.invoice_date >= start,
            Sale.invoice_date <= end
        )

    # Customer filter
    if customer_id:
        query = query.filter_by(customer_id=customer_id)

    # Sorting
    sort = request.args.get('sort', 'date_desc')

    if sort == 'date_asc':
        query = query.order_by(Sale.invoice_date.asc())
    else:
        query = query.order_by(Sale.invoice_date.desc())

    # ---------- CALCULATE TOTALS (ALL FILTERED SALES) ---------- #
    all_sales = query.all()

    total_subtotal = sum((sale.subtotal or 0) for sale in all_sales)
    total_tax = sum((sale.tax_amount or 0) for sale in all_sales)
    total_discount = sum((sale.discount_amount or 0) for sale in all_sales)
    total_sales = sum((sale.total_amount or 0) for sale in all_sales)

    # Pagination for table
    sales_pagination = query.paginate(page=page, per_page=50)
    sales = sales_pagination.items

    # ---------- CSV EXPORT ---------- #
    if export_format == 'csv':

        output = io.StringIO()
        writer = csv.writer(output)

        writer.writerow([
            'Invoice Number', 'Date', 'Customer',
            'Subtotal', 'Tax', 'Discount', 'Total', 'Payment Method'
        ])

        for sale in all_sales:
            writer.writerow([
                sale.invoice_number,
                sale.invoice_date.strftime('%Y-%m-%d %H:%M'),
                sale.customer_name or 'Walk-in',
                sale.subtotal,
                sale.tax_amount,
                sale.discount_amount,
                sale.total_amount,
                sale.payment_method
            ])

        output.seek(0)

        return send_file(
            io.BytesIO(output.getvalue().encode('utf-8')),
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'sales_report_{datetime.utcnow().strftime("%Y%m%d")}.csv'
        )

    customers = Customer.query.filter_by(
        company_id=company_id,
        is_active=True
    ).all()

    return render_template(
        'reports/sales_report.html',
        sales=sales,
        pagination=sales_pagination,
        start_date=start_date,
        end_date=end_date,
        customers=customers,
        customer_id=customer_id,

        total_subtotal=total_subtotal,
        total_tax=total_tax,
        total_discount=total_discount,
        total_sales=total_sales
    )
# ---------------- SALES RETURNS ---------------- #

@reports_bp.route('/sales-returns')
@login_required
@require_roles('owner')
def sales_returns_report():

    company_id = current_user.company_id

    returns = db.session.query(SalesReturn).join(Sale).filter(
        Sale.company_id == company_id
    ).order_by(SalesReturn.return_date.desc()).all()

    return render_template(
        'reports/sales_returns_report.html',
        returns=returns
    )

# ---------------- PURCHASE REPORT ---------------- #

@reports_bp.route('/purchase')
@login_required
@require_roles('owner')
def purchase_report():

    company_id = current_user.company_id

    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    supplier_id = request.args.get('supplier_id', type=int)
    export_format = request.args.get('export', '').lower()

    query = Purchase.query.filter_by(company_id=company_id)

    if start_date and end_date:
        start = datetime.strptime(start_date, '%Y-%m-%d')
        end = datetime.strptime(end_date, '%Y-%m-%d')
        end = end.replace(hour=23, minute=59, second=59)

        query = query.filter(
            Purchase.purchase_date >= start,
            Purchase.purchase_date <= end
        )

    if supplier_id:
        query = query.filter_by(supplier_id=supplier_id)

    purchases = query.order_by(Purchase.purchase_date.desc()).all()

    # ✅ CALCULATE TOTALS
    total_subtotal = sum((p.subtotal or 0) for p in purchases)
    total_tax = sum((p.tax_amount or 0) for p in purchases)
    total_discount = sum((p.discount_amount or 0) for p in purchases)
    total_purchase = sum((p.total_amount or 0) for p in purchases)

    if export_format == 'csv':

        output = io.StringIO()
        writer = csv.writer(output)

        writer.writerow([
            'PO Number', 'Date', 'Supplier',
            'Subtotal', 'Tax', 'Discount', 'Total', 'Status'
        ])

        for purchase in purchases:
            writer.writerow([
                purchase.purchase_number,
                purchase.purchase_date.strftime('%Y-%m-%d'),
                purchase.supplier.supplier_name,
                purchase.subtotal,
                purchase.tax_amount,
                purchase.discount_amount,
                purchase.total_amount,
                purchase.payment_status
            ])

        output.seek(0)

        return send_file(
            io.BytesIO(output.getvalue().encode('utf-8')),
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'purchase_report_{datetime.utcnow().strftime("%Y%m%d")}.csv'
        )

    suppliers = Supplier.query.filter_by(
        company_id=company_id,
        is_active=True
    ).all()

    return render_template(
        'reports/purchase_report.html',

        purchases=purchases,
        suppliers=suppliers,

        start_date=start_date,
        end_date=end_date,
        supplier_id=supplier_id,

        # ✅ SEND TOTALS TO HTML
        total_subtotal=total_subtotal,
        total_tax=total_tax,
        total_discount=total_discount,
        total_purchase=total_purchase
    )
# ---------------- PURCHASE RETURNS ---------------- #

@reports_bp.route('/purchase-returns')
@login_required
@require_roles('owner')
def purchase_returns_report():

    company_id = current_user.company_id

    returns = (
        db.session.query(PurchaseReturn)
        .join(Purchase)
        .filter(Purchase.company_id == company_id)
        .order_by(PurchaseReturn.return_date.desc())
        .all()
    )

    # ✅ Calculate total credit amount for summary
    total_credit = sum((r.credit_amount or 0) for r in returns)

    # ✅ Count total returned quantity
    total_quantity = sum((r.quantity or 0) for r in returns)

    return render_template(
        'reports/purchase_returns_report.html',
        returns=returns,
        total_credit=total_credit,
        total_quantity=total_quantity
    )
# ---------------- EXPIRY REPORT ---------------- #

@reports_bp.route('/expiry')
@login_required
def expiry_report():

    company_id = current_user.company_id

    days_filter = request.args.get('days', 30, type=int)
    export_format = request.args.get('export', '').lower()

    today = datetime.utcnow().date()
    expiry_limit = today + timedelta(days=days_filter)

    products = Product.query.filter(
        Product.company_id == company_id,
        Product.expiry_date != None,
        func.date(Product.expiry_date) <= expiry_limit,
        Product.is_active == True
    ).order_by(Product.expiry_date.asc()).all()

    if export_format == 'csv':

        output = io.StringIO()
        writer = csv.writer(output)

        writer.writerow([
            'Product', 'Batch', 'Quantity',
            'Expiry Date', 'Days Left'
        ])

        for product in products:

            days_left = (product.expiry_date.date() - today).days

            writer.writerow([
                product.product_name,
                product.batch_number,
                product.quantity,
                product.expiry_date.strftime('%Y-%m-%d'),
                days_left
            ])

        output.seek(0)

        return send_file(
            io.BytesIO(output.getvalue().encode('utf-8')),
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'expiry_report_{datetime.utcnow().strftime("%Y%m%d")}.csv'
        )

    return render_template(
        'reports/expiry.html',
        products=products,
        days_filter=days_filter
    )

# ---------------- PROFIT & LOSS ---------------- #

@reports_bp.route('/profit-loss')
@login_required
@require_roles('owner')
def profit_loss_report():

    company_id = current_user.company_id

    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    if not start_date or not end_date:
        today = datetime.utcnow().date()
        start_date = today.replace(day=1).strftime('%Y-%m-%d')
        end_date = today.strftime('%Y-%m-%d')

    start = datetime.strptime(start_date, '%Y-%m-%d')
    end = datetime.strptime(end_date, '%Y-%m-%d')

    total_sales = db.session.query(func.sum(Sale.total_amount)).filter(
        Sale.company_id == company_id,
        Sale.invoice_date.between(start, end),
        Sale.is_cancelled == False
    ).scalar() or 0

    total_purchase = db.session.query(func.sum(Purchase.total_amount)).filter(
        Purchase.company_id == company_id,
        Purchase.purchase_date.between(start, end)
    ).scalar() or 0

    total_expenses = db.session.query(func.sum(Expense.amount)).filter(
        Expense.company_id == company_id,
        Expense.expense_date.between(start, end)
    ).scalar() or 0

    gross_profit = total_sales - total_purchase
    net_profit = gross_profit - total_expenses

    return render_template(
        'reports/profit_loss.html',
        start_date=start_date,
        end_date=end_date,
        total_sales=total_sales,
        total_purchase_cost=total_purchase,
        total_expenses=total_expenses,
        gross_profit=gross_profit,
        net_profit=net_profit
    )

# ---------------- TAX SUMMARY ---------------- #

@reports_bp.route('/tax-summary')
@login_required
@require_roles('owner')
def tax_summary():

    company_id = current_user.company_id

    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    query = Sale.query.filter_by(
        company_id=company_id,
        is_cancelled=False
    )

    if start_date and end_date:
        start = datetime.strptime(start_date, '%Y-%m-%d')
        end = datetime.strptime(end_date, '%Y-%m-%d')
        query = query.filter(Sale.invoice_date.between(start, end))

    sales = query.all()

    tax_breakdown = {}

    for sale in sales:
        for item in sale.items:

            rate = item.tax_percentage or 0

            if rate not in tax_breakdown:
                tax_breakdown[rate] = {
                    "items": 0,
                    "tax_amount": 0
                }

            tax_breakdown[rate]["items"] += item.quantity
            tax_breakdown[rate]["tax_amount"] += item.tax_amount or 0

    return render_template(
        'reports/tax_summary.html',
        tax_breakdown=tax_breakdown,
        start_date=start_date,
        end_date=end_date
    )

# ---------------- OUTSTANDING PAYMENTS ---------------- #

@reports_bp.route('/outstanding')
@login_required
@require_roles('owner')
def outstanding_payments():

    company_id = current_user.company_id

    customers = Customer.query.filter(
        Customer.company_id == company_id,
        Customer.current_balance > 0
    ).all()

    suppliers = db.session.query(
        Supplier,
        func.sum(Purchase.total_amount).label("outstanding")
    ).outerjoin(
        Purchase, Purchase.supplier_id == Supplier.id
    ).filter(
        Supplier.company_id == company_id,
        Purchase.payment_status != 'paid'
    ).group_by(Supplier.id).all()

    return render_template(
        'reports/outstanding_payments.html',
        customers=customers,
        suppliers=suppliers
    )

