from flask import Blueprint, flash, redirect, render_template, request, send_file, session, url_for

from models import get_session
from models.special_retailer import SpecialRetailer
from utils.helpers import (
    admin_required,
    allocate_inventory_fifo,
    apply_date_range,
    available_goods,
    build_base_context,
    calculate_sale_totals,
    effective_commission_per_unit,
    get_fifo_quote,
    get_or_create_settings,
    normalize_discount_mode,
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
    settings = get_or_create_settings(db_session)

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

        discount_per_unit = (
            parse_float(request.form.get("discount_per_unit"))
            if session.get("admin_logged_in")
            else 0.0
        )
        units_count = parse_int(request.form.get("units_count"))
        fruit_name = request.form.get("fruit_name", "").strip()
        class_number = request.form.get("class_number", "").strip()
        kilograms_per_unit = parse_float(request.form.get("kilograms_per_unit"))
        retailer_name = request.form.get("retailer_name", "").strip()
        discount_mode = (
            normalize_discount_mode(request.form.get("discount_mode"))
            if session.get("admin_logged_in")
            else "commission"
        )

        if not retailer_name or not fruit_name or not class_number or kilograms_per_unit <= 0 or units_count <= 0:
            flash("يرجى إدخال اسم التاجر والصنف والدرجة وكجم/وحدة وعدد الوحدات.", "error")
            return redirect(url_for("special_retailers.special_retailers"))

        if retailer_id:
            restore_inventory_allocations(db_session, "special", retailer_id)

        quote = get_fifo_quote(db_session, fruit_name, class_number, kilograms_per_unit, units_count)
        if not quote["success"]:
            db_session.rollback()
            flash(quote["message"], "error")
            return redirect(url_for("special_retailers.special_retailers"))

        if discount_mode == "commission" and discount_per_unit > settings.commission_per_unit:
            db_session.rollback()
            flash("الخصم للوحدة لا يمكن أن يكون أكبر من العمولة للوحدة لأنه يُخصم منها مباشرة.", "error")
            return redirect(url_for("special_retailers.special_retailers"))
        if discount_mode == "unit_price" and discount_per_unit > quote["average_price_per_unit"]:
            db_session.rollback()
            flash("الخصم للوحدة لا يمكن أن يكون أكبر من سعر الوحدة القادم من المخزون.", "error")
            return redirect(url_for("special_retailers.special_retailers"))

        original_price, price_per_unit, subtotal_price, final_total_price = calculate_sale_totals(
            units_count,
            quote["supplier_total_price"],
            discount_per_unit,
            settings.commission_per_unit,
            settings.admin_expense,
            discount_mode,
        )

        existing_paid = payment_total_for_retailer(db_session, retailer_id) if retailer_id else 0.0
        if final_total_price < existing_paid:
            db_session.rollback()
            flash("إجمالي الفاتورة الجديدة أقل من المدفوع فعلاً.", "error")
            return redirect(url_for("special_retailers.special_retailers"))

        retailer.date = parse_date(request.form.get("date"))
        retailer.retailer_name = retailer_name
        retailer.fruit_name = fruit_name
        retailer.units_count = units_count
        retailer.class_number = class_number
        retailer.kilograms_per_unit = kilograms_per_unit
        retailer.original_price_per_unit = original_price
        retailer.discount_per_unit = discount_per_unit
        retailer.discount_mode = discount_mode
        retailer.price_per_unit = price_per_unit
        retailer.commission_per_unit = settings.commission_per_unit
        retailer.admin_expense = settings.admin_expense
        retailer.total_price = final_total_price
        retailer.total_paid = existing_paid
        retailer.notes = request.form.get("notes", "").strip() or None
        update_special_retailer_status(retailer)

        db_session.add(retailer)
        db_session.flush()

        success, message = allocate_inventory_fifo(
            db_session,
            fruit_name,
            class_number,
            kilograms_per_unit,
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

    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()
    retailers_query = db_session.query(SpecialRetailer)
    retailers_query = apply_date_range(
        retailers_query,
        SpecialRetailer.date,
        date_from or None,
        date_to or None,
    )
    retailers = retailers_query.order_by(SpecialRetailer.date.desc(), SpecialRetailer.id.desc()).all()
    goods = available_goods(db_session)
    stock_options = [
        {
            "fruit_name": item.fruit_name,
            "class_number": item.class_number,
            "kilograms_per_unit": float(item.kilograms_per_unit or 0),
            "remaining_units": int(item.remaining_units or 0),
            "price_per_unit": float(item.price_per_unit or 0),
        }
        for item in goods
    ]
    context = {
        **build_base_context(db_session),
        "page_title": "تجار الآجل",
        "retailers": retailers,
        "edit_retailer": edit_retailer,
        "default_commission": settings.commission_per_unit,
        "default_admin_expense": settings.admin_expense,
        "stock_options": stock_options,
        "date_from": date_from,
        "date_to": date_to,
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
        "table_headers": ["الصنف", "الدرجة", "كجم/وحدة", "الوحدات", "سعر الوحدة", "القيمة"],
        "table_rows": [[
            retailer.fruit_name,
            retailer.class_number,
            f"{retailer.kilograms_per_unit:.2f}",
            retailer.units_count,
            f"{retailer.price_per_unit:.2f}",
            f"{retailer.total_price:.2f}",
        ]],
        "summary_lines": [
            ("نوع الخصم", "من العمولة" if retailer.discount_mode == "commission" else "من سعر الوحدة"),
            (
                "قيمة البضاعة" if retailer.discount_mode == "commission" else "قيمة البضاعة بعد الخصم",
                round(retailer.price_per_unit * retailer.units_count, 2)
                if retailer.discount_mode == "unit_price"
                else round(retailer.original_price_per_unit * retailer.units_count, 2),
            ),
            ("العمولة للوحدة", retailer.commission_per_unit),
            (
                "الخصم من العمولة للوحدة" if retailer.discount_mode == "commission" else "الخصم من سعر الوحدة",
                retailer.discount_per_unit,
            ),
            (
                "العمولة الصافية للوحدة" if retailer.discount_mode == "commission" else "العمولة للوحدة",
                effective_commission_per_unit(
                    retailer.commission_per_unit,
                    retailer.discount_per_unit,
                ) if retailer.discount_mode == "commission" else retailer.commission_per_unit,
            ),
            ("المصروف الإداري", retailer.admin_expense),
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
            f"{retailer.kilograms_per_unit:.2f}",
            str(retailer.units_count),
            f"{retailer.price_per_unit:.2f}",
            f"{retailer.total_price:.2f}",
        ],
        [
            "المدفوع",
            retailer.status,
            "-",
            "-",
            "-",
            f"{retailer.total_paid:.2f}",
        ],
        [
            "المتبقي",
            retailer.status,
            "-",
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
        ["البيان", "التفصيل", "كجم/وحدة", "الوحدات", "سعر الوحدة", "القيمة"],
        rows,
        paper="thermal",
    )
    return send_file(
        pdf,
        as_attachment=True,
        download_name=f"special-retailer-{retailer.id}.pdf",
        mimetype="application/pdf",
    )
