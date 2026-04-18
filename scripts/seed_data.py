from app import create_app, db
from app.models import Product, Supplier, Customer

app, _ = create_app()

with app.app_context():

    # Supplier
    supplier = Supplier(
        company_id=1,
        supplier_name="ABC Pharma",
        phone="9876543210",
        is_active=True
    )

    db.session.add(supplier)

    # Customer
    customer = Customer(
        company_id=1,
        customer_name="Walk-in Customer",
        phone="9999999999",
        is_active=True
    )

    db.session.add(customer)

    # Product
    product = Product(
        company_id=1,
        product_name="Paracetamol 500mg",
        category="Tablet",
        purchase_price=10,
        selling_price=15,
        mrp=20,
        tax_percentage=5,
        quantity=100,
        sku="PARA001"
    )

    db.session.add(product)

    db.session.commit()

    print("✅ Demo data inserted!")