from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.models import db, Category, Unit

master_bp = Blueprint('master', __name__, url_prefix='/master')


@master_bp.route('/categories')
@login_required
def categories_list():
    cats = Category.query.filter_by(company_id=current_user.company_id).order_by(Category.name).all()
    return render_template('master/categories_list.html', categories=cats)


@master_bp.route('/categories/add', methods=['GET', 'POST'])
@login_required
def add_category():
    if request.method == 'POST':
        name = request.form.get('name')
        if not name:
            flash('Name is required', 'danger')
            return redirect(url_for('master.add_category'))
        cat = Category(company_id=current_user.company_id, name=name, description=request.form.get('description'))
        db.session.add(cat)
        db.session.commit()
        flash('Category added', 'success')
        return redirect(url_for('master.categories_list'))
    return render_template('master/category_form.html', category=None)


@master_bp.route('/categories/<int:cat_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_category(cat_id):
    cat = Category.query.get_or_404(cat_id)
    if cat.company_id != current_user.company_id:
        flash('Not found', 'danger')
        return redirect(url_for('master.categories_list'))
    if request.method == 'POST':
        cat.name = request.form.get('name', cat.name)
        cat.description = request.form.get('description', cat.description)
        db.session.commit()
        flash('Category updated', 'success')
        return redirect(url_for('master.categories_list'))
    return render_template('master/category_form.html', category=cat)


@master_bp.route('/categories/<int:cat_id>/delete', methods=['POST'])
@login_required
def delete_category(cat_id):
    cat = Category.query.get_or_404(cat_id)
    if cat.company_id != current_user.company_id:
        flash('Not found', 'danger')
        return redirect(url_for('master.categories_list'))
    cat.is_active = False
    db.session.commit()
    flash('Category disabled', 'success')
    return redirect(url_for('master.categories_list'))


@master_bp.route('/units')
@login_required
def units_list():
    units = Unit.query.filter_by(company_id=current_user.company_id).order_by(Unit.name).all()
    return render_template('master/units_list.html', units=units)


@master_bp.route('/units/add', methods=['GET', 'POST'])
@login_required
def add_unit():
    if request.method == 'POST':
        name = request.form.get('name')
        if not name:
            flash('Name is required', 'danger')
            return redirect(url_for('master.add_unit'))
        u = Unit(company_id=current_user.company_id, name=name, abbreviation=request.form.get('abbreviation'))
        db.session.add(u)
        db.session.commit()
        flash('Unit added', 'success')
        return redirect(url_for('master.units_list'))
    return render_template('master/unit_form.html', unit=None)


@master_bp.route('/units/<int:unit_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_unit(unit_id):
    u = Unit.query.get_or_404(unit_id)
    if u.company_id != current_user.company_id:
        flash('Not found', 'danger')
        return redirect(url_for('master.units_list'))
    if request.method == 'POST':
        u.name = request.form.get('name', u.name)
        u.abbreviation = request.form.get('abbreviation', u.abbreviation)
        db.session.commit()
        flash('Unit updated', 'success')
        return redirect(url_for('master.units_list'))
    return render_template('master/unit_form.html', unit=u)


@master_bp.route('/units/<int:unit_id>/delete', methods=['POST'])
@login_required
def delete_unit(unit_id):
    u = Unit.query.get_or_404(unit_id)
    if u.company_id != current_user.company_id:
        flash('Not found', 'danger')
        return redirect(url_for('master.units_list'))
    u.is_active = False
    db.session.commit()
    flash('Unit disabled', 'success')
    return redirect(url_for('master.units_list'))