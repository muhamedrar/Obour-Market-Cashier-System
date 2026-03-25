from flask import Blueprint, flash, redirect, render_template, request, url_for
from sqlalchemy import or_

from models import get_session
from models.supplier import Supplier
from utils.helpers import (
    admin_required,
    build_base_context,
    parse_date,
    parse_float,
    parse_int,
    supplier_units_sold,
    update_supplier_totals,
)


supplier_bp = Blueprint("suppliers", __name__, url_prefix="/suppliers")


@supplier_bp.route("/", methods=["GET", "POST"])
def suppliers():
    db_session = get_session()

    if request.method == "POST":
        supplier_id = parse_int(request.form.get("supplier_id"))
        supplier = db_session.get(Supplier, supplier_id) if supplier_id else Supplier()

        supplier.date = parse_date(request.form.get("date"))
        supplier.supplier_name = request.form.get("supplier_name", "").strip()
        supplier.fruit_name = request.form.get("fruit_name", "").strip()
        supplier.class_number = request.form.get("class_number", "").strip()
        supplier.units_count = parse_int(request.form.get("units_count"))
        supplier.price_per_unit = parse_float(request.form.get("price_per_unit"))
        supplier.notes = request.form.get("notes", "").strip() or None

        if not supplier.supplier_name or not supplier.fruit_name or not supplier.class_number:
            flash("يرجى إدخال اسم المورد والصنف والدرجة.", "error")
            return redirect(url_for("suppliers.suppliers"))

        if supplier.units_count <= 0 or supplier.price_per_unit < 0:
            flash("عدد الوحدات والسعر يجب أن يكونا صالحين.", "error")
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

    suppliers_list = suppliers_query.order_by(Supplier.date.desc(), Supplier.id.desc()).all()
    context = {
        **build_base_context(db_session),
        "page_title": "الموردون",
        "suppliers_list": suppliers_list,
        "edit_supplier": edit_supplier,
        "search_query": search_query,
    }
    return render_template("suppliers.html", **context)


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
