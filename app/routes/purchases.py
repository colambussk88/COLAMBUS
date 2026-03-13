from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app.utils import require_roles
from app.models import db, Purchase, PurchaseItem, PurchaseReturn, Product, Supplier, StockMovement
from datetime import datetime
from sqlalchemy import and_

purchases_bp = Blueprint('purchases', __name__, url_prefix='/purchases')


def generate_purchase_number():
    """Generate unique purchase number"""
    timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
    import random
    random_suffix = random.randint(1000, 9999)
    return f"PO{timestamp}{random_suffix}"


@purchases_bp.route('/')
@login_required
@require_roles('owner')
def purchases_list():
    """List all purchases"""
    company_id = current_user.company_id
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    supplier_id = request.args.get('supplier_id', type=int)
    status = request.args.get('status', '')
    
    query = Purchase.query.filter_by(company_id=company_id)
    
    if search:
        query = query.filter(
            db.or_(
                Purchase.purchase_number.ilike(f'%{search}%'),
                Purchase.supplier_invoice_number.ilike(f'%{search}%'),
                Supplier.supplier_name.ilike(f'%{search}%')
            )
        ).join(Supplier)
    
    if supplier_id:
        query = query.filter_by(supplier_id=supplier_id)
    
    if status:
        query = query.filter_by(payment_status=status)
    
    purchases = query.order_by(Purchase.purchase_date.desc()).paginate(page=page, per_page=20)
    suppliers = Supplier.query.filter_by(company_id=company_id, is_active=True).all()
    
    return render_template('purchases/purchases_list.html', 
                         purchases=purchases, 
                         search=search, 
                         supplier_id=supplier_id,
                         status=status,
                         suppliers=suppliers)


@purchases_bp.route('/add', methods=['GET', 'POST'])
@login_required
@require_roles('owner')
def add_purchase():
    """Add new purchase"""
    company_id = current_user.company_id
    suppliers = Supplier.query.filter_by(company_id=company_id, is_active=True).all()
    
    if request.method == 'POST':
        try:
            supplier_id = request.form.get('supplier_id', type=int)
            supplier = Supplier.query.get(supplier_id)
            if not supplier or supplier.company_id != company_id:
                flash('Invalid supplier.', 'danger')
                return redirect(url_for('purchases.add_purchase'))
            
            # Get items from form
            product_ids = request.form.getlist('product_id[]')
            quantities = request.form.getlist('quantity[]')
            unit_prices = request.form.getlist('unit_price[]')
            batch_numbers = request.form.getlist('batch_number[]')
            expiry_dates = request.form.getlist('expiry_date[]')
            tax_percentages = request.form.getlist('tax_percentage[]')
            
            if not product_ids:
                flash('Add at least one item to the purchase.', 'danger')
                return redirect(url_for('purchases.add_purchase'))
            
            # Validate and prepare items
            purchase_items = []
            subtotal = 0
            total_tax = 0
            
            for i, product_id in enumerate(product_ids):
                product = Product.query.get(product_id)
                if not product or product.company_id != company_id:
                    flash('Invalid product.', 'danger')
                    return redirect(url_for('purchases.add_purchase'))
                
                quantity = int(quantities[i])
                unit_price = float(unit_prices[i])
                batch_number = batch_numbers[i]
                expiry_date = datetime.strptime(expiry_dates[i], '%Y-%m-%d')
                tax_percentage = float(tax_percentages[i])
                
                tax_amount = (unit_price * quantity) * (tax_percentage / 100)
                item_total = (unit_price * quantity) + tax_amount
                
                purchase_items.append({
                    'product': product,
                    'quantity': quantity,
                    'unit_price': unit_price,
                    'batch_number': batch_number,
                    'expiry_date': expiry_date,
                    'tax_percentage': tax_percentage,
                    'tax_amount': tax_amount,
                    'item_total': item_total
                })
                
                subtotal += (unit_price * quantity)
                total_tax += tax_amount
            
            # Get discount and calculate total
            discount = float(request.form.get('discount', 0))
            total_amount = subtotal + total_tax - discount
            
            # Create purchase
            purchase = Purchase(
                company_id=company_id,
                supplier_id=supplier_id,
                purchase_number=generate_purchase_number(),
                purchase_date=datetime.utcnow(),
                supplier_invoice_number=request.form.get('supplier_invoice_number'),
                subtotal=subtotal,
                tax_amount=total_tax,
                discount_amount=discount,
                total_amount=total_amount,
                payment_status=request.form.get('payment_status', 'pending'),
                notes=request.form.get('notes')
            )
            
            db.session.add(purchase)
            db.session.flush()
            
            # Add items and update stock
            for item in purchase_items:
                purchase_item = PurchaseItem(
                    purchase_id=purchase.id,
                    product_id=item['product'].id,
                    batch_number=item['batch_number'],
                    expiry_date=item['expiry_date'],
                    quantity=item['quantity'],
                    unit_price=item['unit_price'],
                    tax_percentage=item['tax_percentage'],
                    tax_amount=item['tax_amount'],
                    total_amount=item['item_total']
                )
                db.session.add(purchase_item)
                
                # Update stock and product details
                product = item['product']
                product.quantity += item['quantity']
                product.batch_number = item['batch_number']
                product.expiry_date = item['expiry_date']
                product.purchase_price = item['unit_price']
                product.updated_date = datetime.utcnow()
                
                # Record stock movement
                movement = StockMovement(
                    product_id=product.id,
                    movement_type='purchase',
                    quantity=item['quantity'],
                    batch_number=item['batch_number'],
                    reference_id=purchase.id
                )
                db.session.add(movement)
            
            db.session.commit()
            
            flash('Purchase created successfully.', 'success')
            return redirect(url_for('purchases.purchase_detail', purchase_id=purchase.id))
        
        except Exception as e:
            db.session.rollback()
            flash(f'Failed to create purchase: {str(e)}', 'danger')
            return redirect(url_for('purchases.add_purchase'))
    
    products = Product.query.filter_by(company_id=company_id, is_active=True).all()
    return render_template('purchases/add_purchase.html', suppliers=suppliers, products=products)


@purchases_bp.route('/<int:purchase_id>')
@login_required
@require_roles('owner')
def purchase_detail(purchase_id):
    """View purchase details"""
    purchase = Purchase.query.get(purchase_id)
    if not purchase or purchase.company_id != current_user.company_id:
        flash('Purchase not found.', 'danger')
        return redirect(url_for('purchases.purchases_list'))
    
    return render_template('purchases/purchase_detail.html', purchase=purchase)


@purchases_bp.route('/<int:purchase_id>/edit', methods=['GET', 'POST'])
@login_required
@require_roles('owner')
def edit_purchase(purchase_id):
    """Edit purchase (only before completion)"""
    purchase = Purchase.query.get(purchase_id)
    if not purchase or purchase.company_id != current_user.company_id:
        flash('Purchase not found.', 'danger')
        return redirect(url_for('purchases.purchases_list'))
    
    company_id = current_user.company_id
    suppliers = Supplier.query.filter_by(company_id=company_id, is_active=True).all()
    products = Product.query.filter_by(company_id=company_id, is_active=True).all()
    
    if request.method == 'POST':
        try:
            purchase.supplier_invoice_number = request.form.get('supplier_invoice_number')
            purchase.payment_status = request.form.get('payment_status')
            purchase.notes = request.form.get('notes')
            purchase.updated_date = datetime.utcnow()
            
            db.session.commit()
            
            flash('Purchase updated successfully.', 'success')
            return redirect(url_for('purchases.purchase_detail', purchase_id=purchase_id))
        
        except Exception as e:
            db.session.rollback()
            flash(f'Failed to update purchase: {str(e)}', 'danger')
            return redirect(url_for('purchases.edit_purchase', purchase_id=purchase_id))
    
    return render_template('purchases/edit_purchase.html', 
                         purchase=purchase, 
                         suppliers=suppliers, 
                         products=products)

@purchases_bp.route('/<int:purchase_id>/record-payment', methods=['POST'])
@login_required
@require_roles('owner')
def record_payment(purchase_id):

    purchase = Purchase.query.get(purchase_id)

    if not purchase or purchase.company_id != current_user.company_id:
        flash('Purchase not found.', 'danger')
        return redirect(url_for('purchases.purchases_list'))

    try:

        purchase.payment_status = 'paid'
        purchase.payment_date = datetime.utcnow()
        purchase.updated_date = datetime.utcnow()

        db.session.commit()

        flash('Payment recorded successfully.', 'success')

        return redirect(url_for('purchases.purchase_detail', purchase_id=purchase_id))

    except Exception as e:

        db.session.rollback()

        flash(f'Error recording payment: {str(e)}', 'danger')

        return redirect(url_for('purchases.purchase_detail', purchase_id=purchase_id))

@purchases_bp.route('/returns')
@login_required
@require_roles('owner')
def returns_list():
    """List all purchase returns"""
    company_id = current_user.company_id
    returns = db.session.query(PurchaseReturn).join(Purchase).filter(
        Purchase.company_id == company_id
    ).order_by(PurchaseReturn.return_date.desc()).all()
    
    return render_template('purchases/returns_list.html', returns=returns)


@purchases_bp.route('/<int:purchase_id>/return', methods=['GET', 'POST'])
@login_required
@require_roles('owner')
def process_return(purchase_id):
    """Process purchase return"""

    purchase = Purchase.query.get(purchase_id)

    if not purchase or purchase.company_id != current_user.company_id:
        flash('Purchase not found.', 'danger')
        return redirect(url_for('purchases.purchases_list'))

    if request.method == 'POST':
        try:
            product_id = request.form.get('product_id', type=int)
            batch_number = request.form.get('batch_number')
            quantity = request.form.get('quantity', type=int)
            reason = request.form.get('reason')

            # Find purchase item
            purchase_item = PurchaseItem.query.filter_by(
                purchase_id=purchase_id,
                product_id=product_id,
                batch_number=batch_number
            ).first()

            if not purchase_item:
                flash('Invalid product for return.', 'danger')
                return redirect(url_for('purchases.process_return', purchase_id=purchase_id))

            # Check already returned quantity
            returned_qty = db.session.query(
                db.func.sum(PurchaseReturn.quantity)
            ).filter_by(
                purchase_id=purchase_id,
                product_id=product_id,
                batch_number=batch_number
            ).scalar() or 0

            available_qty = purchase_item.quantity - returned_qty

            if quantity > available_qty:
                flash(f'Cannot return more than {available_qty} items.', 'danger')
                return redirect(url_for('purchases.process_return', purchase_id=purchase_id))

            # Calculate credit amount
            unit_total = purchase_item.total_amount / purchase_item.quantity
            credit_amount = unit_total * quantity

            # Create return record
            return_record = PurchaseReturn(
                purchase_id=purchase_id,
                product_id=product_id,
                batch_number=batch_number,
                quantity=quantity,
                reason=reason,
                credit_amount=credit_amount
            )

            db.session.add(return_record)

            # -----------------------------
            # UPDATE PURCHASE TOTALS
            # -----------------------------

            # Reduce subtotal
            purchase.subtotal -= (purchase_item.unit_price * quantity)

            # Reduce tax amount proportionally
            tax_reduction = (purchase_item.tax_amount / purchase_item.quantity) * quantity
            purchase.tax_amount -= tax_reduction

            # Reduce total amount
            purchase.total_amount -= credit_amount

            purchase.updated_date = datetime.utcnow()

            # -----------------------------
            # UPDATE PRODUCT STOCK
            # -----------------------------

            product = Product.query.get(product_id)

            if product.quantity < quantity:
                flash('Stock not sufficient to process return.', 'danger')
                return redirect(url_for('purchases.process_return', purchase_id=purchase_id))

            product.quantity -= quantity
            product.updated_date = datetime.utcnow()

            # -----------------------------
            # RECORD STOCK MOVEMENT
            # -----------------------------

            movement = StockMovement(
                product_id=product_id,
                movement_type='purchase_return',
                quantity=-quantity,
                batch_number=batch_number,
                reference_id=purchase_id,
                reason=f'Returned to supplier: {reason}'
            )

            db.session.add(movement)

            db.session.commit()

            flash('Return processed successfully.', 'success')
            return redirect(url_for('purchases.purchase_detail', purchase_id=purchase_id))

        except Exception as e:
            db.session.rollback()
            flash(f'Failed to process return: {str(e)}', 'danger')
            return redirect(url_for('purchases.process_return', purchase_id=purchase_id))

    return render_template('purchases/process_return.html', purchase=purchase)
@purchases_bp.route('/reports/by-date')
@login_required
@require_roles('owner')
def report_by_date():
    """Purchase report by date"""
    company_id = current_user.company_id
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    query = Purchase.query.filter_by(company_id=company_id)
    
    if start_date and end_date:
        start = datetime.strptime(start_date, '%Y-%m-%d')
        end = datetime.strptime(end_date, '%Y-%m-%d')
        query = query.filter(and_(Purchase.purchase_date >= start, Purchase.purchase_date <= end))
    
    purchases = query.order_by(Purchase.purchase_date.desc()).all()
    
    return render_template('purchases/report_by_date.html', 
                         purchases=purchases, 
                         start_date=start_date, 
                         end_date=end_date)


@purchases_bp.route('/reports/by-supplier')
@login_required
@require_roles('owner')
def report_by_supplier():
    """Supplier-wise purchase report"""
    company_id = current_user.company_id
    supplier_id = request.args.get('supplier_id', type=int)
    
    suppliers = db.session.query(Supplier, 
                                 db.func.sum(Purchase.total_amount).label('total_purchased'),
                                 db.func.count(Purchase.id).label('purchase_count')).filter(
        Supplier.company_id == company_id
    ).outerjoin(Purchase).group_by(Supplier.id).all()
    
    selected_supplier = None
    purchases = []
    if supplier_id:
        selected_supplier = Supplier.query.get(supplier_id)
        if selected_supplier and selected_supplier.company_id == company_id:
            purchases = Purchase.query.filter_by(supplier_id=supplier_id).order_by(
                Purchase.purchase_date.desc()).all()
    
    return render_template('purchases/report_by_supplier.html', 
                         suppliers=suppliers, 
                         selected_supplier=selected_supplier,
                         purchases=purchases)


@purchases_bp.route('/reports/pending-payments')
@login_required
@require_roles('owner')
def report_pending_payments():
    """Pending payments report"""
    company_id = current_user.company_id
    purchases = Purchase.query.filter(
        and_(
            Purchase.company_id == company_id,
            Purchase.payment_status.in_(['pending', 'partial'])
        )
    ).order_by(Purchase.purchase_date.desc()).all()
    
    return render_template('purchases/report_pending_payments.html', purchases=purchases)