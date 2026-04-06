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
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from app.services.whatsapp_service import send_whatsapp_message

sales_bp = Blueprint('sales', __name__, url_prefix='/sales')


def generate_invoice_number():
    """Generate short sequential invoice number"""
    
    last_sale = db.session.query(Sale).order_by(Sale.id.desc()).first()
    
    if last_sale and last_sale.invoice_number:
        try:
            last_number = int(last_sale.invoice_number.replace("INV-", ""))
        except:
            last_number = last_sale.id
        new_number = last_number + 1
    else:
        new_number = 1

    return f"INV-{str(new_number).zfill(5)}"


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
        'stock': p.quantity,
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

        # Fix customer lookup
        if customer_id:
            try:
                customer_id = int(customer_id)
                customer = Customer.query.get(customer_id)
                if customer:
                    customer_name = customer.customer_name
                    customer_phone = getattr(customer, "phone", "")
            except:
                customer_id = None

        if not items:
            return jsonify({'success': False, 'message': 'Cart is empty'}), 400

        company_id = current_user.company_id

        sale_items = []
        subtotal = 0
        total_tax = 0

        for item in items:

            pid = item.get('product_id') or item.get('id')
            try:
                pid = int(pid)
            except:
                pid = None

            product = Product.query.get(pid) if pid else None

            if not product or product.company_id != company_id:
                return jsonify({'success': False, 'message': 'Invalid product'}), 400

            quantity = int(item.get('quantity', 1))

            if product.quantity < quantity:
                return jsonify({
                    'success': False,
                    'message': f'Insufficient stock for {product.product_name}'
                }), 400

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

        total_amount = subtotal + total_tax - discount
        if total_amount < 0:
            total_amount = 0

        # Create sale
        sale = Sale(
            company_id=company_id,
            customer_id=customer_id,
            invoice_number=generate_invoice_number(),
            invoice_date=datetime.now(),
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

        # Add sale items
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

            product = item['product']
            product.quantity -= item['quantity']
            product.updated_date = datetime.now()

            movement = StockMovement(
                product_id=product.id,
                movement_type='sale',
                quantity=-item['quantity'],
                batch_number=item['batch_number'],
                reference_id=sale.id
            )

            db.session.add(movement)

        # Update credit balance
        if customer_id and payment_method == 'credit':
            customer = Customer.query.get(customer_id)
            if customer:
                customer.current_balance += total_amount

        db.session.commit()
        print("CHECKOUT SUCCESSFUL")
        print("Customer Phone:", customer_phone)

        #whatsapp notification
        try:
            if customer_phone:

                phone = customer_phone.strip()

                # Convert to international format if needed
                if not phone.startswith("+"):
                    phone = "+91" + phone

                
                message = (
                   f"🧾 *Rukmini Pharmacy*\n\n"
                   f"Hello {customer_name},\n\n"
                   f"📄 Invoice: {sale.invoice_number}\n"
                   f"💰 Total: ₹{total_amount:.2f}\n"
                   f"💳 Payment: {payment_method}\n\n"
                   f"Thank you for choosing our pharmacy 💊"
                )
                send_whatsapp_message(customer_phone, message)
        except Exception as e:
         print("Whatsapp Message Failed:", e)

        

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

    # Get returns for this invoice
    returns = SalesReturn.query.filter_by(sale_id=sale_id).all()

    return render_template(
        'sales/invoice_detail.html',
        sale=sale,
        returns=returns
    )

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

    sale = Sale.query.get(sale_id)

    if not sale or sale.company_id != current_user.company_id:
        return jsonify({'success': False, 'message': 'Invoice not found'}), 404

    try:
        # Font (₹ support)
        pdfmetrics.registerFont(
            TTFont('DejaVu', 'app/static/uploads/DejaVuSans.ttf')
        )

        # Returns calculation
        returns = SalesReturn.query.filter_by(sale_id=sale_id).all()
        returned_amount = sum(r.refund_amount for r in returns)
        net_total = sale.total_amount - returned_amount

        buffer = io.BytesIO()

        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            topMargin=30,
            bottomMargin=30,
            leftMargin=40,
            rightMargin=40
        )

        elements = []
        company = sale.company

        # ---------- HEADER BAR ----------
        header_bg = colors.HexColor("#1a3a52")

        header_table = Table([
            [Paragraph(f"<b>{company.company_name}</b>",
                       ParagraphStyle('header',
                                      fontSize=16,
                                      textColor=colors.white,
                                      alignment=TA_LEFT,
                                      fontName='DejaVu'))]
        ], colWidths=[500])

        header_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), header_bg),
            ('LEFTPADDING', (0,0), (-1,-1), 10),
            ('TOPPADDING', (0,0), (-1,-1), 8),
            ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ]))

        elements.append(header_table)

        # Company Info
        elements.append(Spacer(1, 8))
        company_info = f"""
        {company.address or ''}<br/>
        phone: {company.phone or ''} &nbsp;&nbsp; Mail: {company.email or ''}
        """
        elements.append(Paragraph(company_info,
                                  ParagraphStyle('company',
                                                 fontSize=9,
                                                 fontName='DejaVu')))

        elements.append(Spacer(1, 15))

        # ---------- TITLE ----------
        elements.append(Paragraph(
            "<b>INVOICE</b>",
            ParagraphStyle('title',
                           fontSize=18,
                           alignment=TA_CENTER,
                           fontName='DejaVu')
        ))
        elements.append(Spacer(1, 12))

        # ---------- INVOICE DETAILS ----------
        info_table = Table([
            ['Invoice No', sale.invoice_number],
            ['Date', sale.invoice_date.strftime('%d-%m-%Y')],
            ['Time', sale.invoice_date.strftime('%H:%M:%S')],
        ], colWidths=[120, 200])

        info_table.setStyle(TableStyle([
            ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
            ('BACKGROUND', (0,0), (0,-1), colors.HexColor("#f0f4f8")),
            ('FONTNAME',(0,0),(-1,-1),'DejaVu')
        ]))

        elements.append(info_table)
        elements.append(Spacer(1, 15))

        # ---------- BILL SECTION ----------
        bill_table = Table([
            [
                Paragraph(f"<b>Bill To</b><br/>{sale.customer_name or 'Walk-in Customer'}",
                          ParagraphStyle('normal', fontName='DejaVu')),
                Paragraph(f"<b>Sold By</b><br/>{company.company_name}",
                          ParagraphStyle('normal', fontName='DejaVu'))
            ]
        ], colWidths=[250,250])

        elements.append(bill_table)
        elements.append(Spacer(1, 20))

        # ---------- ITEMS ----------
        item_data = [['Item', 'Qty', 'Price', 'Discount', 'Tax', 'Amount']]

        for item in sale.items:
            item_data.append([
                item.product.product_name,
                str(item.quantity),
                f"₹ {item.unit_price:.2f}",
                f"₹ {item.discount_amount:.2f}",
                f"₹ {item.tax_amount:.2f}",
                f"₹ {item.total_amount:.2f}"
            ])

        items_table = Table(item_data, colWidths=[200,50,80,80,60,80])

        items_table.setStyle(TableStyle([
            ('FONTNAME',(0,0),(-1,-1),'DejaVu'),

            ('BACKGROUND',(0,0),(-1,0),header_bg),
            ('TEXTCOLOR',(0,0),(-1,0),colors.white),

            ('ALIGN',(1,1),(-1,-1),'RIGHT'),
            ('GRID',(0,0),(-1,-1),0.5,colors.grey),

            ('ROWBACKGROUNDS',(0,1),(-1,-1),
             [colors.white, colors.HexColor('#f7f7f7')])
        ]))

        elements.append(items_table)
        elements.append(Spacer(1, 20))

        # ---------- SUMMARY ----------
        summary_data = [
            ['Subtotal', f"₹ {sale.subtotal:.2f}"],
            ['Tax', f"₹ {sale.tax_amount:.2f}"],
            ['Discount', f"- ₹ {sale.discount_amount:.2f}"]
        ]

        if returned_amount > 0:
            summary_data.append(['Returned', f"- ₹ {returned_amount:.2f}"])

        summary_data.append(['TOTAL', f"₹ {net_total:.2f}"])

        summary_table = Table(summary_data, colWidths=[200,120])

        summary_table.setStyle(TableStyle([
            ('FONTNAME',(0,0),(-1,-1),'DejaVu'),

            ('ALIGN',(1,0),(-1,-1),'RIGHT'),
            ('GRID',(0,0),(-1,-2),0.5,colors.grey),

            ('BACKGROUND',(0,-1),(-1,-1),header_bg),
            ('TEXTCOLOR',(0,-1),(-1,-1),colors.white),

            ('FONTSIZE',(0,-1),(-1,-1),13)
        ]))

        elements.append(summary_table)
        elements.append(Spacer(1, 25))

        # ---------- FOOTER ----------
        elements.append(Paragraph(
            "Thank you for your purchase <br/>This is a computer generated invoice.",
            ParagraphStyle('footer',
                           alignment=TA_CENTER,
                           fontSize=9,
                           fontName='DejaVu')
        ))

        # Build PDF
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

@sales_bp.route('/send-invoice-whatsapp/<int:sale_id>', methods=['POST'])
@login_required
def send_invoice_whatsapp(sale_id):

    sale = Sale.query.get(sale_id)

    if not sale:
        return jsonify({"success": False, "message": "Invoice not found"})

    try:

        phone = sale.customer_phone

        if not phone:
            return jsonify({"success": False, "message": "Customer phone missing"})

        if not phone.startswith("+"):
            phone = "+91" + phone

        # build items
        items_text = ""
        for item in sale.items:
            items_text += f"• {item.product.product_name} × {item.quantity}\n"

        message = (
            f"🧾 Rukmini Pharmacy\n\n"
            f"Hello {sale.customer_name or 'Customer'} 👋\n\n"
            f"Invoice: {sale.invoice_number}\n\n"
            f"Items:\n{items_text}\n"
            f"Total: ₹{sale.total_amount:.2f}\n\n"
            f"Thank you for choosing our pharmacy 💊"
        )

        send_whatsapp_message(phone, message)

        return jsonify({"success": True})

    except Exception as e:
        return jsonify({"success": False, "message": str(e)})
        
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