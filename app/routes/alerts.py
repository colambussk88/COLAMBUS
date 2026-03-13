from flask import Blueprint, render_template, jsonify
from flask_login import login_required, current_user
from app.models import db, Alert, Product, Sale, Purchase, Customer, Supplier
from datetime import datetime, timedelta
from sqlalchemy import and_, or_

alerts_bp = Blueprint('alerts', __name__, url_prefix='/alerts')


def generate_alerts(company_id):
    """Generate alerts for the company"""
    today = datetime.utcnow().date()
    alert_created = False
    
    # Clear old alerts
    Alert.query.filter_by(company_id=company_id).delete()
    db.session.commit()
    
    # Low stock alerts
    low_stock_products = Product.query.filter(
        and_(
            Product.company_id == company_id,
            Product.quantity <= Product.minimum_stock_level,
            Product.is_active == True
        )
    ).all()
    
    for product in low_stock_products:
        alert = Alert(
            company_id=company_id,
            alert_type='low_stock',
            product_id=product.id,
            title=f'Low Stock: {product.product_name}',
            message=f'Stock level ({product.quantity}) is below minimum ({product.minimum_stock_level})',
            severity='warning'
        )
        db.session.add(alert)
        alert_created = True
    
    # Expiry alerts
    expiry_30 = today + timedelta(days=30)
    expiry_60 = today + timedelta(days=60)
    expiry_90 = today + timedelta(days=90)
    
    # 90 days expiry (include already expired items)
    expiring_90 = Product.query.filter(
        and_(
            Product.company_id == company_id,
            Product.expiry_date.isnot(None),
            Product.expiry_date <= expiry_90,
            Product.is_active == True
        )
    ).all()
    
    for product in expiring_90:
        try:
            days_left = (product.expiry_date.date() - today).days
        except Exception:
            days_left = None

        if days_left is None:
            severity = 'info'
            msg = f'{product.product_name} has an unknown expiry date.'
            title = f'Expiry Notice: {product.product_name}'
        else:
            if days_left < 0:
                severity = 'critical'
                title = f'Expired: {product.product_name}'
                msg = f'{product.product_name} expired {( -days_left )} days ago ({product.expiry_date.strftime("%Y-%m-%d")})'
            else:
                severity = 'critical' if days_left <= 7 else 'warning' if days_left <= 30 else 'info'
                title = f'Expires Soon: {product.product_name}'
                msg = f'{product.product_name} expires in {days_left} days ({product.expiry_date.strftime("%Y-%m-%d")})'

        alert = Alert(
            company_id=company_id,
            alert_type='expiry',
            product_id=product.id,
            title=title,
            message=msg,
            severity=severity
        )
        db.session.add(alert)
        alert_created = True
    
    # Pending customer payments
    pending_customers = Customer.query.filter(
        and_(
            Customer.company_id == company_id,
            Customer.current_balance > 0
        )
    ).all()
    
    for customer in pending_customers:
        alert = Alert(
            company_id=company_id,
            alert_type='payment_due',
            title=f'Payment Due: {customer.customer_name}',
            message=f'Outstanding balance: ₹{customer.current_balance:.2f}',
            severity='info'
        )
        db.session.add(alert)
        alert_created = True
    
    # Pending supplier payments
    pending_purchases = Purchase.query.filter(
        and_(
            Purchase.company_id == company_id,
            Purchase.payment_status.in_(['pending', 'partial'])
        )
    ).all()
    
    for purchase in pending_purchases:
        alert = Alert(
            company_id=company_id,
            alert_type='payment_pending',
            title=f'Supplier Payment Pending: {purchase.supplier.supplier_name}',
            message=f'Payment due for PO {purchase.purchase_number}: ₹{purchase.total_amount:.2f}',
            severity='info'
        )
        db.session.add(alert)
        alert_created = True
    
    if alert_created:
        db.session.commit()


@alerts_bp.route('/')
@login_required
def alerts():
    """View alerts"""
    company_id = current_user.company_id
    
    # Generate current alerts
    generate_alerts(company_id)
    
    # Get all alerts
    all_alerts = Alert.query.filter_by(company_id=company_id).order_by(
        Alert.created_date.desc()
    ).all()
    
    # Group by severity
    critical_alerts = [a for a in all_alerts if a.severity == 'critical']
    warning_alerts = [a for a in all_alerts if a.severity == 'warning']
    info_alerts = [a for a in all_alerts if a.severity == 'info']
    
    return render_template('alerts/index.html',
                         critical_alerts=critical_alerts,
                         warning_alerts=warning_alerts,
                         info_alerts=info_alerts,
                         all_alerts=all_alerts)


@alerts_bp.route('/api/count')
@login_required
def api_alert_count():
    """Get alert counts"""
    company_id = current_user.company_id
    
    # Generate current alerts
    generate_alerts(company_id)
    
    total = Alert.query.filter_by(company_id=company_id).count()
    critical = Alert.query.filter_by(company_id=company_id, severity='critical').count()
    warning = Alert.query.filter_by(company_id=company_id, severity='warning').count()
    
    return jsonify({
        'total': total,
        'critical': critical,
        'warning': warning
    })


@alerts_bp.route('/<int:alert_id>/mark-read', methods=['POST'])
@login_required
def mark_alert_read(alert_id):
    """Mark alert as read"""
    alert = Alert.query.get(alert_id)
    if not alert or alert.company_id != current_user.company_id:
        return jsonify({'success': False, 'message': 'Alert not found'}), 404
    
    try:
        alert.is_read = True
        db.session.commit()
        return jsonify({'success': True, 'message': 'Alert marked as read'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


@alerts_bp.route('/<int:alert_id>/delete', methods=['POST'])
@login_required
def delete_alert(alert_id):
    """Delete alert"""
    alert = Alert.query.get(alert_id)
    if not alert or alert.company_id != current_user.company_id:
        return jsonify({'success': False, 'message': 'Alert not found'}), 404
    
    try:
        db.session.delete(alert)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Alert deleted'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500