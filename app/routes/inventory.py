from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_login import login_required, current_user
from app.models import db, Product, StockMovement, Category, Unit
from datetime import datetime, timedelta
import csv
import io

inventory_bp = Blueprint('inventory', __name__, url_prefix='/inventory')


# ---------------------------------------------------
# PRODUCT LIST
# ---------------------------------------------------
@inventory_bp.route('/products')
@login_required
def products_list():

    company_id = current_user.company_id
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')

    query = Product.query.filter_by(company_id=company_id, is_active=True)

    if search:
        query = query.filter(
            db.or_(
                Product.product_name.ilike(f'%{search}%'),
                Product.generic_name.ilike(f'%{search}%'),
                Product.barcode.ilike(f'%{search}%'),
                Product.sku.ilike(f'%{search}%')
            )
        )

    products = query.order_by(Product.product_name).paginate(page=page, per_page=20)

    return render_template('inventory/products_list.html', products=products, search=search)


# ---------------------------------------------------
# PRODUCT DETAIL
# ---------------------------------------------------
@inventory_bp.route('/products/<int:product_id>')
@login_required
def product_detail(product_id):

    product = db.session.get(Product, product_id)

    if not product or product.company_id != current_user.company_id:
        flash('Product not found.', 'danger')
        return redirect(url_for('inventory.products_list'))

    return render_template('inventory/product_detail.html', product=product)


# ---------------------------------------------------
# ADD PRODUCT + BULK CSV
# ---------------------------------------------------
@inventory_bp.route('/products/add', methods=['GET', 'POST'])
@login_required
def add_product():

    if request.method == 'POST':

        # ---------- BULK CSV ----------
        if 'bulk_file' in request.files and request.files['bulk_file'].filename:

            file = request.files['bulk_file']

            try:
                stream = io.StringIO(file.stream.read().decode('utf-8'))
                reader = csv.DictReader(stream)

                created = 0
                skipped = 0

                for row in reader:

                    barcode = row.get('barcode') or None
                    sku = row.get('sku') or None

                    # Skip duplicate SKU
                    if sku:
                        existing = Product.query.filter_by(
                            sku=sku,
                            company_id=current_user.company_id
                        ).first()
                        if existing:
                            skipped += 1
                            continue

                    # Skip duplicate barcode
                    if barcode:
                        existing = Product.query.filter_by(
                            barcode=barcode,
                            company_id=current_user.company_id
                        ).first()
                        if existing:
                            skipped += 1
                            continue

                    product = Product(
                        company_id=current_user.company_id,
                        product_name=row.get('product_name'),
                        generic_name=row.get('generic_name'),
                        brand=row.get('brand'),
                        category=row.get('category'),
                        manufacturer=row.get('manufacturer'),
                        barcode=barcode,
                        sku=sku,
                        purchase_price=float(row.get('purchase_price') or 0),
                        selling_price=float(row.get('selling_price') or 0),
                        mrp=float(row.get('mrp') or 0),
                        quantity=int(float(row.get('quantity') or 0)),
                        minimum_stock_level=int(float(row.get('minimum_stock_level') or 10)),
                        reorder_level=int(float(row.get('reorder_level') or 20))
                    )

                    db.session.add(product)
                    created += 1

                db.session.commit()

                flash(f"{created} products uploaded. {skipped} duplicates skipped.", "success")
                return redirect(url_for('inventory.products_list'))

            except Exception as e:
                db.session.rollback()
                flash(f"CSV Upload failed: {str(e)}", "danger")
                return redirect(url_for('inventory.add_product'))

        # ---------- SINGLE PRODUCT ----------
        try:

            category_id = request.form.get('category_id')
            unit_id = request.form.get('unit_id')

            category_name = None
            if category_id:
                cat = db.session.get(Category, int(category_id))
                if cat:
                    category_name = cat.name

            barcode = request.form.get('barcode') or None
            sku = request.form.get('sku') or None

            product = Product(
                company_id=current_user.company_id,
                product_name=request.form.get('product_name'),
                generic_name=request.form.get('generic_name'),
                brand=request.form.get('brand'),
                category=category_name,
                category_id=category_id,
                unit_id=unit_id,
                manufacturer=request.form.get('manufacturer'),
                barcode=barcode,
                sku=sku,
                purchase_price=float(request.form.get('purchase_price', 0)),
                selling_price=float(request.form.get('selling_price', 0)),
                mrp=float(request.form.get('mrp', 0)),
                quantity=int(request.form.get('quantity', 0)),
                minimum_stock_level=int(request.form.get('minimum_stock_level', 10))
            )

            db.session.add(product)
            db.session.commit()

            flash('Product added successfully.', 'success')
            return redirect(url_for('inventory.product_detail', product_id=product.id))

        except Exception as e:
            db.session.rollback()
            flash(str(e), 'danger')

    categories = Category.query.filter(
        Category.company_id == current_user.company_id
    ).order_by(Category.name).all()

    units = Unit.query.filter(
        Unit.company_id == current_user.company_id
    ).order_by(Unit.name).all()

    return render_template('inventory/add_product.html', categories=categories, units=units)


# ---------------------------------------------------
# EDIT PRODUCT
# ---------------------------------------------------
@inventory_bp.route('/products/<int:product_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_product(product_id):

    product = db.session.get(Product, product_id)

    if not product:
        flash("Product not found", "danger")
        return redirect(url_for('inventory.products_list'))

    if request.method == "POST":

        product.product_name = request.form.get("product_name")
        product.generic_name = request.form.get("generic_name")
        product.brand = request.form.get("brand")
        product.updated_date = datetime.utcnow()

        db.session.commit()

        flash("Product updated successfully", "success")
        return redirect(url_for('inventory.product_detail', product_id=product.id))

    return render_template("inventory/edit_product.html", product=product)


# ---------------------------------------------------
# DELETE PRODUCT
# ---------------------------------------------------
@inventory_bp.route('/products/<int:product_id>/delete', methods=['POST'])
@login_required
def delete_product(product_id):

    product = db.session.get(Product, product_id)

    if not product:
        flash("Product not found", "danger")
        return redirect(url_for('inventory.products_list'))

    product.is_active = False
    db.session.commit()

    flash("Product deleted successfully", "success")
    return redirect(url_for('inventory.products_list'))


# ---------------------------------------------------
# LOW STOCK REPORT
# ---------------------------------------------------
@inventory_bp.route('/low-stock')
@login_required
def low_stock_report():

    products = Product.query.filter(
        Product.company_id == current_user.company_id,
        Product.quantity <= Product.minimum_stock_level,
        Product.is_active == True
    ).all()

    return render_template("inventory/low_stock_report.html", products=products)


# ---------------------------------------------------
# EXPIRY REPORT
# ---------------------------------------------------
@inventory_bp.route('/expiry-report')
@login_required
def expiry_report():

    limit = datetime.utcnow().date() + timedelta(days=90)

    products = Product.query.filter(
        Product.company_id == current_user.company_id,
        Product.expiry_date <= limit,
        Product.is_active == True
    ).all()

    return render_template("inventory/expiry_report.html", products=products)


# ---------------------------------------------------
# BARCODE SEARCH
# ---------------------------------------------------
@inventory_bp.route('/barcode-search')
@login_required
def barcode_search():

    barcode = request.args.get("barcode")

    product = Product.query.filter_by(
        barcode=barcode,
        company_id=current_user.company_id
    ).first()

    if not product:
        return jsonify({"error": "Product not found"}), 404

    return jsonify({
        "id": product.id,
        "name": product.product_name,
        "price": product.selling_price,
        "stock": product.quantity
    })


# ---------------------------------------------------
# DOWNLOAD CSV TEMPLATE
# ---------------------------------------------------
@inventory_bp.route('/download-products-template')
@login_required
def download_products_template():

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        'product_name','generic_name','brand','category','manufacturer',
        'barcode','sku','purchase_price','selling_price','mrp','quantity'
    ])

    writer.writerow([
        'Paracetamol 500mg','Paracetamol','Crocin','Tablet','GSK',
        '','SKU001','10','12','15','100'
    ])

    output.seek(0)

    return send_file(
        io.BytesIO(output.getvalue().encode()),
        mimetype='text/csv',
        as_attachment=True,
        download_name='products_template.csv'
    )