from sql_server_config import build_database_uri, build_engine_options


class Config:
    SECRET_KEY = "cashier-local-secret-key"
    DATABASE_URI = build_database_uri()
    DATABASE_ENGINE_OPTIONS = build_engine_options()
    DEFAULT_COMPANY_NAME = "مؤسسة الكاشير"
    DEFAULT_PHONE_NUMBER = "01000000000"
    DEFAULT_COMMISSION = 0.0
    DEFAULT_ADMIN_EXPENSE = 0.0
    DEFAULT_SUPPLIER_PROFIT_PERCENTAGE = 0.0
    DEFAULT_SHIFT_CUTOFF_TIME = "00:00"
    DEFAULT_ADMIN_PASSWORD = "admin123"
