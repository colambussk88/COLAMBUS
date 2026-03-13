from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import uuid

db = SQLAlchemy()


class Company(db.Model):
    """Company/Pharmacy model - single tenant"""
    __tablename__ = 'company'
    
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.String(36), unique=True, default=lambda: str(uuid.uuid4()))
    company_name = db.Column(db.String(255), nullable=False)
    owner_name = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    address = db.Column(db.String(500), nullable=False)
    city = db.Column(db.String(100), nullable=False)
    state = db.Column(db.String(100), nullable=False)
    country = db.Column(db.String(100), nullable=False)
    postal_code = db.Column(db.String(20), nullable=False)
    gst_number = db.Column(db.String(50), unique=True)
    drug_license_number = db.Column(db.String(100), unique=True)
    logo_path = db.Column(db.String(500))
    is_active = db.Column(db.Boolean, default=True)
    created_date = db.Column(db.DateTime, default=datetime.utcnow)
    updated_date = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', back_populates='company', uselist=False, cascade='all, delete-orphan')
    products = db.relationship('Product', back_populates='company', cascade='all, delete-orphan')
    sales = db.relationship('Sale', back_populates='company', cascade='all, delete-orphan')
    purchases = db.relationship('Purchase', back_populates='company', cascade='all, delete-orphan')
    customers = db.relationship('Customer', back_populates='company', cascade='all, delete-orphan')
    suppliers = db.relationship('Supplier', back_populates='company', cascade='all, delete-orphan')
    expenses = db.relationship('Expense', back_populates='company', cascade='all, delete-orphan')
    alerts = db.relationship('Alert', back_populates='company', cascade='all, delete-orphan')


class User(UserMixin, db.Model):
    """User model - single user per company"""
    __tablename__ = 'user'
    
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    # Role: 'owner' or 'manager' (can extend later)
    role = db.Column(db.String(20), default='manager')
    username = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    last_login = db.Column(db.DateTime)
    created_date = db.Column(db.DateTime, default=datetime.utcnow)
    updated_date = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    company = db.relationship('Company', back_populates='user')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Product(db.Model):
    """Product model"""
    __tablename__ = 'product'
    
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    product_name = db.Column(db.String(255), nullable=False)
    generic_name = db.Column(db.String(255))
    brand = db.Column(db.String(255))
    category = db.Column(db.String(100), nullable=False)
    manufacturer = db.Column(db.String(255))
    batch_number = db.Column(db.String(100))
    barcode = db.Column(db.String(100), unique=True)
    sku = db.Column(db.String(100), unique=True, nullable=False)
    purchase_price = db.Column(db.Float, nullable=False)
    selling_price = db.Column(db.Float, nullable=False)
    mrp = db.Column(db.Float, nullable=False)
    tax_percentage = db.Column(db.Float, default=0)
    manufacturing_date = db.Column(db.DateTime)
    expiry_date = db.Column(db.DateTime)
    quantity = db.Column(db.Integer, default=0)
    minimum_stock_level = db.Column(db.Integer, default=10)
    reorder_level = db.Column(db.Integer, default=20)
    prescription_required = db.Column(db.Boolean, default=False)
    description = db.Column(db.Text)
    image_path = db.Column(db.String(500))
    created_date = db.Column(db.DateTime, default=datetime.utcnow)
    updated_date = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    
    company = db.relationship('Company', back_populates='products')
    stock_movements = db.relationship('StockMovement', back_populates='product', cascade='all, delete-orphan')
    sale_items = db.relationship('SaleItem', back_populates='product', cascade='all, delete-orphan')
    purchase_items = db.relationship('PurchaseItem', back_populates='product', cascade='all, delete-orphan')

    # New master references
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'))
    unit_id = db.Column(db.Integer, db.ForeignKey('unit.id'))

    category_rel = db.relationship('Category', back_populates='products')
    unit_rel = db.relationship('Unit', back_populates='products')


class StockMovement(db.Model):
    """Stock movement history"""
    __tablename__ = 'stock_movement'
    
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    movement_type = db.Column(db.String(50), nullable=False)  # 'purchase', 'sale', 'adjustment', 'return'
    quantity = db.Column(db.Integer, nullable=False)
    batch_number = db.Column(db.String(100))
    reference_id = db.Column(db.Integer)  # sale_id or purchase_id
    reason = db.Column(db.String(255))  # For adjustments
    created_date = db.Column(db.DateTime, default=datetime.utcnow)
    
    product = db.relationship('Product', back_populates='stock_movements')


class Category(db.Model):
    """Master category for products"""
    __tablename__ = 'category'

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(255))
    is_active = db.Column(db.Boolean, default=True)
    created_date = db.Column(db.DateTime, default=datetime.utcnow)

    company = db.relationship('Company')
    products = db.relationship('Product', back_populates='category_rel')


class Unit(db.Model):
    """Unit of measure master table (mg, ml, tablet, capsule, etc.)"""
    __tablename__ = 'unit'

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    name = db.Column(db.String(50), nullable=False)
    abbreviation = db.Column(db.String(20))
    is_active = db.Column(db.Boolean, default=True)
    created_date = db.Column(db.DateTime, default=datetime.utcnow)

    company = db.relationship('Company')
    products = db.relationship('Product', back_populates='unit_rel')


class Customer(db.Model):
    """Customer model"""
    __tablename__ = 'customer'
    
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    customer_name = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(255), unique=True)
    address = db.Column(db.String(500))
    gst_number = db.Column(db.String(50))
    credit_limit = db.Column(db.Float, default=0)
    current_balance = db.Column(db.Float, default=0)
    created_date = db.Column(db.DateTime, default=datetime.utcnow)
    updated_date = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    
    company = db.relationship('Company', back_populates='customers')
    sales = db.relationship('Sale', back_populates='customer')


class Supplier(db.Model):
    """Supplier model"""
    __tablename__ = 'supplier'
    
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    supplier_name = db.Column(db.String(255), nullable=False)
    contact_person = db.Column(db.String(255))
    phone = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(255))
    address = db.Column(db.String(500))
    gst_number = db.Column(db.String(50))
    payment_terms = db.Column(db.String(255))
    notes = db.Column(db.Text)
    created_date = db.Column(db.DateTime, default=datetime.utcnow)
    updated_date = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    
    company = db.relationship('Company', back_populates='suppliers')
    purchases = db.relationship('Purchase', back_populates='supplier')


class Sale(db.Model):
    """Sales/Invoice model"""
    __tablename__ = 'sale'
    
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'))
    invoice_number = db.Column(db.String(50), unique=True, nullable=False)
    invoice_date = db.Column(db.DateTime, default=datetime.utcnow)
    customer_name = db.Column(db.String(255))
    customer_phone = db.Column(db.String(20))
    subtotal = db.Column(db.Float, nullable=False)
    tax_amount = db.Column(db.Float, default=0)
    discount_amount = db.Column(db.Float, default=0)
    total_amount = db.Column(db.Float, nullable=False)
    payment_method = db.Column(db.String(50), nullable=False)  # 'cash', 'card', 'upi', 'bank', 'credit'
    payment_status = db.Column(db.String(50), default='paid')  # 'paid', 'pending', 'partial'
    notes = db.Column(db.Text)
    is_cancelled = db.Column(db.Boolean, default=False)
    cancellation_reason = db.Column(db.String(255))
    created_date = db.Column(db.DateTime, default=datetime.utcnow)
    updated_date = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    company = db.relationship('Company', back_populates='sales')
    customer = db.relationship('Customer', back_populates='sales')
    items = db.relationship('SaleItem', back_populates='sale', cascade='all, delete-orphan')
    returns = db.relationship('SalesReturn', back_populates='sale', cascade='all, delete-orphan')
    # Optional consulting doctor for this sale
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctor.id'))
    doctor = db.relationship('Doctor', back_populates='consultations')


class SaleItem(db.Model):
    """Individual items in a sale"""
    __tablename__ = 'sale_item'
    
    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey('sale.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    batch_number = db.Column(db.String(100))
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Float, nullable=False)
    tax_percentage = db.Column(db.Float, default=0)
    tax_amount = db.Column(db.Float, default=0)
    discount_percentage = db.Column(db.Float, default=0)
    discount_amount = db.Column(db.Float, default=0)
    total_amount = db.Column(db.Float, nullable=False)
    
    sale = db.relationship('Sale', back_populates='items')
    product = db.relationship('Product', back_populates='sale_items')


class SalesReturn(db.Model):
    """Sales return/credit note model"""
    __tablename__ = 'sales_return'
    
    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey('sale.id'), nullable=False)
    credit_note_number = db.Column(db.String(50), unique=True, nullable=False)
    return_date = db.Column(db.DateTime, default=datetime.utcnow)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'))
    quantity = db.Column(db.Integer, nullable=False)
    is_full_return = db.Column(db.Boolean, default=False)
    reason = db.Column(db.String(255))
    refund_amount = db.Column(db.Float, nullable=False)
    refund_mode = db.Column(db.String(50))  # 'cash', 'card', 'upi', etc.
    
    sale = db.relationship('Sale', back_populates='returns')


class Purchase(db.Model):
    """Purchase order model"""
    __tablename__ = 'purchase'
    
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    supplier_id = db.Column(db.Integer, db.ForeignKey('supplier.id'), nullable=False)
    purchase_number = db.Column(db.String(50), unique=True, nullable=False)
    purchase_date = db.Column(db.DateTime, default=datetime.utcnow)
    supplier_invoice_number = db.Column(db.String(100))
    subtotal = db.Column(db.Float, nullable=False)
    tax_amount = db.Column(db.Float, default=0)
    discount_amount = db.Column(db.Float, default=0)
    total_amount = db.Column(db.Float, nullable=False)
    payment_status = db.Column(db.String(50), default='pending')  # 'paid', 'pending', 'partial'
    payment_date = db.Column(db.DateTime)
    notes = db.Column(db.Text)
    created_date = db.Column(db.DateTime, default=datetime.utcnow)
    updated_date = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    company = db.relationship('Company', back_populates='purchases')
    supplier = db.relationship('Supplier', back_populates='purchases')
    items = db.relationship('PurchaseItem', back_populates='purchase', cascade='all, delete-orphan')
    returns = db.relationship('PurchaseReturn', back_populates='purchase', cascade='all, delete-orphan')


class PurchaseItem(db.Model):
    """Individual items in a purchase"""
    __tablename__ = 'purchase_item'
    
    id = db.Column(db.Integer, primary_key=True)
    purchase_id = db.Column(db.Integer, db.ForeignKey('purchase.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    batch_number = db.Column(db.String(100), nullable=False)
    expiry_date = db.Column(db.DateTime, nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Float, nullable=False)
    tax_percentage = db.Column(db.Float, default=0)
    tax_amount = db.Column(db.Float, default=0)
    discount_percentage = db.Column(db.Float, default=0)
    discount_amount = db.Column(db.Float, default=0)
    total_amount = db.Column(db.Float, nullable=False)
    
    purchase = db.relationship('Purchase', back_populates='items')
    product = db.relationship('Product', back_populates='purchase_items')


class PurchaseReturn(db.Model):
    """Purchase return model"""
    __tablename__ = 'purchase_return'
    
    id = db.Column(db.Integer, primary_key=True)
    purchase_id = db.Column(db.Integer, db.ForeignKey('purchase.id'), nullable=False)
    return_date = db.Column(db.DateTime, default=datetime.utcnow)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'))
    batch_number = db.Column(db.String(100))
    quantity = db.Column(db.Integer, nullable=False)
    reason = db.Column(db.String(255))
    credit_amount = db.Column(db.Float, nullable=False)
    
    purchase = db.relationship('Purchase', back_populates='returns')


class Expense(db.Model):
    """Expense/Operational costs model"""
    __tablename__ = 'expense'
    
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    expense_category = db.Column(db.String(100), nullable=False)  # 'rent', 'utilities', 'staff', etc.
    description = db.Column(db.String(255), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    receipt_image = db.Column(db.String(500))
    expense_date = db.Column(db.DateTime, nullable=False)
    created_date = db.Column(db.DateTime, default=datetime.utcnow)
    
    company = db.relationship('Company', back_populates='expenses')


class Alert(db.Model):
    """Alert/Notification model"""
    __tablename__ = 'alert'
    
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    alert_type = db.Column(db.String(50), nullable=False)  # 'low_stock', 'expiry', 'payment_due', 'payment_pending'
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'))
    title = db.Column(db.String(255), nullable=False)
    message = db.Column(db.Text, nullable=False)
    severity = db.Column(db.String(20), default='info')  # 'info', 'warning', 'critical'
    is_read = db.Column(db.Boolean, default=False)
    created_date = db.Column(db.DateTime, default=datetime.utcnow)
    
    company = db.relationship('Company', back_populates='alerts')


class Doctor(db.Model):
    """Consulting doctor model"""
    __tablename__ = 'doctor'

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(50))
    clinic = db.Column(db.String(255))
    notes = db.Column(db.Text)
    created_date = db.Column(db.DateTime, default=datetime.utcnow)

    company = db.relationship('Company')
    consultations = db.relationship('Sale', back_populates='doctor')


class AdminLog(db.Model):
    """Simple audit log for admin actions (credential changes, etc.)"""
    __tablename__ = 'admin_log'

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'))
    performed_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    action = db.Column(db.String(100), nullable=False)
    details = db.Column(db.Text)
    created_date = db.Column(db.DateTime, default=datetime.utcnow)

    company = db.relationship('Company')
    performer = db.relationship('User')