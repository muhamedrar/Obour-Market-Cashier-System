from flask import Blueprint, flash, redirect, render_template, request, send_file, url_for
from sqlalchemy import or_

from models import get_session
from models.supplier import Supplier
from models.supplier_payment import SupplierPayment
from utils.helpers import (
    admin_required,
    apply_date_range,
    build_base_context,
    get_or_create_settings,
    is_admin_logged_in,
    parse_date,
    parse_float,
    parse_int,
    split_phone_numbers,
    supplier_payment_status,
    supplier_payment_summaries,
    supplier_payment_total_for_supplier,
    supplier_remaining_payout,
    supplier_units_sold,
    update_supplier_totals,
)
from utils.report_generator import build_pdf


supplier_bp = Blueprint("suppliers", __name__, url_prefix="/suppliers")


@supplier_bp.route("/", methods=["GET", "POST"])
def suppliers():
    db_session = get_session()
    settings = get_or_create_settings(db_session)
    is_admin_user = is_admin_logged_in()

    if request.method == "POST":
        supplier_id = parse_int(request.form.get("supplier_id"))
        if supplier_id and not is_admin_user:
            flash("تعديل سجلات الموردين يحتاج صلاحية المسؤول.", "error")
            return redirect(url_for("admin.login", next=url_for("suppliers.suppliers")))

        supplier = db_session.get(Supplier, supplier_id) if supplier_id else Supplier()

        supplier.date = parse_date(request.form.get("date"))
        supplier.supplier_name = request.form.get("supplier_name", "").strip()
        supplier.fruit_name = request.form.get("fruit_name", "").strip()
        supplier.class_number = request.form.get("class_number", "").strip()
        supplier.units_count = parse_int(request.form.get("units_count"))
        supplier.kilograms_per_unit = parse_float(request.form.get("kilograms_per_unit"))
        price_per_kilogram = parse_float(request.form.get("price_per_kilogram"))
        supplier.price_per_unit = round(price_per_kilogram * supplier.kilograms_per_unit, 2)
        supplier.supplier_profit_percentage = (
            parse_float(
                request.form.get("supplier_profit_percentage"),
                settings.supplier_profit_percentage,
            )
            if is_admin_user
            else (
                supplier.supplier_profit_percentage
                if supplier_id and supplier
                else settings.supplier_profit_percentage
            )
        )
        supplier.notes = request.form.get("notes", "").strip() or None

        if not supplier.supplier_name or not supplier.fruit_name or not supplier.class_number:
            flash("يرجى إدخال اسم المورد والصنف والدرجة.", "error")
            return redirect(url_for("suppliers.suppliers"))

        if (
            supplier.units_count <= 0
            or supplier.price_per_unit < 0
            or supplier.kilograms_per_unit <= 0
            or price_per_kilogram < 0
        ):
            flash("عدد الوحدات والسعر والوزن لكل وحدة يجب أن تكون قيمهم صالحة.", "error")
            return redirect(url_for("suppliers.suppliers"))
        if supplier.supplier_profit_percentage < 0 or supplier.supplier_profit_percentage > 100:
            flash("نسبة ربح المحل من المورد يجب أن تكون بين 0 و100.", "error")
            return redirect(url_for("suppliers.suppliers"))

        sold_units = supplier_units_sold(db_session, supplier) if supplier_id else 0
        if supplier.units_count < sold_units:
            flash("لا يمكن تقليل الكمية عن الوحدات التي تم بيعها بالفعل.", "error")
            return redirect(url_for("suppliers.suppliers"))

        supplier.remaining_units = supplier.units_count - sold_units
        update_supplier_totals(supplier)
        if supplier_id and supplier_payment_total_for_supplier(db_session, supplier_id) > supplier.supplier_payout_total:
            flash("لا يمكن تعديل المورد بحيث يصبح مستحقه أقل من المدفوع له بالفعل.", "error")
            return redirect(url_for("suppliers.suppliers"))
        db_session.add(supplier)
        db_session.commit()

        flash("تم حفظ المورد بنجاح.", "success")
        return redirect(url_for("suppliers.suppliers"))

    edit_supplier = None
    edit_id = parse_int(request.args.get("edit"))
    if edit_id:
        if not is_admin_user:
            flash("تعديل سجلات الموردين يحتاج صلاحية المسؤول.", "error")
            return redirect(url_for("admin.login", next=url_for("suppliers.suppliers")))
        edit_supplier = db_session.get(Supplier, edit_id)

    search_query = request.args.get("q", "").strip()
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()
    status_filter = request.args.get("status", "").strip()
    suppliers_query = db_session.query(Supplier)
    if search_query:
        like_value = f"%{search_query}%"
        suppliers_query = suppliers_query.filter(
            or_(
                Supplier.supplier_name.ilike(like_value),
                Supplier.fruit_name.ilike(like_value),
                Supplier.class_number.ilike(like_value),
                Supplier.notes.ilike(like_value),
            )
        )
    suppliers_query = apply_date_range(suppliers_query, Supplier.date, date_from or None, date_to or None)
    if status_filter == "active":
        suppliers_query = suppliers_query.filter(Supplier.remaining_units > 0)
    elif status_filter == "cleared":
        suppliers_query = suppliers_query.filter(Supplier.remaining_units <= 0)

    suppliers_list = suppliers_query.order_by(Supplier.date.desc(), Supplier.id.desc()).all()
    payment_summaries = supplier_payment_summaries(db_session, [supplier.id for supplier in suppliers_list])
    for supplier in suppliers_list:
        payment_summary = payment_summaries.get(
            supplier.id,
            {"total_paid": 0.0, "last_payment_date": None},
        )
        supplier.total_paid_to_supplier = payment_summary["total_paid"]
        supplier.remaining_payout_balance = supplier_remaining_payout(
            supplier.supplier_payout_total,
            payment_summary["total_paid"],
        )
        supplier.payment_status = supplier_payment_status(
            supplier.supplier_payout_total,
            payment_summary["total_paid"],
        )
        supplier.last_payment_date = payment_summary["last_payment_date"]
    context = {
        **build_base_context(db_session),
        "page_title": "الموردون",
        "suppliers_list": suppliers_list,
        "edit_supplier": edit_supplier,
        "search_query": search_query,
        "date_from": date_from,
        "date_to": date_to,
        "status_filter": status_filter,
    }
    return render_template("suppliers.html", **context)


@supplier_bp.route("/<int:supplier_id>/pay", methods=["POST"])
@admin_required
def pay_supplier(supplier_id: int):
    db_session = get_session()
    supplier = db_session.get(Supplier, supplier_id)
    if not supplier:
        flash("المورد غير موجود.", "error")
        return redirect(url_for("suppliers.suppliers"))

    amount_paid = parse_float(request.form.get("amount_paid"))
    if amount_paid <= 0:
        flash("قيمة الدفعة يجب أن تكون أكبر من صفر.", "error")
        return redirect(request.form.get("next") or url_for("suppliers.suppliers"))

    total_paid = supplier_payment_total_for_supplier(db_session, supplier.id)
    remaining_balance = supplier_remaining_payout(supplier.supplier_payout_total, total_paid)
    if amount_paid > remaining_balance:
        flash("قيمة الدفعة تتجاوز مستحق المورد المتبقي.", "error")
        return redirect(request.form.get("next") or url_for("suppliers.suppliers"))

    db_session.add(
        SupplierPayment(
            supplier_id=supplier.id,
            amount_paid=amount_paid,
            notes=request.form.get("notes", "").strip() or None,
        )
    )
    db_session.commit()
    flash("تم تسجيل دفعة المورد.", "success")
    return redirect(request.form.get("next") or url_for("suppliers.suppliers"))


@supplier_bp.route("/<int:supplier_id>/confirm-payment", methods=["POST"])
@admin_required
def confirm_supplier_payment(supplier_id: int):
    db_session = get_session()
    supplier = db_session.get(Supplier, supplier_id)
    if not supplier:
        flash("المورد غير موجود.", "error")
        return redirect(url_for("suppliers.suppliers"))

    total_paid = supplier_payment_total_for_supplier(db_session, supplier.id)
    remaining_balance = supplier_remaining_payout(supplier.supplier_payout_total, total_paid)
    if remaining_balance <= 0:
        flash("تم سداد مستحق المورد بالكامل بالفعل.", "info")
        return redirect(request.form.get("next") or url_for("suppliers.suppliers"))

    db_session.add(SupplierPayment(supplier_id=supplier.id, amount_paid=remaining_balance))
    db_session.commit()
    flash("تم سداد كامل مستحق المورد.", "success")
    return redirect(request.form.get("next") or url_for("suppliers.suppliers"))


@supplier_bp.route("/<int:supplier_id>/receipt")
def supplier_receipt(supplier_id: int):
    db_session = get_session()
    settings = get_or_create_settings(db_session)
    supplier = db_session.get(Supplier, supplier_id)
    if not supplier:
        flash("المورد غير موجود.", "error")
        return redirect(url_for("suppliers.suppliers"))
    total_paid = supplier_payment_total_for_supplier(db_session, supplier.id)
    remaining_balance = supplier_remaining_payout(supplier.supplier_payout_total, total_paid)
    payment_status = supplier_payment_status(supplier.supplier_payout_total, total_paid)

    context = {
        **build_base_context(db_session),
        "page_title": "معاينة إيصال المورد",
        "report_title": "إيصال مورد",
        "report_subtitle": "معاينة حرارية قبل التنزيل أو الطباعة.",
        "meta_lines": [
            f"الشركة: {settings.company_name}",
            *[f"الهاتف: {phone}" for phone in split_phone_numbers(settings.phone_number)],
            f"المورد: {supplier.supplier_name}",
            f"التاريخ: {supplier.date.strftime('%Y-%m-%d %H:%M')}",
        ],
        "table_headers": ["الصنف", "الدرجة", "الوحدات", "كجم/وحدة", "الإجمالي الخام"],
        "table_rows": [[
            supplier.fruit_name,
            supplier.class_number,
            str(supplier.units_count),
            f"{supplier.kilograms_per_unit:.2f}",
            f"{supplier.total_price:.2f}",
        ]],
        "summary_lines": [
            ("نسبة ربح المحل", f"{supplier.supplier_profit_percentage:.2f}%"),
            ("ربح المحل من المورد", supplier.company_profit_total),
            ("مستحق المورد", supplier.supplier_payout_total),
            ("المدفوع للمورد", total_paid),
            ("المتبقي للمورد", remaining_balance),
            ("حالة السداد", "مدفوع" if payment_status == "paid" else ("مدفوع جزئياً" if payment_status == "partial" else "غير مدفوع")),
            ("سعر الوحدة", supplier.price_per_unit),
            ("إجمالي الوزن", f"{supplier.total_kilograms:.2f} كجم"),
            ("الوحدات المباعة", str(supplier.units_count - supplier.remaining_units)),
            ("الوحدات المتبقية", str(supplier.remaining_units)),
        ],
        "download_url": url_for("suppliers.supplier_receipt_pdf", supplier_id=supplier.id),
        "print_mode": "thermal",
    }
    return render_template("print_preview.html", **context)


@supplier_bp.route("/<int:supplier_id>/receipt/pdf")
def supplier_receipt_pdf(supplier_id: int):
    db_session = get_session()
    settings = get_or_create_settings(db_session)
    supplier = db_session.get(Supplier, supplier_id)
    if not supplier:
        flash("المورد غير موجود.", "error")
        return redirect(url_for("suppliers.suppliers"))
    total_paid = supplier_payment_total_for_supplier(db_session, supplier.id)
    remaining_balance = supplier_remaining_payout(supplier.supplier_payout_total, total_paid)
    payment_status = supplier_payment_status(supplier.supplier_payout_total, total_paid)

    pdf = build_pdf(
        "إيصال مورد",
        [
            f"الشركة: {settings.company_name}",
            *[f"الهاتف: {phone}" for phone in split_phone_numbers(settings.phone_number)],
            f"المورد: {supplier.supplier_name}",
            f"التاريخ: {supplier.date.strftime('%Y-%m-%d %H:%M')}",
            f"كجم لكل وحدة: {supplier.kilograms_per_unit:.2f}",
            f"نسبة ربح المحل: {supplier.supplier_profit_percentage:.2f}%",
            f"ربح المحل: {supplier.company_profit_total:.2f}",
            f"مستحق المورد: {supplier.supplier_payout_total:.2f}",
            f"المدفوع للمورد: {total_paid:.2f}",
            f"المتبقي للمورد: {remaining_balance:.2f}",
            f"حالة السداد: {'مدفوع' if payment_status == 'paid' else ('مدفوع جزئياً' if payment_status == 'partial' else 'غير مدفوع')}",
        ],
        ["الصنف", "الدرجة", "الوحدات", "كجم/وحدة", "الإجمالي"],
        [[
            supplier.fruit_name,
            supplier.class_number,
            str(supplier.units_count),
            f"{supplier.kilograms_per_unit:.2f}",
            f"{supplier.total_price:.2f}",
        ]],
        paper="thermal",
    )
    return send_file(
        pdf,
        as_attachment=True,
        download_name=f"supplier-receipt-{supplier.id}.pdf",
        mimetype="application/pdf",
    )


@supplier_bp.route("/<int:supplier_id>/delete", methods=["POST"])
@admin_required
def delete_supplier(supplier_id: int):
    db_session = get_session()
    supplier = db_session.get(Supplier, supplier_id)
    if not supplier:
        flash("المورد غير موجود.", "error")
        return redirect(url_for("suppliers.suppliers"))

    if supplier_payment_total_for_supplier(db_session, supplier.id) > 0:
        flash("لا يمكن حذف مورد تم تسجيل دفعات له.", "error")
        return redirect(url_for("suppliers.suppliers"))

    if supplier_units_sold(db_session, supplier) > 0:
        flash("لا يمكن حذف مورد مرتبط بحركات بيع. عدّل السجل بدلاً من ذلك.", "error")
        return redirect(url_for("suppliers.suppliers"))

    db_session.delete(supplier)
    db_session.commit()
    flash("تم حذف المورد.", "success")
    return redirect(url_for("suppliers.suppliers"))
