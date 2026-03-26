from flask import Blueprint, flash, redirect, render_template, request, send_file, session, url_for

from models import get_session
from models.retail_transaction import RetailTransaction
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
    restore_inventory_allocations,
    split_phone_numbers,
)
from utils.report_generator import build_pdf


retail_bp = Blueprint("retail", __name__, url_prefix="/retail")


@retail_bp.route("/", methods=["GET", "POST"])
def retail():
    db_session = get_session()
    settings = get_or_create_settings(db_session)
    is_admin_user = bool(session.get("admin_logged_in"))

    if request.method == "POST":
        transaction_id = parse_int(request.form.get("transaction_id"))
        if transaction_id and not is_admin_user:
            flash("تعديل الحركات يحتاج صلاحية المسؤول.", "error")
            return redirect(url_for("admin.login", next=url_for("retail.retail")))

        transaction = (
            db_session.get(RetailTransaction, transaction_id) if transaction_id else RetailTransaction()
        )
        if transaction_id and not transaction:
            flash("حركة البيع غير موجودة.", "error")
            return redirect(url_for("retail.retail"))

        discount_per_unit = parse_float(request.form.get("discount_per_unit"))
        commission_per_unit = (
            parse_float(request.form.get("commission_per_unit"), settings.commission_per_unit)
            if is_admin_user
            else settings.commission_per_unit
        )
        admin_expense = (
            parse_float(request.form.get("admin_expense"), settings.admin_expense)
            if is_admin_user
            else settings.admin_expense
        )
        discount_mode = (
            normalize_discount_mode(request.form.get("discount_mode"))
            if is_admin_user
            else "commission"
        )
        units_count = parse_int(request.form.get("units_count"))
        fruit_name = request.form.get("fruit_name", "").strip()
        class_number = request.form.get("class_number", "").strip()

        if not fruit_name or not class_number or units_count <= 0:
            flash("يرجى إدخال الصنف والدرجة وعدد الوحدات بشكل صحيح.", "error")
            return redirect(url_for("retail.retail"))

        if transaction_id:
            restore_inventory_allocations(db_session, "retail", transaction_id)

        quote = get_fifo_quote(db_session, fruit_name, class_number, units_count)
        if not quote["success"]:
            db_session.rollback()
            flash(quote["message"], "error")
            return redirect(url_for("retail.retail"))

        if discount_mode == "commission" and discount_per_unit > commission_per_unit:
            db_session.rollback()
            flash("الخصم للوحدة لا يمكن أن يكون أكبر من العمولة للوحدة لأنه يُخصم منها مباشرة.", "error")
            return redirect(url_for("retail.retail"))
        if discount_mode == "unit_price" and discount_per_unit > quote["average_price_per_unit"]:
            db_session.rollback()
            flash("الخصم للوحدة لا يمكن أن يكون أكبر من سعر الوحدة القادم من المخزون.", "error")
            return redirect(url_for("retail.retail"))

        original_price, price_per_unit, total_price, final_price = calculate_sale_totals(
            units_count,
            quote["supplier_total_price"],
            discount_per_unit,
            commission_per_unit,
            admin_expense,
            discount_mode,
        )

        transaction.date = parse_date(request.form.get("date"))
        transaction.fruit_name = fruit_name
        transaction.units_count = units_count
        transaction.class_number = class_number
        transaction.original_price_per_unit = original_price
        transaction.discount_per_unit = discount_per_unit
        transaction.discount_mode = discount_mode
        transaction.price_per_unit = price_per_unit
        transaction.commission_per_unit = commission_per_unit
        transaction.admin_expense = admin_expense
        transaction.total_price = total_price
        transaction.final_price = final_price
        transaction.notes = request.form.get("notes", "").strip() or None

        db_session.add(transaction)
        db_session.flush()

        success, message = allocate_inventory_fifo(
            db_session,
            fruit_name,
            class_number,
            units_count,
            "retail",
            transaction.id,
        )
        if not success:
            db_session.rollback()
            flash(message, "error")
            return redirect(url_for("retail.retail"))

        db_session.commit()
        flash("تم حفظ حركة البيع النقدي.", "success")
        return redirect(url_for("retail.retail"))

    edit_transaction = None
    edit_id = parse_int(request.args.get("edit"))
    if edit_id:
        edit_transaction = db_session.get(RetailTransaction, edit_id)

    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()
    transactions_query = db_session.query(RetailTransaction)
    transactions_query = apply_date_range(
        transactions_query,
        RetailTransaction.date,
        date_from or None,
        date_to or None,
    )
    transactions = transactions_query.order_by(
        RetailTransaction.date.desc(), RetailTransaction.id.desc()
    ).all()
    goods = available_goods(db_session)
    stock_options = [
        {
            "fruit_name": item.fruit_name,
            "class_number": item.class_number,
            "remaining_units": int(item.remaining_units or 0),
            "price_per_unit": float(item.price_per_unit or 0),
        }
        for item in goods
    ]
    context = {
        **build_base_context(db_session),
        "page_title": "البيع النقدي",
        "transactions": transactions,
        "edit_transaction": edit_transaction,
        "default_commission": settings.commission_per_unit,
        "default_admin_expense": settings.admin_expense,
        "available_goods": goods,
        "stock_options": stock_options,
        "date_from": date_from,
        "date_to": date_to,
    }
    return render_template("retail.html", **context)


@retail_bp.route("/<int:transaction_id>/delete", methods=["POST"])
@admin_required
def delete_retail(transaction_id: int):
    db_session = get_session()
    transaction = db_session.get(RetailTransaction, transaction_id)
    if not transaction:
        flash("الحركة غير موجودة.", "error")
        return redirect(url_for("retail.retail"))

    restore_inventory_allocations(db_session, "retail", transaction.id)
    db_session.delete(transaction)
    db_session.commit()
    flash("تم حذف حركة البيع وإرجاع المخزون.", "success")
    return redirect(url_for("retail.retail"))


@retail_bp.route("/<int:transaction_id>/receipt")
def retail_receipt(transaction_id: int):
    db_session = get_session()
    settings = get_or_create_settings(db_session)
    transaction = db_session.get(RetailTransaction, transaction_id)
    if not transaction:
        flash("الحركة غير موجودة.", "error")
        return redirect(url_for("retail.retail"))

    context = {
        **build_base_context(db_session),
        "page_title": "معاينة فاتورة النقدي",
        "report_title": "فاتورة بيع نقدي",
        "report_subtitle": "مناسبة للطباعة الحرارية والمعاينة قبل التنزيل.",
        "meta_lines": [
            f"الشركة: {settings.company_name}",
            *[f"الهاتف: {phone}" for phone in split_phone_numbers(settings.phone_number)],
            f"التاريخ: {transaction.date.strftime('%Y-%m-%d %H:%M')}",
        ],
        "table_headers": ["الصنف", "الدرجة", "الوحدات", "سعر الوحدة", "الإجمالي النهائي"],
        "table_rows": [
            [
                transaction.fruit_name,
                transaction.class_number,
                transaction.units_count,
                f"{transaction.price_per_unit:.2f}",
                f"{transaction.final_price:.2f}",
            ]
        ],
        "summary_lines": [
            ("نوع الخصم", "من العمولة" if transaction.discount_mode == "commission" else "من سعر الوحدة"),
            ("متوسط سعر المورد", transaction.original_price_per_unit),
            (
                "قيمة البضاعة" if transaction.discount_mode == "commission" else "قيمة البضاعة بعد الخصم",
                transaction.total_price,
            ),
            (
                "الخصم من العمولة للوحدة" if transaction.discount_mode == "commission" else "الخصم من سعر الوحدة",
                transaction.discount_per_unit,
            ),
            (
                "العمولة الصافية للوحدة" if transaction.discount_mode == "commission" else "العمولة للوحدة",
                effective_commission_per_unit(
                    transaction.commission_per_unit,
                    transaction.discount_per_unit,
                ) if transaction.discount_mode == "commission" else transaction.commission_per_unit,
            ),
            ("المصروف الإداري", transaction.admin_expense),
            ("الإجمالي النهائي", transaction.final_price),
        ],
        "download_url": url_for("retail.retail_receipt_pdf", transaction_id=transaction.id),
        "print_mode": "thermal",
    }
    return render_template("print_preview.html", **context)


@retail_bp.route("/<int:transaction_id>/receipt/pdf")
def retail_receipt_pdf(transaction_id: int):
    db_session = get_session()
    settings = get_or_create_settings(db_session)
    transaction = db_session.get(RetailTransaction, transaction_id)
    if not transaction:
        flash("الحركة غير موجودة.", "error")
        return redirect(url_for("retail.retail"))

    pdf = build_pdf(
        "فاتورة بيع نقدي",
        [
            f"الشركة: {settings.company_name}",
            *[f"الهاتف: {phone}" for phone in split_phone_numbers(settings.phone_number)],
            f"التاريخ: {transaction.date.strftime('%Y-%m-%d %H:%M')}",
        ],
        ["الصنف", "الدرجة", "الوحدات", "سعر الوحدة", "الإجمالي"],
        [[
            transaction.fruit_name,
            transaction.class_number,
            str(transaction.units_count),
            f"{transaction.price_per_unit:.2f}",
            f"{transaction.final_price:.2f}",
        ]],
        paper="thermal",
    )
    return send_file(
        pdf,
        as_attachment=True,
        download_name=f"retail-receipt-{transaction.id}.pdf",
        mimetype="application/pdf",
    )
