from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, UnicodeText
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models import Base


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    retailer_id: Mapped[int] = mapped_column(ForeignKey("special_retailers.id"), nullable=False)
    payment_date: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)
    amount_paid: Mapped[float] = mapped_column(Float, nullable=False)
    notes: Mapped[str | None] = mapped_column(UnicodeText, nullable=True)

    retailer = relationship("SpecialRetailer", back_populates="payments")
