from flask import Blueprint, render_template
from flask_login import login_required, current_user
from app.models import db, Sale, Purchase, PurchaseReturn, Product, Customer, Supplier, StockMovement, SalesReturn
from datetime import datetime, timedelta
from sqlalchemy import func, and_

dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/dashboard')


@dashboard_bp.route('/')
@login_required
def dashboard():
    """Main dashboard"""

    company_id = current_user.company_id
    today = datetime.utcnow().date()
    month_start = datetime.utcnow().replace(day=1).date()

    # Today's sales
    today_sales = db.session.query(func.sum(Sale.total_amount)).filter(
        and_(
            Sale.company_id == company_id,
            func.date(Sale.invoice_date) == today,
            Sale.is_cancelled == False
        )
    ).scalar() or 0

    # Monthly sales
    month_sales = db.session.query(func.sum(Sale.total_amount)).filter(
        and_(
            Sale.company_id == company_id,
            func.date(Sale.invoice_date) >= month_start,
            Sale.is_cancelled == False
        )
    ).scalar() or 0

    # --------------------------------
    # TOTAL PROFIT (WITH SALES RETURNS)
    # --------------------------------
    total_profit = 0

    sales = Sale.query.filter(
        and_(Sale.company_id == company_id, Sale.is_cancelled == False)
    ).all()

    for sale in sales:
        for item in sale.items:
            product = item.product
            if product:
                profit_per_item = item.unit_price - product.purchase_price
                total_profit += profit_per_item * item.quantity

    # Deduct sales return loss
    sales_return_loss = db.session.query(
        func.sum(SalesReturn.refund_amount)
    ).join(
        Sale, SalesReturn.sale_id == Sale.id
    ).filter(
        Sale.company_id == company_id
    ).scalar() or 0

    total_profit -= sales_return_loss

    # --------------------------------
    # TOTAL PURCHASES (WITH RETURNS)
    # --------------------------------
    total_purchases = db.session.query(func.sum(Purchase.total_amount)).filter(
        Purchase.company_id == company_id
    ).scalar() or 0

    total_purchase_returns = db.session.query(func.sum(PurchaseReturn.credit_amount)).join(
        Purchase, PurchaseReturn.purchase_id == Purchase.id
    ).filter(
        Purchase.company_id == company_id
    ).scalar() or 0

    net_purchases = total_purchases - total_purchase_returns

    # Low stock count
    low_stock = Product.query.filter(
        and_(
            Product.company_id == company_id,
            Product.quantity <= Product.minimum_stock_level,
            Product.is_active == True
        )
    ).count()

    # Expiring medicines
    today_date = datetime.utcnow().date()
    expiry_30_days = today_date + timedelta(days=30)
    expiry_60_days = today_date + timedelta(days=60)
    expiry_90_days = today_date + timedelta(days=90)

    expiring_30 = Product.query.filter(
        and_(
            Product.company_id == company_id,
            Product.expiry_date.isnot(None),
            Product.expiry_date >= today_date,
            Product.expiry_date <= expiry_30_days,
            Product.is_active == True
        )
    ).count()

    expiring_60 = Product.query.filter(
        and_(
            Product.company_id == company_id,
            Product.expiry_date.isnot(None),
            Product.expiry_date > expiry_30_days,
            Product.expiry_date <= expiry_60_days,
            Product.is_active == True
        )
    ).count()

    expiring_90 = Product.query.filter(
        and_(
            Product.company_id == company_id,
            Product.expiry_date.isnot(None),
            Product.expiry_date > expiry_60_days,
            Product.expiry_date <= expiry_90_days,
            Product.is_active == True
        )
    ).count()

    # Total customers
    total_customers = Customer.query.filter(
        and_(Customer.company_id == company_id, Customer.is_active == True)
    ).count()

    # Total suppliers
    total_suppliers = Supplier.query.filter(
        and_(Supplier.company_id == company_id, Supplier.is_active == True)
    ).count()

    # Recent sales
    recent_sales = Sale.query.filter(
        and_(Sale.company_id == company_id, Sale.is_cancelled == False)
    ).order_by(Sale.invoice_date.desc()).limit(10).all()

    # Sales graph (last 7 days)
    sales_by_day = {}

    for i in range(7):
        day = today - timedelta(days=i)

        daily_total = db.session.query(func.sum(Sale.total_amount)).filter(
            and_(
                Sale.company_id == company_id,
                func.date(Sale.invoice_date) == day,
                Sale.is_cancelled == False
            )
        ).scalar() or 0

        sales_by_day[day.strftime('%Y-%m-%d')] = float(daily_total)

    sales_by_day = dict(sorted(sales_by_day.items()))

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
    }

    # Total stock value
    total_stock_value = db.session.query(
        func.sum(Product.quantity * Product.purchase_price)
    ).filter(
        Product.company_id == company_id
    ).scalar() or 0

    metrics['total_stock_value'] = float(total_stock_value)

    return render_template(
        'dashboard/index.html',
        company=current_user.company,
        metrics=metrics,
        recent_sales=recent_sales,
        sales_by_day=sales_by_day
    )