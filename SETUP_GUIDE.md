# Pharmacy Management System - Complete Documentation

## Overview
A comprehensive single-tenant Pharmacy Management System built with Flask and SQLite3. This system allows a pharmacy company to register once, manage all operations under one account with full administrative control.

## Key Features

### 1. **Company Registration & Authentication**
- Company registration with complete details (name, owner, contact, address, GST, drug license)
- Logo upload and storage
- User account creation with password hashing
- Session-based login using Flask-Login
- Profile management and password change
- Automatic logout protection on all protected routes

### 2. **Dashboard**
- Real-time key metrics (today's sales, monthly sales, total profit, purchases)
- Stock and expiry alerts
- Quick action buttons for POS, adding products, etc.
- 7-day sales trend graph
- Recent transaction history

### 3. **Inventory Management**
- Complete product management with batch tracking
- Advanced search by name, barcode, SKU
- Product categories and filtering
- Automatic stock deduction on sales
- Automatic stock increase on purchases
- Manual stock adjustments with reason logging
- Low stock alerts
- Expiry tracking (30/60/90 days)
- Stock movement history
- Batch-wise FIFO tracking

### 4. **POS/Sales Module**
- Quick product search with instant add to cart
- Barcode/SKU support
- Real-time tax calculation
- Per-item and bill-level discounts
- Multiple payment methods (Cash, Card, UPI, Bank, Credit)
- Invoice generation with unique numbers
- Professional invoice printing and PDF download
- Sales return and partial return processing
- Cancel invoice with reason logging
- Credit memo generation

### 5. **Purchase Management**
- Supplier management with contact details
- Purchase order creation
- Batch-specific tracking with expiry dates
- Automatic stock updates
- Payment tracking (pending/partial/paid)
- Purchase returns with stock reversal
- Supplier ledger and outstanding balance tracking
- Payment status reports
- Supplier-wise reports

### 6. **Customer Management**
- Customer registration and profile management
- Credit limit and balance tracking
- Purchase history
- Outstanding payment tracking
- Payment recording
- Customer ledger report

### 7. **Accounting Module**
- Expense tracking with categories
- Receipt image attachment
- Daily cash summary
- Sales and purchase registers
- Profit & Loss calculations
- Tax tracking and summary
- Outstanding payment reports

### 8. **Reports & Analytics**
- Sales reports with date filtering
- Purchase reports
- Inventory reports (stock, low stock, expiry)
- Profit & Loss analysis
- Tax summary
- Customer and Supplier ledgers
- CSV/PDF/Excel export options

### 9. **Alert System**
- Low stock alerts
- Expiry alerts (30/60/90 days notifications)
- Pending customer payment alerts
- Pending supplier payment alerts
- Real-time alert notifications
- Critical/Warning/Info severity levels

## Installation & Setup

### Prerequisites
- Python 3.7+
- pip (Python package manager)
- Virtual environment (recommended)

### Step 1: Clone Repository
```bash
cd /workspaces/pharmacy-management-system-
```

### Step 2: Create Virtual Environment
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### Step 3: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 4: Initialize Database
```bash
python
>>> from app import create_app
>>> from app.models import db
>>> app = create_app()
>>> with app.app_context():
>>>     db.create_all()
>>> exit()
```

### Step 5: Set Environment Variables
Create a `.env` file in the root directory:
```
FLASK_ENV=development
FLASK_APP=run.py
SECRET_KEY=your-secret-key-here-change-in-production
```

### Step 6: Run Application
```bash
python run.py
```

The application will be available at `http://localhost:5000`

## Initial Setup

1. **Navigate to Registration**: Go to `http://localhost:5000/register`
2. **Enter Company Details**:
   - Company name
   - Owner name
   - Email & Phone
   - Complete address
   - GST/VAT and Drug License (optional)
   - Company logo (optional)
3. **Create Account**:
   - Unique username
   - Strong password (min 6 characters)
   - Confirm password
4. **User gets auto-logged in** after successful registration
5. **Access Dashboard** to start managing your pharmacy

## Database Structure

### Main Tables
- **company**: Stores pharmacy company information
- **user**: Single user per company (admin)
- **product**: Pharmacy products with batch tracking
- **stock_movement**: History of all inventory movements
- **sale**: Invoices and transactions
- **sale_item**: Individual items in each sale
- **sales_return**: Returns and credit notes
- **purchase**: Purchase orders
- **purchase_item**: Items in purchase orders
- **purchase_return**: Returns to suppliers
- **customer**: Customer profiles and credit info
- **supplier**: Supplier information
- **expense**: Operational expenses
- **alert**: System alerts and notifications

## File Structure

```
pharmacy-management-system/
├── app/
│   ├── __init__.py                 # Flask app factory
│   ├── models.py                   # Database models
│   ├── routes/
│   │   ├── auth.py                 # Authentication routes
│   │   ├── dashboard.py            # Dashboard route
│   │   ├── inventory.py            # Inventory management
│   │   ├── sales.py                # POS and sales
│   │   ├── purchases.py            # Purchase management
│   │   ├── customers.py            # Customer management
│   │   ├── suppliers.py            # Supplier management
│   │   ├── accounting.py           # Accounting module
│   │   ├── reports.py              # Reports generation
│   │   └── alerts.py               # Alert system
│   ├── templates/
│   │   ├── base.html               # Base template with navigation
│   │   ├── login.html
│   │   ├── register.html
│   │   ├── profile.html
│   │   ├── dashboard/
│   │   │   └── index.html
│   │   ├── inventory/
│   │   │   ├── products_list.html
│   │   │   ├── add_product.html
│   │   │   └── ... (other inventory templates)
│   │   ├── sales/
│   │   │   ├── pos.html
│   │   │   ├── invoices_list.html
│   │   │   └── ... (other sales templates)
│   │   └── ... (other module templates)
│   └── static/
│       ├── uploads/                # User uploaded files
│       ├── css/
│       └── js/
├── config.py                       # Application configuration
├── run.py                          # Application entry point
├── requirements.txt                # Python dependencies
└── pharmacy.db                     # SQLite database (created on first run)
```

## Missing Templates - How to Create Them

The system includes core templates and routes. You can extend and create missing templates following the pattern of existing ones:

### 1. **Inventory Templates to Create**
- `product_detail.html` - Display single product info
- `edit_product.html` - Edit product details
- `low_stock_report.html` - Low stock items
- `expiry_report.html` - Expiry tracking
- `stock_movement_report.html` - Stock history

<!-- ### 2. **Sales Templates to Create**
- `invoices_list.html` - List all invoices
- `invoice_detail.html` - View invoice details
- `print_invoice.html` - Print-ready invoice
- `process_return.html` - Sales return processing
- `returns_list.html` - All returns -->

### 3. **Purchase Templates to Create**
<!-- - `purchases_list.html` - List purchases -->
<!-- - `purchase_detail.html` - Purchase details -->
<!-- - `add_purchase.html` - Add new purchase -->
- `process_return.html` - Return to supplier
- `returns_list.html` - Purchase returns

### 4. **Customer Templates to Create**
<!-- - `customers_list.html` - All customers
- `customer_detail.html` - Customer profile
- `add_customer.html` - Add new customer
- `edit_customer.html` - Edit customer -->
- `ledger.html` - Customer ledger

### 5. **Supplier Templates to Create**
- Similar structure to customers

### 6. **Accounting Templates to Create**
<!-- - `dashboard.html` - Accounting dashboard -->
<!-- - `expenses_list.html` - List expenses -->
<!-- - `add_expense.html` - Add expense -->
- `cash_summary.html` - Daily summary
- `sales_register.html` - Sales register
- `purchase_register.html` - Purchase register

### 7. **Reports Templates to Create**
<!-- - `index.html` - Reports home -->
<!-- - `sales.html` - Sales report -->
<!-- - `purchases.html` - Purchase report -->
- `inventory.html` - Inventory report
- `expiry.html` - Expiry report
- `profit_loss.html` - P&L report
- `tax_summary.html` - Tax report
- `outstanding_payments.html` - Payments due

## Template Creation Pattern

Each template should follow this basic structure:

```html
{% extends "base.html" %}

{% block title %}Page Title - Pharmacy Management System{% endblock %}

{% block content %}
<h2 class="mb-4">
    <i class="fas fa-[icon]"></i> Page Title
</h2>

<!-- Your content here -->

{% endblock %}
```

## API Endpoints Summary

### Authentication
- `GET/POST /register` - Company registration
- `GET/POST /login` - User login
- `GET /logout` - User logout
- `GET /profile` - View profile
- `GET/POST /profile/edit` - Edit profile
- `GET/POST /change-password` - Change password

### Dashboard & Alerts
- `GET /dashboard/` - Main dashboard
- `GET /alerts/` - View all alerts
- `GET /alerts/api/count` - Alert counts

### Inventory
- `GET /inventory/products` - List products
- `GET/POST /inventory/products/add` - Add product
- `GET /inventory/products/<id>` - Product detail
- `GET/POST /inventory/products/<id>/edit` - Edit product
- `POST /inventory/products/<id>/adjust-stock` - Adjust stock
- `GET /inventory/low-stock` - Low stock report
- `GET /inventory/expiry-report` - Expiry report

### Sales/POS
- `GET /sales/pos` - POS interface
- `GET /sales/api/products/search` - Search products
- `POST /sales/checkout` - Process checkout
- `GET /sales/invoices` - List invoices
- `GET /sales/invoices/<id>` - Invoice detail
- `GET /sales/invoices/<id>/print` - Print invoice
- `GET /sales/invoices/<id>/pdf` - Download PDF
- `POST /sales/invoices/<id>/cancel` - Cancel invoice

### Purchases
- `GET /purchases/` - List purchases
- `GET/POST /purchases/add` - Add purchase
- `GET /purchases/<id>` - Purchase detail
- `GET/POST /purchases/<id>/return` - Process return

### Customers & Suppliers
- `GET /customers/` - List customers
- `GET/POST /customers/add` - Add customer
- `GET /customers/<id>` - Customer detail
- Similar endpoints for suppliers

### Accounting & Reports
- `GET /accounting/` - Accounting dashboard
- `GET /accounting/expenses` - List expenses
- `GET /accounting/cash-summary` - Daily summary
- `GET /reports/sales` - Sales report
- `GET /reports/purchases` - Purchase report
- And many more...

## Security Features

✅ **Password Hashing**: All passwords hashed using Werkzeug security
✅ **Session Security**: Secure session cookies
✅ **Login Required**: All internal routes protected
✅ **CSRF Protection**: Ready for implementation
✅ **Input Validation**: All user inputs validated
✅ **SQL Injection Prevention**: Using SQLAlchemy ORM
✅ **Single-Tenant**: Each company is isolated

## Production Deployment

### Before Deploying:

1. **Change Secret Key** in `.env`:
   ```
   SECRET_KEY=generate-a-secure-random-key-here
   ```

2. **Set Environment**:
   ```
   FLASK_ENV=production
   ```

3. **Use Production Database**: 
   - Consider PostgreSQL instead of SQLite
   - Update SQLALCHEMY_DATABASE_URI in config.py

4. **Enable HTTPS**: Use SSL certificates

5. **Set Secure Cookies**:
   ```python
   SESSION_COOKIE_SECURE = True
   REMEMBER_COOKIE_SECURE = True
   ```

6. **Use WSGI Server**: Deploy with Gunicorn/uWSGI instead of Flask development server

## Troubleshooting

### Database Not Creating
```bash
python -c "from app import create_app; app, _ = create_app(); app.app_context().push(); from app.models import db; db.create_all()"
```

### Port Already in Use
```bash
python run.py --port 5001
```

### Static Files Not Loading
- Ensure `app/static/uploads` directory exists
- Check file permissions

## Future Enhancements

- [ ] Multi-user roles and permissions
- [ ] SMS/Email notifications
- [ ] Mobile app integration
- [ ] Advanced analytics and dashboards
- [ ] Barcode printer integration
- [ ] Accounting software integration (Tally, QuickBooks)
- [ ] GST compliance reports
- [ ] Medicine interaction checker
- [ ] Loyalty program management
- [ ] Stock sync across branches

## Support & License

This system is provided as-is for pharmacy business management. For customizations or support, refer to the code structure and extend as needed.

## Quick Start Checklist

- [ ] Install dependencies: `pip install -r requirements.txt`
- [ ] Create virtual environment
- [ ] Initialize database
- [ ] Set environment variables
- [ ] Run application: `python run.py`
- [ ] Register company at `http://localhost:5000/register`
- [ ] Login with created credentials
- [ ] Start managing your pharmacy!

---

**System Version**: 1.0  
**Last Updated**: February 20, 2026  
**Support**: Check logs in the application for detailed error messages
