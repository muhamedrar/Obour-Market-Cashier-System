from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from models import Base


class Expense(Base):
    __tablename__ = "expenses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)
    expense_name: Mapped[str] = mapped_column(String(120), nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    paid_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    is_paid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    @property
    def normalized_paid_amount(self) -> float:
        return round(min(max(float(self.paid_amount or 0), 0.0), float(self.amount or 0)), 2)

    @property
    def remaining_amount(self) -> float:
        return round(max(float(self.amount or 0) - self.normalized_paid_amount, 0.0), 2)

    @property
    def payment_status(self) -> str:
        if self.amount > 0 and self.remaining_amount <= 0:
            return "paid"
        if self.normalized_paid_amount > 0:
            return "partial"
        return "unpaid"
