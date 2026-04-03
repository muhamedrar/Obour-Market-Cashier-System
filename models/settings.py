from sqlalchemy import Float, Integer, String, Unicode
from sqlalchemy.orm import Mapped, mapped_column

from models import Base


class Settings(Base):
    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_name: Mapped[str] = mapped_column(Unicode(120), nullable=False)
    phone_number: Mapped[str] = mapped_column(String(255), nullable=False)
    commission_per_unit: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    admin_expense: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    supplier_profit_percentage: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    shift_cutoff_time: Mapped[str] = mapped_column(String(5), nullable=False, default="00:00")
    admin_password: Mapped[str] = mapped_column(String(255), nullable=False)
