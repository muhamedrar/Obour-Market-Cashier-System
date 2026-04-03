from __future__ import annotations

from dataclasses import dataclass

from flask import request, url_for


@dataclass(frozen=True)
class NavigationEntry:
    label: str
    endpoint: str
    active_endpoints: tuple[str, ...] = ()
    badge_key: str | None = None
    guest_endpoint: str | None = None

    def resolved_endpoint(self, is_admin: bool) -> str:
        if not is_admin and self.guest_endpoint:
            return self.guest_endpoint
        return self.endpoint

    def matches(self, current_endpoint: str | None) -> bool:
        if not current_endpoint:
            return False
        allowed_endpoints = self.active_endpoints or (self.endpoint,)
        return current_endpoint in allowed_endpoints


NAVIGATION_ENTRIES = (
    NavigationEntry("لوحة التحكم", "admin.dashboard"),
    NavigationEntry(
        "الموردون",
        "suppliers.suppliers",
        active_endpoints=(
            "suppliers.suppliers",
            "suppliers.pay_supplier",
            "suppliers.confirm_supplier_payment",
            "suppliers.supplier_receipt",
            "suppliers.supplier_receipt_pdf",
            "suppliers.delete_supplier",
        ),
        badge_key="open_suppliers",
    ),
    NavigationEntry(
        "البيع النقدي",
        "retail.retail",
        active_endpoints=(
            "retail.retail",
            "retail.delete_retail",
            "retail.retail_receipt",
            "retail.retail_receipt_pdf",
        ),
    ),
    NavigationEntry(
        "تجار الآجل",
        "special_retailers.special_retailers",
        active_endpoints=(
            "special_retailers.special_retailers",
            "special_retailers.delete_special_retailer",
            "special_retailers.special_retailer_receipt",
            "special_retailers.special_retailer_receipt_pdf",
        ),
        badge_key="unpaid_retailers",
    ),
    NavigationEntry(
        "الدفعات",
        "payments.payments",
        active_endpoints=("payments.payments", "payments.delete_payment"),
    ),
    NavigationEntry(
        "المصروفات",
        "expenses.expenses",
        active_endpoints=(
            "expenses.expenses",
            "expenses.confirm_expense_payment",
            "expenses.pay_expense",
            "expenses.delete_expense",
        ),
    ),
    NavigationEntry(
        "التقارير",
        "admin.reports",
        active_endpoints=(
            "admin.reports",
            "admin.report_pdf",
            "admin.inventory_thermal_preview",
            "admin.inventory_thermal_pdf",
        ),
    ),
    NavigationEntry(
        "المسؤول",
        "admin.admin_panel",
        active_endpoints=("admin.admin_panel", "admin.login"),
        guest_endpoint="admin.login",
    ),
)


def build_navigation_items(nav_badges: dict[str, int], is_admin: bool) -> list[dict[str, object]]:
    current_endpoint = request.endpoint
    items: list[dict[str, object]] = []

    for entry in NAVIGATION_ENTRIES:
        endpoint = entry.resolved_endpoint(is_admin)
        items.append(
            {
                "label": entry.label,
                "href": url_for(endpoint),
                "active": entry.matches(current_endpoint),
                "badge": nav_badges.get(entry.badge_key) if entry.badge_key else None,
            }
        )

    return items
