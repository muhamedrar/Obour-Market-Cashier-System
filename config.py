from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATABASE_FILE = DATA_DIR / "cashier.db"


class Config:
    SECRET_KEY = "cashier-local-secret-key"
    DATA_DIR = str(DATA_DIR)
    DATABASE_URI = f"sqlite:///{DATABASE_FILE}"
    DEFAULT_COMPANY_NAME = "مؤسسة الكاشير"
    DEFAULT_PHONE_NUMBER = "01000000000"
    DEFAULT_COMMISSION = 0.0
    DEFAULT_ADMIN_EXPENSE = 0.0
    DEFAULT_SUPPLIER_PROFIT_PERCENTAGE = 0.0
    DEFAULT_ADMIN_PASSWORD = "admin123"
