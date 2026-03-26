from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from models import Base


class RetailTransaction(Base):
    __tablename__ = "retail_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)
    fruit_name: Mapped[str] = mapped_column(String(120), nullable=False)
    units_count: Mapped[int] = mapped_column(Integer, nullable=False)
    class_number: Mapped[str] = mapped_column(String(50), nullable=False)
    original_price_per_unit: Mapped[float] = mapped_column(Float, nullable=False)
    discount_per_unit: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    discount_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="commission")
    price_per_unit: Mapped[float] = mapped_column(Float, nullable=False)
    commission_per_unit: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    admin_expense: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_price: Mapped[float] = mapped_column(Float, nullable=False)
    final_price: Mapped[float] = mapped_column(Float, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
