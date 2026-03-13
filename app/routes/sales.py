from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_login import login_required, current_user
from app.models import db, Sale, SaleItem, Product, Customer, SalesReturn, StockMovement
from datetime import datetime
from sqlalchemy import and_, func
import io
import os
from reportlab.lib.pagesizes import A4, letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, Image, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, mm
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT

sales_bp = Blueprint('sales', __name__, url_prefix='/sales')


def generate_invoice_number():
    """Generate unique invoice number"""
    timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
    import random
    random_suffix = random.randint(1000, 9999)
    return f"INV{timestamp}{random_suffix}"


@sales_bp.route('/pos')
@login_required
def pos():
    """POS interface"""
    customers = Customer.query.filter_by(company_id=current_user.company_id, is_active=True).all()
    # Provide doctors for selection at checkout
    from app.models import Doctor
    doctors = Doctor.query.filter_by(company_id=current_user.company_id).order_by(Doctor.name).all()
    return render_template('sales/pos.html', customers=customers, doctors=doctors)


@sales_bp.route('/api/products/search')
@login_required
def search_products():
    """Search products by name or barcode"""
    query = request.args.get('q', '').strip()
    if len(query) < 2:
        return jsonify([])
    
    company_id = current_user.company_id
    products = Product.query.filter(
        and_(
            Product.company_id == company_id,
            Product.is_active == True,
            db.or_(
                Product.product_name.ilike(f'%{query}%'),
                Product.barcode.ilike(f'%{query}%'),
                Product.sku.ilike(f'%{query}%')
            )
        )
    ).limit(10).all()
    
    return jsonify([{
        'id': p.id,
        'name': p.product_name,
        'barcode': p.barcode,
        'sku': p.sku,
        'price': p.selling_price,
        'mrp': p.mrp,
        'quantity': p.quantity,
        'tax_percentage': p.tax_percentage,
        'batch_number': p.batch_number
    } for p in products])


@sales_bp.route('/checkout', methods=['POST'])
@login_required
def checkout():
    """Process checkout and create invoice"""
    try:
        data = request.json
        items = data.get('items', [])
        customer_id = data.get('customer_id')
        customer_name = data.get('customer_name', '')
        customer_phone = data.get('customer_phone', '')
        payment_method = data.get('payment_method', 'cash')
        discount = float(data.get('discount', 0))
        include_tax = data.get('include_tax', True)
        notes = data.get('notes', '')
        
        if not items:
            return jsonify({'success': False, 'message': 'Cart is empty'}), 400
        
        company_id = current_user.company_id
        
        # Validate and prepare items
        sale_items = []
        subtotal = 0
        total_tax = 0
        
        for item in items:
            # Accept product identifier from front-end as either 'product_id' or 'id'
            pid = item.get('product_id') or item.get('id')
            try:
                pid = int(pid)
            except Exception:
                pid = None

            product = Product.query.get(pid) if pid else None
            if not product or product.company_id != company_id:
                return jsonify({'success': False, 'message': 'Invalid product'}), 400
            
            quantity = int(item.get('quantity', 1))
            if product.quantity < quantity:
                return jsonify({'success': False, 'message': f'Insufficient stock for {product.product_name}'}), 400
            
            unit_price = float(item.get('price', product.selling_price))
            item_discount = float(item.get('discount', 0))
            
            tax_amount = 0
            if include_tax:
                tax_amount = (unit_price * quantity - item_discount) * (product.tax_percentage / 100)
            
            item_total = (unit_price * quantity) - item_discount + tax_amount
            
            sale_items.append({
                'product': product,
                'quantity': quantity,
                'unit_price': unit_price,
                'tax_percentage': product.tax_percentage,
                'tax_amount': tax_amount,
                'item_discount': item_discount,
                'item_total': item_total,
                'batch_number': product.batch_number
            })
            
            subtotal += (unit_price * quantity) - item_discount
            total_tax += tax_amount
        
        # Calculate total
        total_amount = subtotal + total_tax - discount
        if total_amount < 0:
            total_amount = 0
        
        # Create sale
        sale = Sale(
            company_id=company_id,
            customer_id=customer_id,
            invoice_number=generate_invoice_number(),
            invoice_date=datetime.utcnow(),
            customer_name=customer_name,
            customer_phone=customer_phone,
            doctor_id=data.get('doctor_id'),
            subtotal=subtotal,
            tax_amount=total_tax,
            discount_amount=discount,
            total_amount=total_amount,
            payment_method=payment_method,
            payment_status='paid' if payment_method != 'credit' else 'pending',
            notes=notes
        )
        
        db.session.add(sale)
        db.session.flush()
        
        # Add items and deduct stock
        for item in sale_items:
            sale_item = SaleItem(
                sale_id=sale.id,
                product_id=item['product'].id,
                batch_number=item['batch_number'],
                quantity=item['quantity'],
                unit_price=item['unit_price'],
                tax_percentage=item['tax_percentage'],
                tax_amount=item['tax_amount'],
                discount_amount=item['item_discount'],
                total_amount=item['item_total']
            )
            db.session.add(sale_item)
            
            # Deduct stock
            product = item['product']
            product.quantity -= item['quantity']
            product.updated_date = datetime.utcnow()
            
            # Record stock movement
            movement = StockMovement(
                product_id=product.id,
                movement_type='sale',
                quantity=-item['quantity'],
                batch_number=item['batch_number'],
                reference_id=sale.id
            )
            db.session.add(movement)
        
        # Update customer balance if credit sale
        if customer_id and payment_method == 'credit':
            customer = Customer.query.get(customer_id)
            if customer:
                customer.current_balance += total_amount
        # Associate consulting doctor if provided
        try:
            doc_id = data.get('doctor_id')
            if doc_id:
                sale.doctor_id = int(doc_id)
        except Exception:
            pass
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Sale completed successfully',
            'invoice_number': sale.invoice_number,
            'sale_id': sale.id,
            'total_amount': total_amount
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


@sales_bp.route('/invoices')
@login_required
def invoices_list():
    """List all invoices"""
    company_id = current_user.company_id
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    
    query = Sale.query.filter_by(company_id=company_id)
    
    if search:
        query = query.filter(
            db.or_(
                Sale.invoice_number.ilike(f'%{search}%'),
                Sale.customer_name.ilike(f'%{search}%'),
                Sale.customer_phone.ilike(f'%{search}%')
            )
        )
    
    sales = query.order_by(Sale.invoice_date.desc()).paginate(page=page, per_page=20)
    
    return render_template('sales/invoices_list.html', sales=sales, search=search)


@sales_bp.route('/invoices/<int:sale_id>')
@login_required
def invoice_detail(sale_id):
    """View invoice"""
    sale = Sale.query.get(sale_id)
    if not sale or sale.company_id != current_user.company_id:
        flash('Invoice not found.', 'danger')
        return redirect(url_for('sales.invoices_list'))
    
    return render_template('sales/invoice_detail.html', sale=sale)


@sales_bp.route('/invoices/<int:sale_id>/print')
@login_required
def print_invoice(sale_id):
    """Print invoice"""
    sale = Sale.query.get(sale_id)
    if not sale or sale.company_id != current_user.company_id:
        return jsonify({'success': False, 'message': 'Invoice not found'}), 404
    
    return render_template('sales/print_invoice.html', sale=sale)


@sales_bp.route('/invoices/<int:sale_id>/pdf')
@login_required
def download_invoice_pdf(sale_id):
    """Download invoice as PDF with professional formatting and logo"""
    sale = Sale.query.get(sale_id)
    if not sale or sale.company_id != current_user.company_id:
        return jsonify({'success': False, 'message': 'Invoice not found'}), 404
    
    try:
        # Create PDF buffer (A4) and layout
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            topMargin=0.4*inch,
            bottomMargin=0.4*inch,
            leftMargin=0.5*inch,
            rightMargin=0.5*inch
        )
        
        elements = []
        styles = getSampleStyleSheet()
        
        # Define custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1a3a52'),
            alignment=TA_CENTER,
            spaceAfter=6,
            fontName='Helvetica-Bold'
        )
        
        subtitle_style = ParagraphStyle(
            'Subtitle',
            parent=styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#666666'),
            alignment=TA_CENTER,
            spaceAfter=12
        )
        
        section_header_style = ParagraphStyle(
            'SectionHeader',
            parent=styles['Heading2'],
            fontSize=11,
            textColor=colors.HexColor('#1a3a52'),
            spaceAfter=6,
            fontName='Helvetica-Bold',
            borderColor=colors.HexColor('#1a3a52'),
            borderWidth=1,
            borderPadding=4
        )
        
        # Helper to format company info and logo
        header_data = []
        company = sale.company
        # Compose company contact/address
        comp_lines = []
        if getattr(company, 'address', None):
            addr = company.address
            parts = [addr]
            if getattr(company, 'city', None):
                parts.append(company.city)
            if getattr(company, 'state', None):
                parts.append(company.state)
            if getattr(company, 'country', None):
                parts.append(company.country)
            if getattr(company, 'postal_code', None):
                parts.append(company.postal_code)
            comp_lines.append(', '.join([p for p in parts if p]))
        if getattr(company, 'phone', None):
            comp_lines.append(f"Phone: {company.phone}")
        if getattr(company, 'email', None):
            comp_lines.append(f"Email: {company.email}")

        comp_info = '<br/>'.join(comp_lines)

        # Resolve logo path relative to static folder if needed
        logo_path = company.logo_path
        logo_full = None
        if logo_path:
            candidate = os.path.join(os.getcwd(), 'app', 'static', logo_path)
            if os.path.exists(candidate):
                logo_full = candidate

        if logo_full:
            try:
                img = Image(logo_full, width=1.0*inch, height=1.0*inch)
                header_data.append([img, Paragraph(f"<b>{company.company_name}</b><br/>{comp_info}", subtitle_style)])
            except:
                header_data.append([Paragraph(f"<b>{company.company_name}</b><br/>{comp_info}", subtitle_style)])
        else:
            header_data.append([Paragraph(f"<b>{company.company_name}</b><br/>{comp_info}", subtitle_style)])

        header_table = Table(header_data, colWidths=[1.2*inch, doc.width-1.2*inch])
        header_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ALIGN', (0, 0), (0, -1), 'CENTER'),
        ]))
        elements.append(header_table)
        elements.append(Spacer(1, 0.15*inch))
        
        # Invoice Title
        elements.append(Paragraph(f"<b>INVOICE</b>", title_style))
        
        # Invoice and Date Info
        invoice_info_data = [
            [Paragraph(f"<b>Invoice #:</b> {sale.invoice_number}", styles['Normal']),
             Paragraph(f"<b>Date:</b> {sale.invoice_date.strftime('%d-%m-%Y')}", styles['Normal']),
             Paragraph(f"<b>Time:</b> {sale.invoice_date.strftime('%H:%M:%S')}", styles['Normal'])],
        ]
        
        invoice_info_table = Table(invoice_info_data, colWidths=[2.5*inch, 2*inch, 2*inch])
        invoice_info_table.setStyle(TableStyle([
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#333333')),
        ]))
        elements.append(invoice_info_table)
        elements.append(Spacer(1, 0.15*inch))
        
        # Customer and Company Details
        bill_to = f"<b>Bill To:</b><br/>{sale.customer_name or 'Walk-in Customer'}"
        if sale.customer_phone:
            bill_to += f"<br/>Phone: {sale.customer_phone}"
        if sale.customer and getattr(sale.customer, 'address', None):
            bill_to += f"<br/>{sale.customer.address}"
        
        bill_ship_data = [
            [Paragraph(bill_to, styles['Normal']),
             Paragraph(f"<b>Sold By:</b><br/>{company.company_name}", styles['Normal'])]
        ]
        
        bill_ship_table = Table(bill_ship_data, colWidths=[3.5*inch, 3.5*inch])
        bill_ship_table.setStyle(TableStyle([
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))
        elements.append(bill_ship_table)
        elements.append(Spacer(1, 0.2*inch))
        
        # Items Table
        item_data = [['Item', 'Qty', 'Unit Price', 'Discount', 'Tax', 'Amount']]
        
        for item in sale.items:
            item_data.append([
                Paragraph(f"<b>{item.product.product_name}</b><br/><font size=7>SKU: {item.product.sku}</font>", styles['Normal']),
                Paragraph(str(item.quantity), ParagraphStyle('Normal', parent=styles['Normal'], alignment=TA_CENTER)),
                Paragraph(f"₹{item.unit_price:.2f}", ParagraphStyle('Normal', parent=styles['Normal'], alignment=TA_RIGHT)),
                Paragraph(f"₹{item.discount_amount:.2f}", ParagraphStyle('Normal', parent=styles['Normal'], alignment=TA_RIGHT)),
                Paragraph(f"₹{item.tax_amount:.2f}", ParagraphStyle('Normal', parent=styles['Normal'], alignment=TA_RIGHT)),
                Paragraph(f"<b>₹{item.total_amount:.2f}</b>", ParagraphStyle('Normal', parent=styles['Normal'], alignment=TA_RIGHT))
            ])
        
        items_table = Table(item_data, colWidths=[2.8*inch, 0.6*inch, 1*inch, 0.8*inch, 0.8*inch, 1*inch])
        items_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a3a52')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('TOPPADDING', (0, 0), (-1, 0), 8),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor('#333333')),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#cccccc')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9f9f9')]),
            ('ALIGN', (1, 1), (-1, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 1), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
        ]))
        
        elements.append(items_table)
        elements.append(Spacer(1, 0.15*inch))
        
        # Summary Section
        summary_data = [
            ['', 'Subtotal', f"₹{sale.subtotal:.2f}"],
            ['', 'Tax Amount', f"₹{sale.tax_amount:.2f}"],
            ['', 'Discount', f"-₹{sale.discount_amount:.2f}"],
            ['', '', ''],
            ['', 'TOTAL AMOUNT', f"₹{sale.total_amount:.2f}"],
        ]
        
        summary_table = Table(summary_data, colWidths=[3.5*inch, 2*inch, 1.5*inch])
        summary_table.setStyle(TableStyle([
            ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
            ('FONTNAME', (1, 0), (-1, 3), 'Helvetica-Bold'),
            ('FONTSIZE', (1, 0), (-1, 3), 9),
            ('FONTSIZE', (1, 4), (-1, 4), 11),
            ('FONTNAME', (1, 4), (-1, 4), 'Helvetica-Bold'),
            ('BACKGROUND', (1, 4), (-1, 4), colors.HexColor('#1a3a52')),
            ('TEXTCOLOR', (1, 4), (-1, 4), colors.whitesmoke),
            ('TOPPADDING', (1, 4), (-1, 4), 8),
            ('BOTTOMPADDING', (1, 4), (-1, 4), 8),
            ('LINEABOVE', (1, 3), (-1, 3), 0.5, colors.HexColor('#cccccc')),
            ('LINEABOVE', (1, 4), (-1, 4), 1, colors.HexColor('#1a3a52')),
            ('RIGHTPADDING', (2, 0), (2, -1), 10),
        ]))
        
        elements.append(summary_table)
        elements.append(Spacer(1, 0.2*inch))
        
        # Payment Details
        payment_data = [
            ['Payment Method:', sale.payment_method.upper()],
            ['Payment Status:', sale.payment_status.upper()],
        ]
        
        if sale.notes:
            payment_data.append(['Notes:', sale.notes])
        
        payment_table = Table(payment_data, colWidths=[1.5*inch, 5.5*inch])
        payment_table.setStyle(TableStyle([
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))
        elements.append(payment_table)
        
        elements.append(Spacer(1, 0.3*inch))
        
        # Footer
        footer_style = ParagraphStyle(
            'Footer',
            parent=styles['Normal'],
            fontSize=8,
            textColor=colors.HexColor('#999999'),
            alignment=TA_CENTER
        )
        
        elements.append(Paragraph(
            "Thank you for your business!<br/>This is a computer-generated invoice. No signature required.",
            footer_style
        ))

        # Support store copy option: include both customer and merchant copies on same A4 page
        include_store_copy = request.args.get('store_copy', '1') not in ('0', 'false', 'False')

        # Build content for one invoice copy; we'll re-use by cloning elements fragments
        # For simplicity, rebuild elements per copy to ensure separation
        def build_invoice_copy(copy_label=None):
            part = []
            # header
            part.append(header_table)
            part.append(Spacer(1, 0.08*inch))
            if copy_label:
                part.append(Paragraph(f"<b>{copy_label}</b>", subtitle_style))
                part.append(Spacer(1, 0.05*inch))

            part.append(Paragraph(f"<b>INVOICE</b>", title_style))
            part.append(Spacer(1, 0.05*inch))
            part.append(invoice_info_table)
            part.append(Spacer(1, 0.06*inch))
            part.append(bill_ship_table)
            part.append(Spacer(1, 0.06*inch))
            part.append(items_table)
            part.append(Spacer(1, 0.06*inch))
            part.append(summary_table)
            part.append(Spacer(1, 0.04*inch))
            part.append(payment_table)
            part.append(Spacer(1, 0.04*inch))
            part.append(Paragraph(
                "Thank you for your business!<br/>This is a computer-generated invoice. No signature required.",
                footer_style
            ))
            return part

        # Assemble page: customer copy on top
        elements = build_invoice_copy('Customer Copy')
        if include_store_copy:
            # small separator line then store copy
            elements.append(Spacer(1, 0.2*inch))
            elements.append(Table([['']], colWidths=[doc.width], style=[('LINEABOVE', (0,0), (-1,0), 0.5, colors.HexColor('#cccccc'))]))
            elements.append(Spacer(1, 0.1*inch))
            elements.extend(build_invoice_copy('Merchant Copy'))

        doc.build(elements)
        buffer.seek(0)
        
        return send_file(
            buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f"invoice_{sale.invoice_number}.pdf"
        )
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@sales_bp.route('/invoices/<int:sale_id>/cancel', methods=['POST'])
@login_required
def cancel_invoice(sale_id):
    """Cancel invoice"""
    sale = Sale.query.get(sale_id)
    if not sale or sale.company_id != current_user.company_id:
        flash('Invoice not found.', 'danger')
        return redirect(url_for('sales.invoices_list'))
    
    if sale.is_cancelled:
        flash('Invoice is already cancelled.', 'info')
        return redirect(url_for('sales.invoice_detail', sale_id=sale_id))
    
    try:
        reason = request.form.get('cancellation_reason', '')
        
        # Reverse stock movements
        for item in sale.items:
            item.product.quantity += item.quantity
            item.product.updated_date = datetime.utcnow()
            
            # Record reversal movement
            movement = StockMovement(
                product_id=item.product_id,
                movement_type='sale',
                quantity=item.quantity,
                batch_number=item.batch_number,
                reason=f'Cancelled invoice {sale.invoice_number}'
            )
            db.session.add(movement)
        
        # Update customer balance if credit sale
        if sale.customer_id and sale.payment_method == 'credit':
            customer = sale.customer
            if customer:
                customer.current_balance -= sale.total_amount
        
        sale.is_cancelled = True
        sale.cancellation_reason = reason
        sale.updated_date = datetime.utcnow()
        
        db.session.commit()
        flash('Invoice cancelled successfully.', 'success')
        return redirect(url_for('sales.invoice_detail', sale_id=sale_id))
    
    except Exception as e:
        db.session.rollback()
        flash(f'Failed to cancel invoice: {str(e)}', 'danger')
        return redirect(url_for('sales.invoice_detail', sale_id=sale_id))


@sales_bp.route('/returns')
@login_required
def sales_returns_list():
    """List all sales returns"""
    company_id = current_user.company_id
    returns = db.session.query(SalesReturn).join(Sale).filter(
        Sale.company_id == company_id
    ).order_by(SalesReturn.return_date.desc()).all()
    
    return render_template('sales/returns_list.html', returns=returns)


@sales_bp.route('/invoices/<int:sale_id>/return', methods=['GET', 'POST'])
@login_required
def process_return(sale_id):
    """Process sales return"""
    sale = Sale.query.get(sale_id)
    if not sale or sale.company_id != current_user.company_id:
        flash('Invoice not found.', 'danger')
        return redirect(url_for('sales.invoices_list'))
    
    if request.method == 'POST':
        try:
            is_full_return = request.form.get('return_type') == 'full'
            reason = request.form.get('return_reason', '')
            refund_mode = request.form.get('refund_mode', 'cash')
            
            if is_full_return:
                # Full return
                return_credit = sale.total_amount
                for item in sale.items:
                    item.product.quantity += item.quantity
                    item.product.updated_date = datetime.utcnow()
            else:
                # Partial return
                product_id = request.form.get('product_id', type=int)
                quantity = request.form.get('quantity', type=int)
                
                # Find the sale item
                sale_item = SaleItem.query.filter_by(sale_id=sale_id, product_id=product_id).first()
                if not sale_item or sale_item.quantity < quantity:
                    flash('Invalid return quantity.', 'danger')
                    return redirect(url_for('sales.process_return', sale_id=sale_id))
                
                # Return stock
                product = sale_item.product
                product.quantity += quantity
                product.updated_date = datetime.utcnow()
                
                # Calculate refund amount
                return_credit = (sale_item.unit_price * quantity) + (sale_item.tax_amount * quantity / sale_item.quantity)
            
            # Create return record
            credit_note = SalesReturn(
                sale_id=sale_id,
                credit_note_number=generate_invoice_number().replace('INV', 'CN'),
                return_date=datetime.utcnow(),
                quantity=sum(item.quantity for item in sale.items) if is_full_return else quantity,
                is_full_return=is_full_return,
                reason=reason,
                refund_amount=return_credit,
                refund_mode=refund_mode
            )
            
            db.session.add(credit_note)
            
            # Update customer balance if applicable
            if sale.customer_id and sale.payment_method == 'credit':
                sale.customer.current_balance -= return_credit
            
            db.session.commit()
            flash('Return processed successfully.', 'success')
            return redirect(url_for('sales.invoice_detail', sale_id=sale_id))
        
        except Exception as e:
            db.session.rollback()
            flash(f'Failed to process return: {str(e)}', 'danger')
            return redirect(url_for('sales.process_return', sale_id=sale_id))
    
    return render_template('sales/process_return.html', sale=sale)