from sqlalchemy import Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from models import Base


class Settings(Base):
    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_name: Mapped[str] = mapped_column(String(120), nullable=False)
    phone_number: Mapped[str] = mapped_column(String(50), nullable=False)
    commission_per_unit: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    admin_expense: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    admin_password: Mapped[str] = mapped_column(String(255), nullable=False)
