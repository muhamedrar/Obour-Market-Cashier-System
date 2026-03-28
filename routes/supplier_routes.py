from flask import Blueprint, flash, redirect, render_template, request, send_file, url_for
from sqlalchemy import or_

from models import get_session
from models.supplier import Supplier
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
        supplier = db_session.get(Supplier, supplier_id) if supplier_id else Supplier()

        supplier.date = parse_date(request.form.get("date"))
        supplier.supplier_name = request.form.get("supplier_name", "").strip()
        supplier.fruit_name = request.form.get("fruit_name", "").strip()
        supplier.class_number = request.form.get("class_number", "").strip()
        supplier.units_count = parse_int(request.form.get("units_count"))
        supplier.price_per_unit = parse_float(request.form.get("price_per_unit"))
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

        if supplier.units_count <= 0 or supplier.price_per_unit < 0:
            flash("عدد الوحدات والسعر يجب أن يكونا صالحين.", "error")
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
        db_session.add(supplier)
        db_session.commit()

        flash("تم حفظ المورد بنجاح.", "success")
        return redirect(url_for("suppliers.suppliers"))

    edit_supplier = None
    edit_id = parse_int(request.args.get("edit"))
    if edit_id:
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


@supplier_bp.route("/<int:supplier_id>/receipt")
def supplier_receipt(supplier_id: int):
    db_session = get_session()
    settings = get_or_create_settings(db_session)
    supplier = db_session.get(Supplier, supplier_id)
    if not supplier:
        flash("المورد غير موجود.", "error")
        return redirect(url_for("suppliers.suppliers"))

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
        "table_headers": ["الصنف", "الدرجة", "الوحدات", "سعر الوحدة", "الإجمالي الخام"],
        "table_rows": [[
            supplier.fruit_name,
            supplier.class_number,
            str(supplier.units_count),
            f"{supplier.price_per_unit:.2f}",
            f"{supplier.total_price:.2f}",
        ]],
        "summary_lines": [
            ("نسبة ربح المحل", f"{supplier.supplier_profit_percentage:.2f}%"),
            ("ربح المحل من المورد", supplier.company_profit_total),
            ("مستحق المورد", supplier.supplier_payout_total),
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

    pdf = build_pdf(
        "إيصال مورد",
        [
            f"الشركة: {settings.company_name}",
            *[f"الهاتف: {phone}" for phone in split_phone_numbers(settings.phone_number)],
            f"المورد: {supplier.supplier_name}",
            f"التاريخ: {supplier.date.strftime('%Y-%m-%d %H:%M')}",
            f"نسبة ربح المحل: {supplier.supplier_profit_percentage:.2f}%",
            f"ربح المحل: {supplier.company_profit_total:.2f}",
            f"مستحق المورد: {supplier.supplier_payout_total:.2f}",
        ],
        ["الصنف", "الدرجة", "الوحدات", "سعر الوحدة", "الإجمالي"],
        [[
            supplier.fruit_name,
            supplier.class_number,
            str(supplier.units_count),
            f"{supplier.price_per_unit:.2f}",
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

    if supplier_units_sold(db_session, supplier) > 0:
        flash("لا يمكن حذف مورد مرتبط بحركات بيع. عدّل السجل بدلاً من ذلك.", "error")
        return redirect(url_for("suppliers.suppliers"))

    db_session.delete(supplier)
    db_session.commit()
    flash("تم حذف المورد.", "success")
    return redirect(url_for("suppliers.suppliers"))
