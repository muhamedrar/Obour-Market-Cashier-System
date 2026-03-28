from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models import Base


class Supplier(Base):
    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)
    supplier_name: Mapped[str] = mapped_column(String(120), nullable=False)
    fruit_name: Mapped[str] = mapped_column(String(120), nullable=False)
    units_count: Mapped[int] = mapped_column(Integer, nullable=False)
    remaining_units: Mapped[int] = mapped_column(Integer, nullable=False)
    class_number: Mapped[str] = mapped_column(String(50), nullable=False)
    price_per_unit: Mapped[float] = mapped_column(Float, nullable=False)
    kilograms_per_unit: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    supplier_profit_percentage: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_price: Mapped[float] = mapped_column(Float, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_cleared: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    allocations = relationship(
        "InventoryAllocation", back_populates="supplier", cascade="all, delete-orphan"
    )
    payments = relationship(
        "SupplierPayment",
        back_populates="supplier",
        cascade="all, delete-orphan",
        order_by="SupplierPayment.payment_date.desc()",
    )

    @property
    def company_profit_total(self) -> float:
        return round(self.total_price * (self.supplier_profit_percentage / 100), 2)

    @property
    def supplier_payout_total(self) -> float:
        return round(self.total_price - self.company_profit_total, 2)

    @property
    def supplier_payout_per_unit(self) -> float:
        return round(self.price_per_unit * (1 - (self.supplier_profit_percentage / 100)), 2)

    @property
    def total_kilograms(self) -> float:
        return round(self.units_count * self.kilograms_per_unit, 2)

    @property
    def remaining_kilograms(self) -> float:
        return round(self.remaining_units * self.kilograms_per_unit, 2)
