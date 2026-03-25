from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from sqlalchemy import func, select

from models import get_session
from models.payment import Payment
from models.special_retailer import SpecialRetailer
from utils.helpers import (
    admin_required,
    build_base_context,
    parse_date,
    parse_float,
    parse_int,
    update_special_retailer_status,
)


payment_bp = Blueprint("payments", __name__, url_prefix="/payments")


@payment_bp.route("/", methods=["GET", "POST"])
def payments():
    db_session = get_session()

    if request.method == "POST":
        payment_id = parse_int(request.form.get("payment_id"))
        if payment_id and not session.get("admin_logged_in"):
            flash("تعديل الدفعات يحتاج صلاحية المسؤول.", "error")
            return redirect(url_for("admin.login", next=url_for("payments.payments")))

        payment = db_session.get(Payment, payment_id) if payment_id else None
        if payment_id and not payment:
            flash("الدفعة غير موجودة.", "error")
            return redirect(url_for("payments.payments"))

        retailer_id = payment.retailer_id if payment else parse_int(request.form.get("retailer_id"))
        retailer = db_session.get(SpecialRetailer, retailer_id)
        if not retailer:
            flash("التاجر غير موجود.", "error")
            return redirect(url_for("payments.payments"))

        if not payment:
            payment = Payment(retailer_id=retailer_id)

        amount_paid = parse_float(request.form.get("amount_paid"))
        if amount_paid <= 0:
            flash("قيمة الدفعة يجب أن تكون أكبر من صفر.", "error")
            return redirect(url_for("payments.payments"))

        query = select(func.coalesce(func.sum(Payment.amount_paid), 0)).where(
            Payment.retailer_id == retailer.id
        )
        if payment.id:
            query = query.where(Payment.id != payment.id)
        other_payments_total = db_session.scalar(query) or 0
        max_allowed = round(retailer.total_price - other_payments_total, 2)
        if amount_paid > max_allowed:
            flash("قيمة الدفعة تتجاوز الرصيد المتبقي.", "error")
            return redirect(url_for("payments.payments"))

        payment.payment_date = parse_date(request.form.get("payment_date"))
        payment.amount_paid = amount_paid
        payment.notes = request.form.get("notes", "").strip() or None

        db_session.add(payment)
        db_session.flush()

        retailer.total_paid = round(other_payments_total + amount_paid, 2)
        update_special_retailer_status(retailer)
        db_session.commit()

        flash("تم حفظ الدفعة وتحديث الرصيد.", "success")
        return redirect(url_for("payments.payments", retailer=retailer.id))

    edit_payment = None
    edit_id = parse_int(request.args.get("edit"))
    if edit_id:
        edit_payment = db_session.get(Payment, edit_id)

    selected_retailer = None
    retailer_query_id = parse_int(request.args.get("retailer"))
    if retailer_query_id:
        selected_retailer = db_session.get(SpecialRetailer, retailer_query_id)

    retailers = (
        db_session.query(SpecialRetailer)
        .order_by(SpecialRetailer.remaining_balance.desc(), SpecialRetailer.date.desc())
        .all()
    )
    payments_list = (
        db_session.query(Payment).order_by(Payment.payment_date.desc(), Payment.id.desc()).all()
    )
    context = {
        **build_base_context(db_session),
        "page_title": "الدفعات",
        "retailers": retailers,
        "payments_list": payments_list,
        "selected_retailer": selected_retailer,
        "edit_payment": edit_payment,
    }
    return render_template("payments.html", **context)


@payment_bp.route("/<int:payment_id>/delete", methods=["POST"])
@admin_required
def delete_payment(payment_id: int):
    db_session = get_session()
    payment = db_session.get(Payment, payment_id)
    if not payment:
        flash("الدفعة غير موجودة.", "error")
        return redirect(url_for("payments.payments"))

    retailer = payment.retailer
    db_session.delete(payment)
    db_session.flush()

    remaining_total_paid = db_session.scalar(
        select(func.coalesce(func.sum(Payment.amount_paid), 0)).where(Payment.retailer_id == retailer.id)
    ) or 0
    retailer.total_paid = round(remaining_total_paid, 2)
    update_special_retailer_status(retailer)
    db_session.commit()

    flash("تم حذف الدفعة وتحديث الرصيد.", "success")
    return redirect(url_for("payments.payments", retailer=retailer.id))
