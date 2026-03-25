from datetime import datetime

from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from sqlalchemy import func, select

from models import get_session
from models.expense import Expense
from models.retail_transaction import RetailTransaction
from models.settings import Settings
from models.special_retailer import SpecialRetailer
from models.supplier import Supplier
from utils.helpers import (
    admin_required,
    build_base_context,
    dashboard_metrics,
    get_or_create_settings,
    hash_password,
    inventory_summary,
    is_admin_logged_in,
    parse_float,
    revenue_breakdown,
    sold_units_summary,
    verify_password,
)
from utils.report_generator import build_pdf


admin_bp = Blueprint("admin", __name__)


@admin_bp.route("/dashboard")
def dashboard():
    db_session = get_session()
    selected_fruit = request.args.get("fruit", "").strip() or None
    fruits = db_session.scalars(
        select(Supplier.fruit_name).distinct().order_by(Supplier.fruit_name.asc())
    ).all()

    recent_retail = (
        db_session.query(RetailTransaction)
        .order_by(RetailTransaction.date.desc(), RetailTransaction.id.desc())
        .limit(5)
        .all()
    )
    recent_debt = (
        db_session.query(SpecialRetailer)
        .order_by(SpecialRetailer.date.desc(), SpecialRetailer.id.desc())
        .limit(5)
        .all()
    )

    context = {
        **build_base_context(db_session),
        "page_title": "لوحة التحكم",
        "metrics": dashboard_metrics(db_session),
        "inventory_rows": inventory_summary(db_session, selected_fruit),
        "fruit_options": fruits,
        "selected_fruit": selected_fruit or "",
        "recent_retail": recent_retail,
        "recent_debt": recent_debt,
    }
    return render_template("dashboard.html", **context)


@admin_bp.route("/reports")
def reports():
    db_session = get_session()
    inventory_rows = inventory_summary(db_session)
    sold_rows = sold_units_summary(db_session)
    breakdown = revenue_breakdown(db_session)
    context = {
        **build_base_context(db_session),
        "page_title": "التقارير",
        "inventory_rows": inventory_rows,
        "sold_rows": sold_rows,
        "breakdown": breakdown,
    }
    return render_template("reports.html", **context)


@admin_bp.route("/reports/pdf")
def report_pdf():
    db_session = get_session()
    settings = get_or_create_settings(db_session)
    inventory_rows = inventory_summary(db_session)
    sold_rows = sold_units_summary(db_session)
    breakdown = revenue_breakdown(db_session)

    rows = []
    for row in inventory_rows:
        rows.append(
            [
                f"مخزون - {row.fruit_name}",
                str(row.class_number),
                str(int(row.remaining_units or 0)),
                f"{float(row.avg_price or 0):.2f}",
                f"{float(row.total_value or 0):.2f}",
            ]
        )
    for row in sold_rows:
        rows.append(
            [
                f"مباع - {row['fruit_name']}",
                str(row["class_number"]),
                str(int(row["units_count"])),
                "-",
                f"{float(row['revenue']):.2f}",
            ]
        )

    rows.extend(
        [
            ["إجمالي العمولات", "-", "-", "-", f"{breakdown['commission_total']:.2f}"],
            ["إجمالي المصروف الإداري", "-", "-", "-", f"{breakdown['admin_fees_total']:.2f}"],
            ["إجمالي تكلفة البضاعة", "-", "-", "-", f"{breakdown['supplier_cost_total']:.2f}"],
            ["إجمالي المصروفات الأخرى", "-", "-", "-", f"{breakdown['other_expenses_total']:.2f}"],
            ["إجمالي الديون المسجلة", "-", "-", "-", f"{breakdown['debt_total']:.2f}"],
            ["إجمالي الإيراد", "-", "-", "-", f"{breakdown['total_revenue']:.2f}"],
            ["صافي الإيراد", "-", "-", "-", f"{breakdown['net_revenue']:.2f}"],
            ["الإيراد الحالي", "-", "-", "-", f"{breakdown['current_revenue']:.2f}"],
        ]
    )

    pdf = build_pdf(
        "تقرير النظام",
        [
            f"الشركة: {settings.company_name}",
            f"الهاتف: {settings.phone_number}",
            f"تاريخ التقرير: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        ],
        ["البيان", "الدرجة", "الوحدات", "السعر", "الإجمالي"],
        rows,
    )
    return send_file(
        pdf,
        as_attachment=True,
        download_name="cashier-report.pdf",
        mimetype="application/pdf",
    )


@admin_bp.route("/admin/login", methods=["GET", "POST"])
def login():
    db_session = get_session()
    settings = get_or_create_settings(db_session)
    if request.method == "POST":
        password = request.form.get("password", "")
        if verify_password(settings.admin_password, password):
            session["admin_logged_in"] = True
            flash("تم تسجيل الدخول بنجاح.", "success")
            return redirect(request.args.get("next") or url_for("admin.admin_panel"))
        flash("كلمة المرور غير صحيحة.", "error")

    return render_template(
        "admin_login.html",
        **build_base_context(db_session),
        page_title="دخول المسؤول",
    )


@admin_bp.route("/admin/logout", methods=["POST"])
def logout():
    session.pop("admin_logged_in", None)
    flash("تم تسجيل الخروج من لوحة المسؤول.", "success")
    return redirect(url_for("admin.dashboard"))


@admin_bp.route("/admin", methods=["GET", "POST"])
@admin_required
def admin_panel():
    db_session = get_session()
    settings = get_or_create_settings(db_session)

    if request.method == "POST":
        settings.company_name = request.form.get("company_name", "").strip() or settings.company_name
        settings.phone_number = request.form.get("phone_number", "").strip() or settings.phone_number
        settings.commission_per_unit = parse_float(
            request.form.get("commission_per_unit"), settings.commission_per_unit
        )
        settings.admin_expense = parse_float(
            request.form.get("admin_expense"), settings.admin_expense
        )

        new_password = request.form.get("new_password", "").strip()
        if new_password:
            settings.admin_password = hash_password(new_password)

        db_session.commit()
        flash("تم تحديث إعدادات النظام.", "success")
        return redirect(url_for("admin.admin_panel"))

    recent_suppliers = (
        db_session.query(Supplier).order_by(Supplier.date.desc(), Supplier.id.desc()).limit(10).all()
    )
    recent_expenses = (
        db_session.query(Expense).order_by(Expense.date.desc(), Expense.id.desc()).limit(10).all()
    )
    context = {
        **build_base_context(db_session),
        "page_title": "لوحة المسؤول",
        "recent_suppliers": recent_suppliers,
        "recent_expenses": recent_expenses,
        "is_admin": is_admin_logged_in(),
    }
    return render_template("admin.html", **context)
