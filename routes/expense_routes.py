from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from models import get_session
from models.expense import Expense
from utils.helpers import (
    admin_required,
    apply_date_range,
    build_base_context,
    parse_date,
    parse_float,
    parse_int,
)


expense_bp = Blueprint("expenses", __name__, url_prefix="/expenses")


@expense_bp.route("/", methods=["GET", "POST"])
def expenses():
    db_session = get_session()

    if request.method == "POST":
        expense_id = parse_int(request.form.get("expense_id"))
        if expense_id and not session.get("admin_logged_in"):
            flash("تعديل المصروفات يحتاج صلاحية المسؤول.", "error")
            return redirect(url_for("admin.login", next=url_for("expenses.expenses")))

        expense = db_session.get(Expense, expense_id) if expense_id else Expense()
        if expense_id and not expense:
            flash("المصروف غير موجود.", "error")
            return redirect(url_for("expenses.expenses"))

        expense.date = parse_date(request.form.get("date"))
        expense.expense_name = request.form.get("expense_name", "").strip()
        expense.amount = parse_float(request.form.get("amount"))

        if not expense.expense_name or expense.amount <= 0:
            flash("يرجى إدخال اسم المصروف وقيمته بشكل صحيح.", "error")
            return redirect(url_for("expenses.expenses"))

        db_session.add(expense)
        db_session.commit()
        flash("تم حفظ المصروف.", "success")
        return redirect(url_for("expenses.expenses"))

    edit_expense = None
    edit_id = parse_int(request.args.get("edit"))
    if edit_id:
        edit_expense = db_session.get(Expense, edit_id)

    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()
    expenses_query = db_session.query(Expense)
    expenses_query = apply_date_range(expenses_query, Expense.date, date_from or None, date_to or None)
    expenses_list = expenses_query.order_by(Expense.date.desc(), Expense.id.desc()).all()
    context = {
        **build_base_context(db_session),
        "page_title": "المصروفات",
        "expenses_list": expenses_list,
        "edit_expense": edit_expense,
        "date_from": date_from,
        "date_to": date_to,
    }
    return render_template("expenses.html", **context)


@expense_bp.route("/<int:expense_id>/confirm-payment", methods=["POST"])
@admin_required
def confirm_expense_payment(expense_id: int):
    db_session = get_session()
    expense = db_session.get(Expense, expense_id)
    if not expense:
        flash("المصروف غير موجود.", "error")
        return redirect(url_for("expenses.expenses"))

    if expense.is_paid:
        flash("تم تأكيد سداد هذا المصروف مسبقاً.", "info")
        return redirect(request.form.get("next") or url_for("expenses.expenses"))

    expense.is_paid = True
    expense.paid_at = datetime.now()
    db_session.add(expense)
    db_session.commit()
    flash("تم تأكيد سداد المصروف.", "success")
    return redirect(request.form.get("next") or url_for("expenses.expenses"))


@expense_bp.route("/<int:expense_id>/delete", methods=["POST"])
@admin_required
def delete_expense(expense_id: int):
    db_session = get_session()
    expense = db_session.get(Expense, expense_id)
    if not expense:
        flash("المصروف غير موجود.", "error")
        return redirect(url_for("expenses.expenses"))

    db_session.delete(expense)
    db_session.commit()
    flash("تم حذف المصروف.", "success")
    return redirect(url_for("expenses.expenses"))
