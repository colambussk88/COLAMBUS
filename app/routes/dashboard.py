from flask import Blueprint, render_template
from flask_login import login_required, current_user
from app.models import db, Sale, Purchase, PurchaseReturn, Product, Customer, Supplier, SalesReturn, SaleItem
from datetime import datetime, timedelta
from sqlalchemy import func, and_

dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/dashboard')


@dashboard_bp.route('/')
@login_required
def dashboard():

    company_id = current_user.company_id
    today = datetime.utcnow().date()
    month_start = datetime.utcnow().replace(day=1).date()

    # -------------------------------
    # TODAY SALES
    # -------------------------------
    today_sales = db.session.query(func.sum(Sale.total_amount)).filter(
        Sale.company_id == company_id,
        func.date(Sale.invoice_date) == today,
        Sale.is_cancelled == False
    ).scalar() or 0

    # TODAY SALES RETURNS
    today_returns = db.session.query(func.sum(SalesReturn.refund_amount)).join(
        Sale, SalesReturn.sale_id == Sale.id
    ).filter(
        Sale.company_id == company_id,
        func.date(SalesReturn.return_date) == today
    ).scalar() or 0

    today_sales = today_sales - today_returns

    # -------------------------------
    # MONTHLY SALES
    # -------------------------------
    month_sales = db.session.query(func.sum(Sale.total_amount)).filter(
        Sale.company_id == company_id,
        func.date(Sale.invoice_date) >= month_start,
        Sale.is_cancelled == False
    ).scalar() or 0

    month_returns = db.session.query(func.sum(SalesReturn.refund_amount)).join(
        Sale, SalesReturn.sale_id == Sale.id
    ).filter(
        Sale.company_id == company_id,
        func.date(SalesReturn.return_date) >= month_start
    ).scalar() or 0

    month_sales = month_sales - month_returns

    # -------------------------------
    # TOTAL PROFIT
    # -------------------------------
    total_profit = db.session.query(
        func.sum(
            (SaleItem.unit_price - Product.purchase_price) * SaleItem.quantity
        )
    ).join(Product, SaleItem.product_id == Product.id)\
     .join(Sale, SaleItem.sale_id == Sale.id)\
     .filter(
        Sale.company_id == company_id,
        Sale.is_cancelled == False
     ).scalar() or 0

    # SALES RETURN LOSS
    sales_return_loss = db.session.query(
        func.sum(SalesReturn.refund_amount)
    ).join(
        Sale, SalesReturn.sale_id == Sale.id
    ).filter(
        Sale.company_id == company_id
    ).scalar() or 0

    total_profit -= sales_return_loss

    # -------------------------------
    # TOTAL PURCHASES (WITH RETURNS)
    # -------------------------------
    total_purchases = db.session.query(
        func.sum(Purchase.total_amount)
    ).filter(
        Purchase.company_id == company_id
    ).scalar() or 0

    total_purchase_returns = db.session.query(
        func.sum(PurchaseReturn.credit_amount)
    ).join(
        Purchase, PurchaseReturn.purchase_id == Purchase.id
    ).filter(
        Purchase.company_id == company_id
    ).scalar() or 0

    net_purchases = total_purchases - total_purchase_returns

    # -------------------------------
    # LOW STOCK
    # -------------------------------
    low_stock = Product.query.filter(
        Product.company_id == company_id,
        Product.quantity <= Product.minimum_stock_level,
        Product.is_active == True
    ).count()

    # -------------------------------
    # EXPIRY MEDICINES
    # -------------------------------
    today_date = datetime.utcnow().date()

    expiring_30 = Product.query.filter(
        Product.company_id == company_id,
        Product.expiry_date >= today_date,
        Product.expiry_date <= today_date + timedelta(days=30),
        Product.is_active == True
    ).count()

    expiring_60 = Product.query.filter(
        Product.company_id == company_id,
        Product.expiry_date > today_date + timedelta(days=30),
        Product.expiry_date <= today_date + timedelta(days=60),
        Product.is_active == True
    ).count()

    expiring_90 = Product.query.filter(
        Product.company_id == company_id,
        Product.expiry_date > today_date + timedelta(days=60),
        Product.expiry_date <= today_date + timedelta(days=90),
        Product.is_active == True
    ).count()

    # -------------------------------
    # CUSTOMERS & SUPPLIERS
    # -------------------------------
    total_customers = Customer.query.filter(
        Customer.company_id == company_id,
        Customer.is_active == True
    ).count()

    total_suppliers = Supplier.query.filter(
        Supplier.company_id == company_id,
        Supplier.is_active == True
    ).count()

    # -------------------------------
    # RECENT SALES
    # -------------------------------
    recent_sales = Sale.query.filter(
        Sale.company_id == company_id,
        Sale.is_cancelled == False
    ).order_by(
        Sale.invoice_date.desc()
    ).limit(10).all()

    # -------------------------------
    # SALES GRAPH (7 DAYS)
    # -------------------------------
    sales_by_day = {}

    for i in range(7):
        day = today - timedelta(days=i)

        sales = db.session.query(func.sum(Sale.total_amount)).filter(
            Sale.company_id == company_id,
            func.date(Sale.invoice_date) == day,
            Sale.is_cancelled == False
        ).scalar() or 0

        returns = db.session.query(func.sum(SalesReturn.refund_amount)).join(
            Sale, SalesReturn.sale_id == Sale.id
        ).filter(
            Sale.company_id == company_id,
            func.date(SalesReturn.return_date) == day
        ).scalar() or 0

        sales_by_day[day.strftime('%Y-%m-%d')] = float(sales - returns)

    sales_by_day = dict(sorted(sales_by_day.items()))

    # -------------------------------
    # TOTAL STOCK VALUE
    # -------------------------------
    total_stock_value = db.session.query(
        func.sum(Product.quantity * Product.purchase_price)
    ).filter(
        Product.company_id == company_id
    ).scalar() or 0

    # -------------------------------
    # METRICS
    # -------------------------------
    metrics = {
        'today_sales': today_sales,
        'month_sales': month_sales,
        'total_profit': total_profit,
        'total_purchases': net_purchases,
        'low_stock_count': low_stock,
        'expiring_30': expiring_30,
        'expiring_60': expiring_60,
        'expiring_90': expiring_90,
        'total_customers': total_customers,
        'total_suppliers': total_suppliers,
        'total_stock_value': float(total_stock_value)
    }

    return render_template(
        'dashboard/index.html',
        company=current_user.company,
        metrics=metrics,
        recent_sales=recent_sales,
        sales_by_day=sales_by_day
    )