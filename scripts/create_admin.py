from app import create_app, db
from app.models import User, Company

app, _ = create_app()   # ✅ FIX HERE

with app.app_context():

    company = Company(
        company_name="Platform Admin",
        owner_name="Admin",
        email="admin@system.com",
        phone="0000000000",
        address="System",
        city="NA",
        state="NA",
        country="NA",
        postal_code="00000"
    )

    db.session.add(company)
    db.session.commit()

    admin = User(
        company_id=company.id,
        username="admin",
        role="owner"
    )

    admin.set_password("admin123")

    db.session.add(admin)
    db.session.commit()

    print("✅ Admin created successfully!")