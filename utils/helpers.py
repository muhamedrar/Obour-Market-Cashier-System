from __future__ import annotations

from datetime import date, datetime, time, timedelta
from functools import wraps

from flask import flash, redirect, request, session, url_for
from sqlalchemy import and_, case, func, select
from werkzeug.security import check_password_hash, generate_password_hash

from config import Config
from models.expense import Expense
from models.inventory_allocation import InventoryAllocation
from models.payment import Payment
from models.retail_transaction import RetailTransaction
from models.settings import Settings
from models.special_retailer import SpecialRetailer
from models.supplier import Supplier


def parse_filter_datetime(value: str | None, end_of_day: bool = False) -> datetime | None:
    if not value:
        return None

    normalized = value.strip().replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            parsed = datetime.strptime(normalized, fmt)
            if fmt == "%Y-%m-%d":
                return datetime.combine(parsed.date(), time.max if end_of_day else time.min)
            return parsed
        except ValueError:
            continue
    return None


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


def supplier_company_profit(total_price: float, supplier_profit_percentage: float) -> float:
    percentage = min(max(float(supplier_profit_percentage or 0), 0.0), 100.0)
    return round(float(total_price or 0) * (percentage / 100), 2)


def supplier_payout_total(total_price: float, supplier_profit_percentage: float) -> float:
    return round(float(total_price or 0) - supplier_company_profit(total_price, supplier_profit_percentage), 2)


def supplier_payout_unit_price(price_per_unit: float, supplier_profit_percentage: float) -> float:
    percentage = min(max(float(supplier_profit_percentage or 0), 0.0), 100.0)
    return round(float(price_per_unit or 0) * (1 - (percentage / 100)), 2)


def normalize_shift_cutoff_time(value: str | None, default: str = "00:00") -> str:
    normalized = (value or "").strip()
    try:
        parsed = datetime.strptime(normalized, "%H:%M")
        return parsed.strftime("%H:%M")
    except ValueError:
        return default


def current_shift_cutoff_range(cutoff_time: str | None, reference: datetime | None = None) -> dict[str, str]:
    now = reference or datetime.now()
    normalized_cutoff = normalize_shift_cutoff_time(cutoff_time)
    cutoff_clock = datetime.strptime(normalized_cutoff, "%H:%M").time()
    today_cutoff = datetime.combine(now.date(), cutoff_clock)

    if now >= today_cutoff:
        start = today_cutoff
        end = today_cutoff + timedelta(days=1) - timedelta(minutes=1)
    else:
        start = today_cutoff - timedelta(days=1)
        end = today_cutoff - timedelta(minutes=1)

    return {
        "cutoff": normalized_cutoff,
        "start": start.strftime("%Y-%m-%dT%H:%M"),
        "end": end.strftime("%Y-%m-%dT%H:%M"),
    }


def effective_commission_per_unit(commission_per_unit: float, discount_per_unit: float) -> float:
    return max(round(commission_per_unit - discount_per_unit, 2), 0.0)


def normalize_discount_mode(discount_mode: str | None) -> str:
    return "unit_price" if discount_mode == "unit_price" else "commission"


def calculate_sale_values(
    units_count: int,
    original_price_per_unit: float,
    discount_per_unit: float,
    commission_per_unit: float = 0.0,
    admin_expense: float = 0.0,
    discount_mode: str = "commission",
):
    discount_mode = normalize_discount_mode(discount_mode)
    if discount_mode == "unit_price":
        price_per_unit = max(round(original_price_per_unit - discount_per_unit, 2), 0.0)
        total_price = round(price_per_unit * units_count, 2)
        net_commission = round(commission_per_unit, 2)
    else:
        price_per_unit = round(original_price_per_unit, 2)
        total_price = round(price_per_unit * units_count, 2)
        net_commission = effective_commission_per_unit(commission_per_unit, discount_per_unit)
    final_price = round(
        total_price + (net_commission * units_count) + admin_expense,
        2,
    )
    return price_per_unit, total_price, final_price


def calculate_sale_totals(
    units_count: int,
    supplier_total_price: float,
    discount_per_unit: float,
    commission_per_unit: float = 0.0,
    admin_expense: float = 0.0,
    discount_mode: str = "commission",
):
    discount_mode = normalize_discount_mode(discount_mode)
    original_price_per_unit = round(supplier_total_price / units_count, 2) if units_count else 0.0
    if discount_mode == "unit_price":
        price_per_unit = max(round(original_price_per_unit - discount_per_unit, 2), 0.0)
        total_price = round(price_per_unit * units_count, 2)
        net_commission = round(commission_per_unit, 2)
    else:
        price_per_unit = original_price_per_unit
        total_price = round(supplier_total_price, 2)
        net_commission = effective_commission_per_unit(commission_per_unit, discount_per_unit)
    final_price = round(
        total_price + (net_commission * units_count) + admin_expense,
        2,
    )
    return original_price_per_unit, price_per_unit, total_price, final_price


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
        supplier_profit_percentage=Config.DEFAULT_SUPPLIER_PROFIT_PERCENTAGE,
        shift_cutoff_time=Config.DEFAULT_SHIFT_CUTOFF_TIME,
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


def inventory_summary(
    db_session,
    fruit_name: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
):
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
    query = apply_date_range(query, Supplier.date, date_from, date_to)
    return query.all()


def sold_units_summary(db_session, date_from: str | None = None, date_to: str | None = None):
    retail_rows = (
        db_session.query(
            RetailTransaction.fruit_name.label("fruit_name"),
            RetailTransaction.class_number.label("class_number"),
            func.sum(RetailTransaction.units_count).label("units_count"),
            func.sum(RetailTransaction.final_price).label("revenue"),
        )
    )
    retail_rows = apply_date_range(retail_rows, RetailTransaction.date, date_from, date_to)
    retail_rows = retail_rows.group_by(RetailTransaction.fruit_name, RetailTransaction.class_number).all()
    debt_rows = (
        db_session.query(
            SpecialRetailer.fruit_name.label("fruit_name"),
            SpecialRetailer.class_number.label("class_number"),
            func.sum(SpecialRetailer.units_count).label("units_count"),
            func.sum(SpecialRetailer.total_price).label("revenue"),
        )
    )
    debt_rows = apply_date_range(debt_rows, SpecialRetailer.date, date_from, date_to)
    debt_rows = debt_rows.group_by(SpecialRetailer.fruit_name, SpecialRetailer.class_number).all()

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


def received_payments_total(
    db_session,
    date_from: str | None = None,
    date_to: str | None = None,
) -> float:
    query = select(func.coalesce(func.sum(Payment.amount_paid), 0))
    query = apply_date_range(query, Payment.payment_date, date_from, date_to)
    total = db_session.scalar(query)
    return round(float(total or 0), 2)


def supplier_cost_total(
    db_session,
    date_from: str | None = None,
    date_to: str | None = None,
) -> float:
    payout_expression = (
        InventoryAllocation.units_count
        * Supplier.price_per_unit
        * (1 - (Supplier.supplier_profit_percentage / 100))
    )
    retail_query = (
        db_session.query(func.coalesce(func.sum(payout_expression), 0))
        .select_from(InventoryAllocation)
        .join(Supplier, InventoryAllocation.supplier_id == Supplier.id)
        .join(
            RetailTransaction,
            and_(
                InventoryAllocation.transaction_type == "retail",
                InventoryAllocation.transaction_id == RetailTransaction.id,
            ),
        )
    )
    retail_query = apply_date_range(retail_query, RetailTransaction.date, date_from, date_to)
    debt_query = (
        db_session.query(func.coalesce(func.sum(payout_expression), 0))
        .select_from(InventoryAllocation)
        .join(Supplier, InventoryAllocation.supplier_id == Supplier.id)
        .join(
            SpecialRetailer,
            and_(
                InventoryAllocation.transaction_type == "special",
                InventoryAllocation.transaction_id == SpecialRetailer.id,
            ),
        )
    )
    debt_query = apply_date_range(debt_query, SpecialRetailer.date, date_from, date_to)
    total = float(retail_query.scalar() or 0) + float(debt_query.scalar() or 0)
    return round(total, 2)


def revenue_breakdown(db_session, date_from: str | None = None, date_to: str | None = None):
    retail_effective_commission = case(
        (
            RetailTransaction.discount_mode == "commission",
            case(
                (
                    RetailTransaction.commission_per_unit > RetailTransaction.discount_per_unit,
                    (RetailTransaction.commission_per_unit - RetailTransaction.discount_per_unit)
                    * RetailTransaction.units_count,
                ),
                else_=0,
            ),
        ),
        else_=RetailTransaction.commission_per_unit * RetailTransaction.units_count,
    )
    retail_commission_query = select(
        func.coalesce(
            func.sum(retail_effective_commission),
            0,
        )
    )
    retail_commission_query = apply_date_range(
        retail_commission_query,
        RetailTransaction.date,
        date_from,
        date_to,
    )
    retail_commission_total = db_session.scalar(retail_commission_query) or 0
    debt_effective_commission = case(
        (
            SpecialRetailer.discount_mode == "commission",
            case(
                (
                    SpecialRetailer.commission_per_unit > SpecialRetailer.discount_per_unit,
                    (SpecialRetailer.commission_per_unit - SpecialRetailer.discount_per_unit)
                    * SpecialRetailer.units_count,
                ),
                else_=0,
            ),
        ),
        else_=SpecialRetailer.commission_per_unit * SpecialRetailer.units_count,
    )
    debt_commission_query = select(
        func.coalesce(
            func.sum(debt_effective_commission),
            0,
        )
    )
    debt_commission_query = apply_date_range(
        debt_commission_query,
        SpecialRetailer.date,
        date_from,
        date_to,
    )
    debt_commission_total = db_session.scalar(debt_commission_query) or 0
    commission_total = float(retail_commission_total) + float(debt_commission_total)

    retail_admin_query = select(func.coalesce(func.sum(RetailTransaction.admin_expense), 0))
    retail_admin_query = apply_date_range(retail_admin_query, RetailTransaction.date, date_from, date_to)
    retail_admin_total = db_session.scalar(retail_admin_query) or 0
    debt_admin_query = select(func.coalesce(func.sum(SpecialRetailer.admin_expense), 0))
    debt_admin_query = apply_date_range(debt_admin_query, SpecialRetailer.date, date_from, date_to)
    debt_admin_total = db_session.scalar(debt_admin_query) or 0
    admin_fees_total = float(retail_admin_total) + float(debt_admin_total)

    retail_total_query = select(func.coalesce(func.sum(RetailTransaction.final_price), 0))
    retail_total_query = apply_date_range(retail_total_query, RetailTransaction.date, date_from, date_to)
    retail_total = float(db_session.scalar(retail_total_query) or 0)

    expenses_query = select(func.coalesce(func.sum(Expense.amount), 0))
    expenses_query = apply_date_range(expenses_query, Expense.date, date_from, date_to)
    other_expenses_total = float(db_session.scalar(expenses_query) or 0)
    debt_total_query = select(func.coalesce(func.sum(SpecialRetailer.total_price), 0))
    debt_total_query = apply_date_range(debt_total_query, SpecialRetailer.date, date_from, date_to)
    debt_total = float(db_session.scalar(debt_total_query) or 0)
    supplier_costs = supplier_cost_total(db_session, date_from, date_to)
    debt_paid_total = received_payments_total(db_session, date_from, date_to)
    retail_count_query = select(func.count(RetailTransaction.id))
    retail_count_query = apply_date_range(retail_count_query, RetailTransaction.date, date_from, date_to)
    debt_count_query = select(func.count(SpecialRetailer.id))
    debt_count_query = apply_date_range(debt_count_query, SpecialRetailer.date, date_from, date_to)
    sales_count = (db_session.scalar(retail_count_query) or 0) + (db_session.scalar(debt_count_query) or 0)

    total_revenue = round(retail_total + debt_total, 2)
    net_revenue = round(total_revenue - supplier_costs - other_expenses_total, 2)
    current_revenue = round(retail_total + debt_paid_total - other_expenses_total, 2)

    return {
        "commission_total": round(float(commission_total), 2),
        "admin_fees_total": round(float(admin_fees_total), 2),
        "supplier_cost_total": supplier_costs,
        "other_expenses_total": round(other_expenses_total, 2),
        "debt_total": round(debt_total, 2),
        "debt_paid_total": debt_paid_total,
        "sales_count": int(sales_count),
        "net_revenue": net_revenue,
        "current_revenue": current_revenue,
        "total_revenue": total_revenue,
    }


def dashboard_metrics(db_session, date_from: str | None = None, date_to: str | None = None):
    breakdown = revenue_breakdown(db_session, date_from, date_to)
    outstanding_query = select(func.coalesce(func.sum(SpecialRetailer.remaining_balance), 0)).where(
        SpecialRetailer.remaining_balance > 0
    )
    outstanding_query = apply_date_range(outstanding_query, SpecialRetailer.date, date_from, date_to)
    outstanding = db_session.scalar(outstanding_query) or 0
    active_suppliers_query = select(func.count(Supplier.id)).where(Supplier.remaining_units > 0)
    active_suppliers_query = apply_date_range(active_suppliers_query, Supplier.date, date_from, date_to)
    active_suppliers = db_session.scalar(active_suppliers_query) or 0

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
    shift_cutoff_range = current_shift_cutoff_range(settings.shift_cutoff_time)
    return {
        "settings": settings,
        "phone_numbers": split_phone_numbers(settings.phone_number),
        "nav_badges": navigation_badges(db_session),
        "is_admin": is_admin_logged_in(),
        "now_string": datetime.now().strftime("%Y-%m-%dT%H:%M"),
        "shift_cutoff_range": shift_cutoff_range,
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
    start = parse_filter_datetime(date_from, end_of_day=False)
    end = parse_filter_datetime(date_to, end_of_day=True)
    if start:
        criterion = column >= start
        query = query.filter(criterion) if hasattr(query, "filter") else query.where(criterion)
    if end:
        criterion = column <= end
        query = query.filter(criterion) if hasattr(query, "filter") else query.where(criterion)
    return query


def filtered_period_label(date_from: str | None, date_to: str | None) -> str:
    start = parse_filter_datetime(date_from, end_of_day=False)
    end = parse_filter_datetime(date_to, end_of_day=True)
    if start and end:
        return f"الفترة: {start.strftime('%Y-%m-%d %H:%M')} إلى {end.strftime('%Y-%m-%d %H:%M')}"
    if start:
        return f"الفترة من: {start.strftime('%Y-%m-%d %H:%M')}"
    if end:
        return f"الفترة حتى: {end.strftime('%Y-%m-%d %H:%M')}"
    return "الفترة: كل البيانات"
