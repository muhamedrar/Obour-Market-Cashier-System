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
    total_price: Mapped[float] = mapped_column(Float, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_cleared: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    allocations = relationship(
        "InventoryAllocation", back_populates="supplier", cascade="all, delete-orphan"
    )
