from flask import Blueprint, flash, redirect, render_template, request, send_file, session, url_for

from models import get_session
from models.special_retailer import SpecialRetailer
from utils.helpers import (
    admin_required,
    allocate_inventory_fifo,
    build_base_context,
    calculate_sale_totals,
    get_fifo_quote,
    get_or_create_settings,
    parse_date,
    parse_float,
    parse_int,
    payment_total_for_retailer,
    restore_inventory_allocations,
    split_phone_numbers,
    update_special_retailer_status,
)
from utils.report_generator import build_pdf


special_retailer_bp = Blueprint(
    "special_retailers", __name__, url_prefix="/special-retailers"
)


@special_retailer_bp.route("/", methods=["GET", "POST"])
def special_retailers():
    db_session = get_session()

    if request.method == "POST":
        retailer_id = parse_int(request.form.get("retailer_id"))
        if retailer_id and not session.get("admin_logged_in"):
            flash("تعديل حركة الدين يحتاج صلاحية المسؤول.", "error")
            return redirect(url_for("admin.login", next=url_for("special_retailers.special_retailers")))

        retailer = (
            db_session.get(SpecialRetailer, retailer_id) if retailer_id else SpecialRetailer()
        )
        if retailer_id and not retailer:
            flash("حركة التاجر غير موجودة.", "error")
            return redirect(url_for("special_retailers.special_retailers"))

        discount_per_unit = parse_float(request.form.get("discount_per_unit"))
        units_count = parse_int(request.form.get("units_count"))
        fruit_name = request.form.get("fruit_name", "").strip()
        class_number = request.form.get("class_number", "").strip()
        retailer_name = request.form.get("retailer_name", "").strip()

        if not retailer_name or not fruit_name or not class_number or units_count <= 0:
            flash("يرجى إدخال اسم التاجر والصنف والدرجة وعدد الوحدات.", "error")
            return redirect(url_for("special_retailers.special_retailers"))

        if retailer_id:
            restore_inventory_allocations(db_session, "special", retailer_id)

        quote = get_fifo_quote(db_session, fruit_name, class_number, units_count)
        if not quote["success"]:
            db_session.rollback()
            flash(quote["message"], "error")
            return redirect(url_for("special_retailers.special_retailers"))

        if discount_per_unit > quote["average_price_per_unit"]:
            db_session.rollback()
            flash("الخصم للوحدة لا يمكن أن يكون أكبر من سعر الوحدة القادم من المخزون.", "error")
            return redirect(url_for("special_retailers.special_retailers"))

        original_price, price_per_unit, total_price, _ = calculate_sale_totals(
            units_count,
            quote["supplier_total_price"],
            discount_per_unit,
        )

        existing_paid = payment_total_for_retailer(db_session, retailer_id) if retailer_id else 0.0
        if total_price < existing_paid:
            db_session.rollback()
            flash("إجمالي الفاتورة الجديدة أقل من المدفوع فعلاً.", "error")
            return redirect(url_for("special_retailers.special_retailers"))

        retailer.date = parse_date(request.form.get("date"))
        retailer.retailer_name = retailer_name
        retailer.fruit_name = fruit_name
        retailer.units_count = units_count
        retailer.class_number = class_number
        retailer.original_price_per_unit = original_price
        retailer.discount_per_unit = discount_per_unit
        retailer.price_per_unit = price_per_unit
        retailer.total_price = total_price
        retailer.total_paid = existing_paid
        retailer.notes = request.form.get("notes", "").strip() or None
        update_special_retailer_status(retailer)

        db_session.add(retailer)
        db_session.flush()

        success, message = allocate_inventory_fifo(
            db_session,
            fruit_name,
            class_number,
            units_count,
            "special",
            retailer.id,
        )
        if not success:
            db_session.rollback()
            flash(message, "error")
            return redirect(url_for("special_retailers.special_retailers"))

        db_session.commit()
        flash("تم حفظ حركة التاجر الآجل.", "success")
        return redirect(url_for("special_retailers.special_retailers"))

    edit_retailer = None
    edit_id = parse_int(request.args.get("edit"))
    if edit_id:
        edit_retailer = db_session.get(SpecialRetailer, edit_id)

    retailers = (
        db_session.query(SpecialRetailer)
        .order_by(SpecialRetailer.date.desc(), SpecialRetailer.id.desc())
        .all()
    )
    context = {
        **build_base_context(db_session),
        "page_title": "تجار الآجل",
        "retailers": retailers,
        "edit_retailer": edit_retailer,
    }
    return render_template("special_retailers.html", **context)


@special_retailer_bp.route("/<int:retailer_id>/delete", methods=["POST"])
@admin_required
def delete_special_retailer(retailer_id: int):
    db_session = get_session()
    retailer = db_session.get(SpecialRetailer, retailer_id)
    if not retailer:
        flash("الحركة غير موجودة.", "error")
        return redirect(url_for("special_retailers.special_retailers"))

    restore_inventory_allocations(db_session, "special", retailer.id)
    db_session.delete(retailer)
    db_session.commit()
    flash("تم حذف حركة الدين وإرجاع المخزون.", "success")
    return redirect(url_for("special_retailers.special_retailers"))


@special_retailer_bp.route("/<int:retailer_id>/receipt")
def special_retailer_receipt(retailer_id: int):
    db_session = get_session()
    settings = get_or_create_settings(db_session)
    retailer = db_session.get(SpecialRetailer, retailer_id)
    if not retailer:
        flash("الحركة غير موجودة.", "error")
        return redirect(url_for("special_retailers.special_retailers"))

    context = {
        **build_base_context(db_session),
        "page_title": "معاينة إيصال الآجل",
        "report_title": "إيصال تاجر آجل",
        "report_subtitle": "معاينة قبل التنزيل أو الطباعة الحرارية.",
        "meta_lines": [
            f"الشركة: {settings.company_name}",
            *[f"الهاتف: {phone}" for phone in split_phone_numbers(settings.phone_number)],
            f"التاجر: {retailer.retailer_name}",
            f"التاريخ: {retailer.date.strftime('%Y-%m-%d %H:%M')}",
        ],
        "table_headers": ["الصنف", "الدرجة", "الوحدات", "سعر الوحدة", "القيمة"],
        "table_rows": [[
            retailer.fruit_name,
            retailer.class_number,
            retailer.units_count,
            f"{retailer.price_per_unit:.2f}",
            f"{retailer.total_price:.2f}",
        ]],
        "summary_lines": [
            ("المدفوع", retailer.total_paid),
            ("المتبقي", retailer.remaining_balance),
            ("الحالة", "مدفوع" if retailer.status == "paid" else ("مدفوع جزئياً" if retailer.status == "partial" else "غير مدفوع")),
        ],
        "download_url": url_for("special_retailers.special_retailer_receipt_pdf", retailer_id=retailer.id),
        "print_mode": "thermal",
    }
    return render_template("print_preview.html", **context)


@special_retailer_bp.route("/<int:retailer_id>/receipt/pdf")
def special_retailer_receipt_pdf(retailer_id: int):
    db_session = get_session()
    settings = get_or_create_settings(db_session)
    retailer = db_session.get(SpecialRetailer, retailer_id)
    if not retailer:
        flash("الحركة غير موجودة.", "error")
        return redirect(url_for("special_retailers.special_retailers"))

    rows = [
        [
            retailer.fruit_name,
            retailer.class_number,
            str(retailer.units_count),
            f"{retailer.price_per_unit:.2f}",
            f"{retailer.total_price:.2f}",
        ],
        [
            "المدفوع",
            retailer.status,
            "-",
            "-",
            f"{retailer.total_paid:.2f}",
        ],
        [
            "المتبقي",
            retailer.status,
            "-",
            "-",
            f"{retailer.remaining_balance:.2f}",
        ],
    ]
    pdf = build_pdf(
        "إيصال تاجر آجل",
        [
            f"الشركة: {settings.company_name}",
            *[f"الهاتف: {phone}" for phone in split_phone_numbers(settings.phone_number)],
            f"التاجر: {retailer.retailer_name}",
            f"التاريخ: {retailer.date.strftime('%Y-%m-%d %H:%M')}",
        ],
        ["الصنف", "الحالة", "الوحدات", "سعر الوحدة", "القيمة"],
        rows,
        paper="thermal",
    )
    return send_file(
        pdf,
        as_attachment=True,
        download_name=f"special-retailer-{retailer.id}.pdf",
        mimetype="application/pdf",
    )
