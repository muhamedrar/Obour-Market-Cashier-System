from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, UnicodeText
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models import Base


class SupplierPayment(Base):
    __tablename__ = "supplier_payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"), nullable=False)
    payment_date: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)
    amount_paid: Mapped[float] = mapped_column(Float, nullable=False)
    notes: Mapped[str | None] = mapped_column(UnicodeText, nullable=True)

    supplier = relationship("Supplier", back_populates="payments")
