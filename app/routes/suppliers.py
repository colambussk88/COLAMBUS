from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app.models import db, Supplier, Purchase
from datetime import datetime
from sqlalchemy import and_, func

suppliers_bp = Blueprint('suppliers', __name__, url_prefix='/suppliers')


@suppliers_bp.route('/')
@login_required
def suppliers_list():
    """List all suppliers"""
    company_id = current_user.company_id
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    
    query = Supplier.query.filter(
        and_(Supplier.company_id == company_id, Supplier.is_active == True)
    )
    
    if search:
        query = query.filter(
            db.or_(
                Supplier.supplier_name.ilike(f'%{search}%'),
                Supplier.phone.ilike(f'%{search}%'),
                Supplier.email.ilike(f'%{search}%')
            )
        )
    
    suppliers = query.order_by(Supplier.supplier_name).paginate(page=page, per_page=20)
    
    return render_template('suppliers/suppliers_list.html', suppliers=suppliers, search=search)


@suppliers_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add_supplier():
    """Add new supplier"""
    if request.method == 'POST':
        try:
            supplier = Supplier(
                company_id=current_user.company_id,
                supplier_name=request.form.get('supplier_name'),
                contact_person=request.form.get('contact_person'),
                phone=request.form.get('phone'),
                email=request.form.get('email'),
                address=request.form.get('address'),
                gst_number=request.form.get('gst_number'),
                payment_terms=request.form.get('payment_terms'),
                notes=request.form.get('notes')
            )
            
            db.session.add(supplier)
            db.session.commit()
            
            flash('Supplier added successfully.', 'success')
            return redirect(url_for('suppliers.supplier_detail', supplier_id=supplier.id))
        
        except Exception as e:
            db.session.rollback()
            flash(f'Failed to add supplier: {str(e)}', 'danger')
            return redirect(url_for('suppliers.add_supplier'))
    
    return render_template('suppliers/add_supplier.html')


@suppliers_bp.route('/<int:supplier_id>')
@login_required
def supplier_detail(supplier_id):
    """Supplier detail view"""
    supplier = Supplier.query.get(supplier_id)
    if not supplier or supplier.company_id != current_user.company_id:
        flash('Supplier not found.', 'danger')
        return redirect(url_for('suppliers.suppliers_list'))
    
    # Get recent purchases
    purchases = Purchase.query.filter_by(supplier_id=supplier_id).order_by(
        Purchase.purchase_date.desc()).limit(20).all()
    
    # Calculate totals
    total_purchased = db.session.query(func.sum(Purchase.total_amount)).filter_by(
        supplier_id=supplier_id).scalar() or 0
    pending_balance = db.session.query(func.sum(Purchase.total_amount)).filter(
        and_(Purchase.supplier_id == supplier_id, Purchase.payment_status != 'paid')
    ).scalar() or 0
    
    return render_template('suppliers/supplier_detail.html', 
                         supplier=supplier, 
                         purchases=purchases,
                         total_purchased=total_purchased,
                         pending_balance=pending_balance)


@suppliers_bp.route('/<int:supplier_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_supplier(supplier_id):
    """Edit supplier"""
    supplier = Supplier.query.get(supplier_id)
    if not supplier or supplier.company_id != current_user.company_id:
        flash('Supplier not found.', 'danger')
        return redirect(url_for('suppliers.suppliers_list'))
    
    if request.method == 'POST':
        try:
            supplier.supplier_name = request.form.get('supplier_name', supplier.supplier_name)
            supplier.contact_person = request.form.get('contact_person', supplier.contact_person)
            supplier.phone = request.form.get('phone', supplier.phone)
            supplier.email = request.form.get('email', supplier.email)
            supplier.address = request.form.get('address', supplier.address)
            supplier.gst_number = request.form.get('gst_number', supplier.gst_number)
            supplier.payment_terms = request.form.get('payment_terms', supplier.payment_terms)
            supplier.notes = request.form.get('notes', supplier.notes)
            supplier.updated_date = datetime.utcnow()
            
            db.session.commit()
            
            flash('Supplier updated successfully.', 'success')
            return redirect(url_for('suppliers.supplier_detail', supplier_id=supplier_id))
        
        except Exception as e:
            db.session.rollback()
            flash(f'Failed to update supplier: {str(e)}', 'danger')
            return redirect(url_for('suppliers.edit_supplier', supplier_id=supplier_id))
    
    return render_template('suppliers/edit_supplier.html', supplier=supplier)


@suppliers_bp.route('/<int:supplier_id>/delete', methods=['POST'])
@login_required
def delete_supplier(supplier_id):
    """Soft delete supplier"""
    supplier = Supplier.query.get(supplier_id)
    if not supplier or supplier.company_id != current_user.company_id:
        flash('Supplier not found.', 'danger')
        return redirect(url_for('suppliers.suppliers_list'))
    
    try:
        supplier.is_active = False
        supplier.updated_date = datetime.utcnow()
        db.session.commit()
        
        flash('Supplier deleted successfully.', 'success')
        return redirect(url_for('suppliers.suppliers_list'))
    
    except Exception as e:
        db.session.rollback()
        flash(f'Failed to delete supplier: {str(e)}', 'danger')
        return redirect(url_for('suppliers.supplier_detail', supplier_id=supplier_id))


@suppliers_bp.route('/ledger')
@login_required
def supplier_ledger():
    """Supplier ledger report"""
    company_id = current_user.company_id
    
    suppliers = db.session.query(
        Supplier,
        func.sum(Purchase.total_amount).label('total_purchased'),
        func.sum(db.case(
            (Purchase.payment_status != 'paid', Purchase.total_amount),
            else_=0
        )).label('pending_balance')
    ).filter(
        Supplier.company_id == company_id
    ).outerjoin(Purchase).group_by(Supplier.id).all()
    
    return render_template('suppliers/ledger.html', suppliers=suppliers)
