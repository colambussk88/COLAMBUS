from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    jsonify,
    send_file,
)
from flask_login import login_required, current_user
from app.models import (
    db,
    Product,
    StockMovement,
    Category,
    Unit,
    Supplier,
    Purchase,
    PurchaseItem,
    PurchaseReturn,
)
from datetime import datetime, timedelta
import csv
import io

inventory_bp = Blueprint("inventory", __name__, url_prefix="/inventory")

# ---------------------------------------------------
# Generate Purchase number
# ---------------------------------------------------

def generate_purchase_number():
    last = Purchase.query.order_by(Purchase.id.desc()).first()

    if last and last.purchase_number:
        try:
            last_num = int(last.purchase_number.replace("PUR-", ""))
        except:
            last_num = last.id
        new_num = last_num + 1
    else:
        new_num = 1

    return f"PUR-{str(new_num).zfill(5)}"


# ---------------------------------------------------
# PRODUCT LIST
# ---------------------------------------------------
@inventory_bp.route("/products")
@login_required
def products_list():

    company_id = current_user.company_id
    page = request.args.get("page", 1, type=int)
    search = request.args.get("search", "")

    query = Product.query.filter_by(company_id=company_id, is_active=True)

    if search:
        query = query.filter(
            db.or_(
                Product.product_name.ilike(f"%{search}%"),
                Product.generic_name.ilike(f"%{search}%"),
                Product.barcode.ilike(f"%{search}%"),
                Product.sku.ilike(f"%{search}%"),
            )
        )

    products = query.order_by(Product.product_name).paginate(page=page, per_page=20)

    return render_template(
        "inventory/products_list.html", products=products, search=search
    )


# ---------------------------------------------------
# PRODUCT DETAIL
# ---------------------------------------------------
@inventory_bp.route("/products/<int:product_id>")
@login_required
def product_detail(product_id):

    product = db.session.get(Product, product_id)

    if not product or product.company_id != current_user.company_id:
        flash("Product not found.", "danger")
        return redirect(url_for("inventory.products_list"))

    return render_template("inventory/product_detail.html", product=product)


# ---------------------------------------------------
# ADD PRODUCT + BULK CSV
# ---------------------------------------------------
@inventory_bp.route("/products/add", methods=["GET", "POST"])
@login_required
def add_product():

    if request.method == "POST":

        # ---------- BULK CSV ----------
        if "bulk_file" in request.files and request.files["bulk_file"].filename:

            file = request.files["bulk_file"]

            try:
                stream = io.StringIO(file.stream.read().decode("utf-8"))
                reader = csv.DictReader(stream)

                created = 0
                skipped = 0

                for row in reader:

                    # -----------------------------
                    # GET SUPPLIER FROM CSV ✅ FIX
                    # -----------------------------
                    supplier_name = (
                        row.get("supplier_name") or ""
                    ).strip() or "Default Supplier"
                    phone = (row.get("phone") or "").strip() or "0000000000"
                    batch_number = (
                        row.get("batch_number") or ""
                    ).strip() or "BATCH-001"

                    # ✅ EXPIRY DATE FIX
                    expiry_date_str = (row.get("expiry_date") or "").strip()
                    if expiry_date_str:
                        expiry_date = datetime.strptime(expiry_date_str, "%Y-%m-%d")
                    else:
                        expiry_date = datetime.utcnow()

                    supplier = Supplier.query.filter_by(
                        supplier_name=supplier_name, company_id=current_user.company_id
                    ).first()

                    if not supplier:
                        supplier = Supplier(
                            supplier_name=supplier_name,
                            company_id=current_user.company_id,
                            phone=phone,
                            is_active=True,
                        )
                        db.session.add(supplier)
                        db.session.flush()

                    # -----------------------------
                    # PRODUCT DUPLICATE CHECK
                    # -----------------------------
                    barcode = row.get("barcode") or None
                    sku = row.get("sku") or None

                    if sku:
                        existing = Product.query.filter_by(
                            sku=sku, company_id=current_user.company_id
                        ).first()
                        if existing:
                            skipped += 1
                            continue

                    if barcode:
                        existing = Product.query.filter_by(
                            barcode=barcode, company_id=current_user.company_id
                        ).first()
                        if existing:
                            skipped += 1
                            continue

                    # -----------------------------
                    # CREATE PRODUCT
                    # -----------------------------
                    product = Product(
                        company_id=current_user.company_id,
                        product_name=row.get("product_name"),
                        generic_name=row.get("generic_name"),
                        brand=row.get("brand"),
                        category=row.get("category"),
                        manufacturer=row.get("manufacturer"),
                        barcode=barcode,
                        sku=sku,
                        purchase_price=float(row.get("purchase_price") or 0),
                        selling_price=float(row.get("selling_price") or 0),
                        mrp=float(row.get("mrp") or 0),
                        tax_percentage=float(row.get("tax_percentage") or 0),
                        quantity=0,
                        minimum_stock_level=int(
                            float(row.get("minimum_stock_level") or 10)
                        ),
                        reorder_level=int(float(row.get("reorder_level") or 20)),
                    )

                    db.session.add(product)
                    db.session.flush()

                    # -----------------------------
                    # VALUES FROM CSV
                    # -----------------------------
                    quantity = int(float(row.get("quantity") or 0))
                    purchase_price = float(row.get("purchase_price") or 0)

                     # ✅ READ TAX FROM CSV
                    tax = row.get("tax_percentage", "0")
                    tax = float(str(tax).replace("%", "").strip())

                        # ✅ CALCULATE TAX
                    subtotal = quantity * purchase_price
                    tax_amount = subtotal * (tax / 100)
                    total = subtotal + tax_amount


                    # -----------------------------
                    # CREATE PURCHASE
                    # -----------------------------
                    purchase = Purchase(
                        company_id=current_user.company_id,
                        supplier_id=supplier.id,
                        purchase_number=generate_purchase_number(),
                        purchase_date=datetime.utcnow(),
                        subtotal=quantity * purchase_price,
                        tax_amount=tax_amount,
                        discount_amount=0,
                        total_amount=total,
                        payment_status="paid",
                    )

                    db.session.add(purchase)
                    db.session.flush()

                    # -----------------------------
                    # CREATE PURCHASE ITEM
                    # -----------------------------
                    purchase_item = PurchaseItem(
                        purchase_id=purchase.id,
                        product_id=product.id,
                        batch_number=batch_number,
                        expiry_date=expiry_date,
                        quantity=quantity,
                        unit_price=purchase_price,
                        tax_percentage=tax,
                        tax_amount=tax_amount,
                        total_amount=total,
                    )

                    db.session.add(purchase_item)

                    # -----------------------------
                    # UPDATE STOCK
                    # -----------------------------
                    product.quantity += quantity
                    product.purchase_price = purchase_price
                    product.updated_date = datetime.utcnow()

                    # -----------------------------
                    # STOCK MOVEMENT
                    # -----------------------------
                    movement = StockMovement(
                        product_id=product.id,
                        movement_type="purchase",
                        quantity=quantity,
                        batch_number=batch_number,
                        reference_id=purchase.id,
                    )

                    db.session.add(movement)

                    created += 1

                db.session.commit()

                flash(
                    f"{created} products uploaded with purchases. {skipped} duplicates skipped.",
                    "success",
                )
                return redirect(url_for("inventory.products_list"))

            except Exception as e:
                db.session.rollback()
                flash(f"CSV Upload failed: {str(e)}", "danger")
                return redirect(url_for("inventory.add_product"))

        # ---------- SINGLE PRODUCT ----------
        try:

            category_id = request.form.get("category_id")
            unit_id = request.form.get("unit_id")

            category_name = None
            if category_id:
                cat = db.session.get(Category, int(category_id))
                if cat:
                    category_name = cat.name

            barcode = request.form.get("barcode") or None
            sku = request.form.get("sku") or None

            product = Product(
                company_id=current_user.company_id,
                product_name=request.form.get("product_name"),
                generic_name=request.form.get("generic_name"),
                brand=request.form.get("brand"),
                category=category_name,
                category_id=category_id,
                unit_id=unit_id,
                manufacturer=request.form.get("manufacturer"),
                barcode=barcode,
                sku=sku,
                purchase_price=float(request.form.get("purchase_price", 0)),
                selling_price=float(request.form.get("selling_price", 0)),
                mrp=float(request.form.get("mrp", 0)),
                quantity=int(request.form.get("quantity", 0)),
                minimum_stock_level=int(request.form.get("minimum_stock_level", 10)),
            )

            db.session.add(product)
            db.session.commit()

            flash("Product added successfully.", "success")
            return redirect(url_for("inventory.product_detail", product_id=product.id))

        except Exception as e:
            db.session.rollback()
            flash(str(e), "danger")

    categories = (
        Category.query.filter(Category.company_id == current_user.company_id)
        .order_by(Category.name)
        .all()
    )

    units = (
        Unit.query.filter(Unit.company_id == current_user.company_id)
        .order_by(Unit.name)
        .all()
    )

    return render_template(
        "inventory/add_product.html", categories=categories, units=units
    )


# ---------------------------------------------------
# EDIT PRODUCT
# ---------------------------------------------------
@inventory_bp.route("/products/<int:product_id>/edit", methods=["GET", "POST"])
@login_required
def edit_product(product_id):

    product = db.session.get(Product, product_id)

    if not product:
        flash("Product not found", "danger")
        return redirect(url_for("inventory.products_list"))

    if request.method == "POST":

        product.product_name = request.form.get("product_name")
        product.generic_name = request.form.get("generic_name")
        product.brand = request.form.get("brand")
        product.manufacturer = request.form.get("manufacturer")
        product.batch_number = request.form.get("batch_number")

        # ✅ CATEGORY
        category_id = request.form.get("category_id")
        if category_id:
            category = db.session.get(Category, int(category_id))
            product.category_id = int(category_id)
            product.category = category.name if category else None

        # ✅ UNIT
        unit_id = request.form.get("unit_id")
        if unit_id:
            product.unit_id = int(unit_id)

        # ✅ TAX (MAIN FIX)
        product.tax_percentage = float(request.form.get("tax_percentage") or 0)

        # ✅ PRICING
        product.purchase_price = float(request.form.get("purchase_price") or 0)
        product.selling_price = float(request.form.get("selling_price") or 0)
        product.mrp = float(request.form.get("mrp") or 0)

        # ✅ STOCK
        product.quantity = int(request.form.get("quantity") or 0)
        product.minimum_stock_level = int(request.form.get("minimum_stock_level") or 0)
        product.reorder_level = int(request.form.get("reorder_level") or 0)

        product.updated_date = datetime.utcnow()

        db.session.commit()

        print("✅ SAVED TAX:", product.tax_percentage)  # DEBUG

        flash("Product updated successfully", "success")
        return redirect(url_for("inventory.product_detail", product_id=product.id))

    # ✅ LOAD DROPDOWNS (VERY IMPORTANT)
    categories = Category.query.filter(
        Category.company_id == current_user.company_id
    ).all()

    units = Unit.query.filter(Unit.company_id == current_user.company_id).all()

    return render_template(
        "inventory/edit_product.html",
        product=product,
        categories=categories,
        units=units,
    )


# ---------------------------------------------------
# DELETE PRODUCT
# ---------------------------------------------------
@inventory_bp.route("/products/<int:product_id>/delete", methods=["POST"])
@login_required
def delete_product(product_id):

    product = db.session.get(Product, product_id)

    if not product:
        flash("Product not found", "danger")
        return redirect(url_for("inventory.products_list"))

    product.is_active = False
    db.session.commit()

    flash("Product deleted successfully", "success")
    return redirect(url_for("inventory.products_list"))


# ---------------------------------------------------
# LOW STOCK REPORT
# ---------------------------------------------------
@inventory_bp.route("/low-stock")
@login_required
def low_stock_report():

    products = Product.query.filter(
        Product.company_id == current_user.company_id,
        Product.quantity <= Product.minimum_stock_level,
        Product.is_active == True,
    ).all()

    return render_template("inventory/low_stock_report.html", products=products)


# ---------------------------------------------------
# expiry REPORT
# ---------------------------------------------------


@inventory_bp.route("/expiry-report")
@login_required
def expiry_report():

    days = request.args.get("days", 90, type=int)

    today = datetime.utcnow().date()
    end_date = today + timedelta(days=days)

    products = (
        Product.query.filter(
            Product.company_id == current_user.company_id,
            Product.expiry_date != None,
            Product.expiry_date <= end_date,  # ✅ includes past + future
            Product.is_active == True,
        )
        .order_by(Product.expiry_date)
        .all()
    )

    products_info = []

    for p in products:
        if p.expiry_date:
            days_left = (p.expiry_date.date() - today).days  # 🔥 negative = past
        else:
            days_left = None

        products_info.append(
            {"product": p, "expiry_date": p.expiry_date, "days_left": days_left}
        )

    return render_template("inventory/expiry_report.html", products_info=products_info)


@inventory_bp.route("/return-expired", methods=["POST"])
@login_required
def return_expired():

    product_id = request.form.get("product_id")
    quantity = int(request.form.get("quantity", 0))

    if not product_id or quantity <= 0:
        flash("Invalid input", "danger")
        return redirect(url_for("inventory.expiry_report"))

    product = Product.query.get(product_id)

    if not product:
        flash("Product not found", "danger")
        return redirect(url_for("inventory.expiry_report"))

    if quantity > product.quantity:
        flash("Not enough stock", "danger")
        return redirect(url_for("inventory.expiry_report"))

    # 🔍 Get latest purchase item (for supplier link)
    purchase_item = (
        PurchaseItem.query.filter_by(product_id=product.id)
        .order_by(PurchaseItem.id.desc())
        .first()
    )

    if not purchase_item:
        flash("No purchase found for this product", "danger")
        return redirect(url_for("inventory.expiry_report"))

    # 💰 Calculate credit
    credit_amount = quantity * purchase_item.unit_price

    # 🧾 Create purchase return
    purchase_return = PurchaseReturn(
        purchase_id=purchase_item.purchase_id,
        product_id=product.id,
        batch_number=purchase_item.batch_number,
        quantity=quantity,
        reason="Expired",
        credit_amount=credit_amount,
    )

    db.session.add(purchase_return)

    # 📦 Reduce stock
    product.quantity -= quantity

    db.session.commit()

    flash("Returned to supplier successfully", "success")
    return redirect(url_for("inventory.expiry_report"))


# ---------------------------------------------------
# BARCODE SEARCH
# ---------------------------------------------------
@inventory_bp.route("/barcode-search")
@login_required
def barcode_search():

    barcode = request.args.get("barcode")

    product = Product.query.filter_by(
        barcode=barcode, company_id=current_user.company_id
    ).first()

    if not product:
        return jsonify({"error": "Product not found"}), 404

    return jsonify(
        {
            "id": product.id,
            "name": product.product_name,
            "price": product.selling_price,
            "stock": product.quantity,
        }
    )


# ---------------------------------------------------
# DOWNLOAD CSV TEMPLATE
# ---------------------------------------------------
@inventory_bp.route("/download-products-template")
@login_required
def download_products_template():

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(
        [
            "product_name",
            "generic_name",
            "brand",
            "category",
            "manufacturer",
            "barcode",
            "sku",
            "purchase_price",
            "selling_price",
            "mrp",
            "tax_percentage",
            "quantity",
            "supplier_name",
            "phone",
            "batch_number",
        ]
    )

    writer.writerow(
        [
            "Paracetamol 500mg",
            "Paracetamol",
            "Crocin",
            "Tablet",
            "GSK",
            "",
            "SKU001",
            "10",
            "12",
            "15",
            "5",
            "100",
            "ABC Pharma",
            "9876543210",
            "BATCH001",
        ]
    )

    output.seek(0)

    return send_file(
        io.BytesIO(output.getvalue().encode()),
        mimetype="text/csv",
        as_attachment=True,
        download_name="products_template.csv",
    )
