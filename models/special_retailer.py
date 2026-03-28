from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models import Base


class SpecialRetailer(Base):
    __tablename__ = "special_retailers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)
    retailer_name: Mapped[str] = mapped_column(String(120), nullable=False)
    fruit_name: Mapped[str] = mapped_column(String(120), nullable=False)
    units_count: Mapped[int] = mapped_column(Integer, nullable=False)
    class_number: Mapped[str] = mapped_column(String(50), nullable=False)
    kilograms_per_unit: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    original_price_per_unit: Mapped[float] = mapped_column(Float, nullable=False)
    discount_per_unit: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    discount_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="commission")
    price_per_unit: Mapped[float] = mapped_column(Float, nullable=False)
    commission_per_unit: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    admin_expense: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_price: Mapped[float] = mapped_column(Float, nullable=False)
    total_paid: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    remaining_balance: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="unpaid")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    payments = relationship(
        "Payment", back_populates="retailer", cascade="all, delete-orphan", order_by="Payment.payment_date.desc()"
    )
