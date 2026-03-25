from __future__ import annotations

from datetime import date, datetime, time
from functools import wraps

from flask import flash, redirect, request, session, url_for
from sqlalchemy import func, select
from werkzeug.security import check_password_hash, generate_password_hash

from config import Config
from models.expense import Expense
from models.inventory_allocation import InventoryAllocation
from models.payment import Payment
from models.retail_transaction import RetailTransaction
from models.settings import Settings
from models.special_retailer import SpecialRetailer
from models.supplier import Supplier


def parse_date(value: str | None) -> datetime:
    if value:
        normalized = value.replace("T", " ")
        for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                parsed = datetime.strptime(normalized, fmt)
                if fmt == "%Y-%m-%d":
                    return parsed.replace(hour=datetime.now().hour, minute=datetime.now().minute)
                return parsed
            except ValueError:
                continue
    return datetime.now()


def parse_int(value: str | None, default: int = 0) -> int:
    try:
        return int(value or default)
    except (TypeError, ValueError):
        return default


def parse_float(value: str | None, default: float = 0.0) -> float:
    try:
        return round(float(value or default), 2)
    except (TypeError, ValueError):
        return default


def currency_filter(value) -> str:
    return f"{float(value or 0):,.2f} ج.م"


def date_filter(value) -> str:
    if not value:
        return "-"
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M")
    return value.strftime("%Y-%m-%d")


def datetime_input_filter(value) -> str:
    if not value:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%dT%H:%M")
    return datetime.combine(value, datetime.now().time()).strftime("%Y-%m-%dT%H:%M")


def sync_supplier_status(supplier: Supplier) -> None:
    supplier.is_cleared = supplier.remaining_units <= 0
    if supplier.remaining_units < 0:
        supplier.remaining_units = 0


def update_supplier_totals(supplier: Supplier) -> None:
    supplier.total_price = round(supplier.units_count * supplier.price_per_unit, 2)
    sync_supplier_status(supplier)


def calculate_sale_values(
    units_count: int,
    original_price_per_unit: float,
    discount_per_unit: float,
    commission_per_unit: float = 0.0,
    admin_expense: float = 0.0,
):
    discounted_price = max(round(original_price_per_unit - discount_per_unit, 2), 0.0)
    total_price = round(discounted_price * units_count, 2)
    final_price = round(
        total_price + (commission_per_unit * units_count) + admin_expense,
        2,
    )
    return discounted_price, total_price, final_price


def calculate_sale_totals(
    units_count: int,
    supplier_total_price: float,
    discount_per_unit: float,
    commission_per_unit: float = 0.0,
    admin_expense: float = 0.0,
):
    original_price_per_unit = round(supplier_total_price / units_count, 2) if units_count else 0.0
    discounted_total = max(round(supplier_total_price - (discount_per_unit * units_count), 2), 0.0)
    discounted_price_per_unit = round(discounted_total / units_count, 2) if units_count else 0.0
    final_price = round(
        discounted_total + (commission_per_unit * units_count) + admin_expense,
        2,
    )
    return original_price_per_unit, discounted_price_per_unit, discounted_total, final_price


def update_special_retailer_status(retailer: SpecialRetailer) -> None:
    retailer.remaining_balance = round(retailer.total_price - retailer.total_paid, 2)
    if retailer.remaining_balance <= 0:
        retailer.remaining_balance = 0.0
        retailer.status = "paid"
    elif retailer.total_paid > 0:
        retailer.status = "partial"
    else:
        retailer.status = "unpaid"


def get_or_create_settings(db_session) -> Settings:
    settings = db_session.get(Settings, 1)
    if settings:
        return settings

    settings = Settings(
        id=1,
        company_name=Config.DEFAULT_COMPANY_NAME,
        phone_number=Config.DEFAULT_PHONE_NUMBER,
        commission_per_unit=Config.DEFAULT_COMMISSION,
        admin_expense=Config.DEFAULT_ADMIN_EXPENSE,
        admin_password=generate_password_hash(Config.DEFAULT_ADMIN_PASSWORD),
    )
    db_session.add(settings)
    db_session.commit()
    return settings


def hash_password(password: str) -> str:
    return generate_password_hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    return check_password_hash(password_hash, password)


def is_admin_logged_in() -> bool:
    return bool(session.get("admin_logged_in"))


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not is_admin_logged_in():
            flash("يجب تسجيل الدخول كمسؤول أولاً.", "error")
            return redirect(url_for("admin.login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


def restore_inventory_allocations(db_session, transaction_type: str, transaction_id: int) -> None:
    allocations = (
        db_session.query(InventoryAllocation)
        .filter(
            InventoryAllocation.transaction_type == transaction_type,
            InventoryAllocation.transaction_id == transaction_id,
        )
        .all()
    )
    for allocation in allocations:
        allocation.supplier.remaining_units += allocation.units_count
        sync_supplier_status(allocation.supplier)
        db_session.delete(allocation)


def allocate_inventory_fifo(
    db_session,
    fruit_name: str,
    class_number: str,
    units_needed: int,
    transaction_type: str,
    transaction_id: int,
) -> tuple[bool, str]:
    suppliers = (
        db_session.query(Supplier)
        .filter(
            Supplier.fruit_name == fruit_name,
            Supplier.class_number == class_number,
            Supplier.remaining_units > 0,
        )
        .order_by(Supplier.date.asc(), Supplier.id.asc())
        .all()
    )

    available_units = sum(supplier.remaining_units for supplier in suppliers)
    if available_units < units_needed:
        return (
            False,
            f"المخزون غير كافٍ. المتاح حالياً {available_units} وحدة فقط لهذا الصنف.",
        )

    remaining = units_needed
    for supplier in suppliers:
        if remaining <= 0:
            break
        consumed = min(supplier.remaining_units, remaining)
        supplier.remaining_units -= consumed
        sync_supplier_status(supplier)
        db_session.add(
            InventoryAllocation(
                supplier_id=supplier.id,
                transaction_type=transaction_type,
                transaction_id=transaction_id,
                units_count=consumed,
            )
        )
        remaining -= consumed

    return True, ""


def supplier_units_sold(db_session, supplier: Supplier) -> int:
    sold_units = db_session.scalar(
        select(func.coalesce(func.sum(InventoryAllocation.units_count), 0)).where(
            InventoryAllocation.supplier_id == supplier.id
        )
    )
    return int(sold_units or 0)


def today_metrics(db_session):
    return dashboard_metrics(db_session)


def inventory_summary(db_session, fruit_name: str | None = None):
    query = (
        db_session.query(
            Supplier.fruit_name,
            Supplier.class_number,
            func.sum(Supplier.remaining_units).label("remaining_units"),
            func.avg(Supplier.price_per_unit).label("avg_price"),
            func.sum(Supplier.remaining_units * Supplier.price_per_unit).label("total_value"),
        )
        .filter(Supplier.remaining_units > 0)
        .group_by(Supplier.fruit_name, Supplier.class_number)
        .order_by(Supplier.fruit_name.asc(), Supplier.class_number.asc())
    )
    if fruit_name:
        query = query.filter(Supplier.fruit_name == fruit_name)
    return query.all()


def sold_units_summary(db_session):
    retail_rows = (
        db_session.query(
            RetailTransaction.fruit_name.label("fruit_name"),
            RetailTransaction.class_number.label("class_number"),
            func.sum(RetailTransaction.units_count).label("units_count"),
            func.sum(RetailTransaction.final_price).label("revenue"),
        )
        .group_by(RetailTransaction.fruit_name, RetailTransaction.class_number)
        .all()
    )
    debt_rows = (
        db_session.query(
            SpecialRetailer.fruit_name.label("fruit_name"),
            SpecialRetailer.class_number.label("class_number"),
            func.sum(SpecialRetailer.units_count).label("units_count"),
            func.sum(SpecialRetailer.total_price).label("revenue"),
        )
        .group_by(SpecialRetailer.fruit_name, SpecialRetailer.class_number)
        .all()
    )

    merged = {}
    for row in [*retail_rows, *debt_rows]:
        key = (row.fruit_name, row.class_number)
        if key not in merged:
            merged[key] = {
                "fruit_name": row.fruit_name,
                "class_number": row.class_number,
                "units_count": 0,
                "revenue": 0.0,
            }
        merged[key]["units_count"] += int(row.units_count or 0)
        merged[key]["revenue"] += float(row.revenue or 0)
    return list(merged.values())


def total_net_revenue(db_session) -> float:
    return revenue_breakdown(db_session)["net_revenue"]


def payment_total_for_retailer(db_session, retailer_id: int) -> float:
    total = db_session.scalar(
        select(func.coalesce(func.sum(Payment.amount_paid), 0)).where(
            Payment.retailer_id == retailer_id
        )
    )
    return round(total or 0, 2)


def received_payments_total(db_session) -> float:
    total = db_session.scalar(select(func.coalesce(func.sum(Payment.amount_paid), 0)))
    return round(float(total or 0), 2)


def supplier_cost_total(db_session) -> float:
    total = db_session.scalar(
        select(func.coalesce(func.sum(InventoryAllocation.units_count * Supplier.price_per_unit), 0))
        .select_from(InventoryAllocation)
        .join(Supplier, Supplier.id == InventoryAllocation.supplier_id)
    )
    return round(float(total or 0), 2)


def revenue_breakdown(db_session):
    retail_commission_total = db_session.scalar(
        select(
            func.coalesce(
                func.sum(RetailTransaction.commission_per_unit * RetailTransaction.units_count),
                0,
            )
        )
    ) or 0
    debt_commission_total = db_session.scalar(
        select(
            func.coalesce(
                func.sum(SpecialRetailer.commission_per_unit * SpecialRetailer.units_count),
                0,
            )
        )
    ) or 0
    commission_total = float(retail_commission_total) + float(debt_commission_total)

    retail_admin_total = db_session.scalar(
        select(func.coalesce(func.sum(RetailTransaction.admin_expense), 0))
    ) or 0
    debt_admin_total = db_session.scalar(
        select(func.coalesce(func.sum(SpecialRetailer.admin_expense), 0))
    ) or 0
    admin_fees_total = float(retail_admin_total) + float(debt_admin_total)
    other_expenses_total = db_session.scalar(
        select(func.coalesce(func.sum(Expense.amount), 0))
    ) or 0
    debt_total = db_session.scalar(
        select(func.coalesce(func.sum(SpecialRetailer.total_price), 0))
    ) or 0
    supplier_costs = supplier_cost_total(db_session)
    debt_paid_total = received_payments_total(db_session)
    sales_count = (
        db_session.scalar(select(func.count(RetailTransaction.id))) or 0
    ) + (
        db_session.scalar(select(func.count(SpecialRetailer.id))) or 0
    )

    total_revenue = round(
        float(commission_total) + float(admin_fees_total) + supplier_costs + float(debt_total),
        2,
    )
    net_revenue = round(
        float(commission_total) + float(admin_fees_total) - float(other_expenses_total),
        2,
    )
    current_revenue = round(net_revenue + supplier_costs + debt_paid_total, 2)

    return {
        "commission_total": round(float(commission_total), 2),
        "admin_fees_total": round(float(admin_fees_total), 2),
        "supplier_cost_total": supplier_costs,
        "other_expenses_total": round(float(other_expenses_total), 2),
        "debt_total": round(float(debt_total), 2),
        "debt_paid_total": debt_paid_total,
        "sales_count": int(sales_count),
        "net_revenue": net_revenue,
        "current_revenue": current_revenue,
        "total_revenue": total_revenue,
    }


def dashboard_metrics(db_session):
    breakdown = revenue_breakdown(db_session)
    outstanding = db_session.scalar(
        select(func.coalesce(func.sum(SpecialRetailer.remaining_balance), 0)).where(
            SpecialRetailer.remaining_balance > 0
        )
    ) or 0
    active_suppliers = db_session.scalar(
        select(func.count(Supplier.id)).where(Supplier.remaining_units > 0)
    ) or 0

    return {
        **breakdown,
        "outstanding_debt": round(float(outstanding), 2),
        "active_suppliers": active_suppliers,
    }


def navigation_badges(db_session):
    return {
        "unpaid_retailers": db_session.scalar(
            select(func.count(SpecialRetailer.id)).where(SpecialRetailer.remaining_balance > 0)
        )
        or 0,
        "open_suppliers": db_session.scalar(
            select(func.count(Supplier.id)).where(Supplier.remaining_units > 0)
        )
        or 0,
    }


def build_base_context(db_session):
    settings = get_or_create_settings(db_session)
    return {
        "settings": settings,
        "phone_numbers": split_phone_numbers(settings.phone_number),
        "nav_badges": navigation_badges(db_session),
        "is_admin": is_admin_logged_in(),
        "now_string": datetime.now().strftime("%Y-%m-%dT%H:%M"),
    }


def get_fifo_quote(db_session, fruit_name: str, class_number: str, units_needed: int):
    suppliers = (
        db_session.query(Supplier)
        .filter(
            Supplier.fruit_name == fruit_name,
            Supplier.class_number == class_number,
            Supplier.remaining_units > 0,
        )
        .order_by(Supplier.date.asc(), Supplier.id.asc())
        .all()
    )

    available_units = sum(supplier.remaining_units for supplier in suppliers)
    if not suppliers:
        return {
            "success": False,
            "message": "لا يوجد مخزون متاح لهذا الصنف حالياً.",
            "available_units": 0,
            "starting_price": 0.0,
            "average_price_per_unit": 0.0,
            "supplier_total_price": 0.0,
        }

    starting_price = round(float(suppliers[0].price_per_unit), 2)
    if units_needed <= 0:
        return {
            "success": True,
            "message": "",
            "available_units": available_units,
            "starting_price": starting_price,
            "average_price_per_unit": starting_price,
            "supplier_total_price": 0.0,
        }

    if available_units < units_needed:
        return {
            "success": False,
            "message": f"المخزون غير كافٍ. المتاح {available_units} وحدة فقط.",
            "available_units": available_units,
            "starting_price": starting_price,
            "average_price_per_unit": starting_price,
            "supplier_total_price": 0.0,
        }

    remaining = units_needed
    supplier_total_price = 0.0
    for supplier in suppliers:
        if remaining <= 0:
            break
        consumed = min(supplier.remaining_units, remaining)
        supplier_total_price += consumed * supplier.price_per_unit
        remaining -= consumed

    average_price = round(supplier_total_price / units_needed, 2) if units_needed else starting_price
    return {
        "success": True,
        "message": "",
        "available_units": available_units,
        "starting_price": starting_price,
        "average_price_per_unit": average_price,
        "supplier_total_price": round(supplier_total_price, 2),
    }


def available_goods(db_session):
    return (
        db_session.query(Supplier)
        .filter(Supplier.remaining_units > 0)
        .order_by(Supplier.date.asc(), Supplier.id.asc())
        .all()
    )


def split_phone_numbers(value: str | None) -> list[str]:
    if not value:
        return []
    numbers = []
    for line in value.replace(",", "\n").splitlines():
        cleaned = line.strip()
        if cleaned:
            numbers.append(cleaned)
    return numbers


def apply_date_range(query, column, date_from: str | None, date_to: str | None):
    if date_from:
        query = query.filter(column >= datetime.combine(datetime.strptime(date_from, "%Y-%m-%d").date(), time.min))
    if date_to:
        query = query.filter(column <= datetime.combine(datetime.strptime(date_to, "%Y-%m-%d").date(), time.max))
    return query
