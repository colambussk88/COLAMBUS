from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app.utils import require_roles
from app.models import db, Doctor
from datetime import datetime

doctors_bp = Blueprint('doctors', __name__, url_prefix='/doctors')


@doctors_bp.route('/')
@login_required
def doctors_list():
    company_id = current_user.company_id
    doctors = Doctor.query.filter_by(company_id=company_id).order_by(Doctor.name).all()
    return render_template('doctors/list.html', doctors=doctors)


@doctors_bp.route('/add', methods=['GET', 'POST'])
@login_required
@require_roles('owner', 'manager')
def add_doctor():
    if request.method == 'POST':
        try:
            doc = Doctor(
                company_id=current_user.company_id,
                name=request.form.get('name'),
                phone=request.form.get('phone'),
                clinic=request.form.get('clinic'),
                notes=request.form.get('notes')
            )
            db.session.add(doc)
            db.session.commit()
            flash('Doctor added.', 'success')
            return redirect(url_for('doctors.doctors_list'))
        except Exception as e:
            db.session.rollback()
            flash(f'Failed to add doctor: {e}', 'danger')
            return redirect(url_for('doctors.add_doctor'))
    return render_template('doctors/add.html')


@doctors_bp.route('/<int:doctor_id>/edit', methods=['GET', 'POST'])
@login_required
@require_roles('owner', 'manager')
def edit_doctor(doctor_id):
    doc = Doctor.query.get(doctor_id)
    if not doc or doc.company_id != current_user.company_id:
        flash('Doctor not found.', 'danger')
        return redirect(url_for('doctors.doctors_list'))
    if request.method == 'POST':
        try:
            doc.name = request.form.get('name', doc.name)
            doc.phone = request.form.get('phone', doc.phone)
            doc.clinic = request.form.get('clinic', doc.clinic)
            doc.notes = request.form.get('notes', doc.notes)
            db.session.commit()
            flash('Doctor updated.', 'success')
            return redirect(url_for('doctors.doctors_list'))
        except Exception as e:
            db.session.rollback()
            flash(f'Failed to update doctor: {e}', 'danger')
            return redirect(url_for('doctors.edit_doctor', doctor_id=doctor_id))
    return render_template('doctors/edit.html', doctor=doc)


@doctors_bp.route('/<int:doctor_id>/delete', methods=['POST'])
@login_required
@require_roles('owner', 'manager')
def delete_doctor(doctor_id):
    doc = Doctor.query.get(doctor_id)
    if not doc or doc.company_id != current_user.company_id:
        flash('Doctor not found.', 'danger')
        return redirect(url_for('doctors.doctors_list'))
    try:
        db.session.delete(doc)
        db.session.commit()
        flash('Doctor deleted.', 'success')
        return redirect(url_for('doctors.doctors_list'))
    except Exception as e:
        db.session.rollback()
        flash(f'Failed to delete doctor: {e}', 'danger')
        return redirect(url_for('doctors.doctors_list'))