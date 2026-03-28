from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import DeclarativeBase, scoped_session, sessionmaker


class Base(DeclarativeBase):
    pass


SessionLocal = scoped_session(
    sessionmaker(autoflush=False, autocommit=False, expire_on_commit=False)
)
engine = None


def ensure_sqlite_columns():
    if engine is None or engine.dialect.name != "sqlite":
        return

    inspector = inspect(engine)
    statements = []

    if "special_retailers" in inspector.get_table_names():
        special_columns = {column["name"] for column in inspector.get_columns("special_retailers")}
        if "commission_per_unit" not in special_columns:
            statements.append(
                "ALTER TABLE special_retailers ADD COLUMN commission_per_unit FLOAT NOT NULL DEFAULT 0"
            )
        if "admin_expense" not in special_columns:
            statements.append(
                "ALTER TABLE special_retailers ADD COLUMN admin_expense FLOAT NOT NULL DEFAULT 0"
            )
        if "discount_mode" not in special_columns:
            statements.append(
                "ALTER TABLE special_retailers ADD COLUMN discount_mode VARCHAR(20) NOT NULL DEFAULT 'commission'"
            )

    if "retail_transactions" in inspector.get_table_names():
        retail_columns = {column["name"] for column in inspector.get_columns("retail_transactions")}
        if "discount_mode" not in retail_columns:
            statements.append(
                "ALTER TABLE retail_transactions ADD COLUMN discount_mode VARCHAR(20) NOT NULL DEFAULT 'commission'"
            )

    if "suppliers" in inspector.get_table_names():
        supplier_columns = {column["name"] for column in inspector.get_columns("suppliers")}
        if "kilograms_per_unit" not in supplier_columns:
            statements.append(
                "ALTER TABLE suppliers ADD COLUMN kilograms_per_unit FLOAT NOT NULL DEFAULT 0"
            )
        if "supplier_profit_percentage" not in supplier_columns:
            statements.append(
                "ALTER TABLE suppliers ADD COLUMN supplier_profit_percentage FLOAT NOT NULL DEFAULT 0"
            )

    if "settings" in inspector.get_table_names():
        settings_columns = {column["name"] for column in inspector.get_columns("settings")}
        if "supplier_profit_percentage" not in settings_columns:
            statements.append(
                "ALTER TABLE settings ADD COLUMN supplier_profit_percentage FLOAT NOT NULL DEFAULT 0"
            )
        if "shift_cutoff_time" not in settings_columns:
            statements.append(
                "ALTER TABLE settings ADD COLUMN shift_cutoff_time VARCHAR(5) NOT NULL DEFAULT '00:00'"
            )

    if "expenses" in inspector.get_table_names():
        expense_columns = {column["name"] for column in inspector.get_columns("expenses")}
        if "paid_amount" not in expense_columns:
            statements.append("ALTER TABLE expenses ADD COLUMN paid_amount FLOAT NOT NULL DEFAULT 0")
        if "is_paid" not in expense_columns:
            statements.append("ALTER TABLE expenses ADD COLUMN is_paid BOOLEAN NOT NULL DEFAULT 0")
        if "paid_at" not in expense_columns:
            statements.append("ALTER TABLE expenses ADD COLUMN paid_at DATETIME")
        statements.append(
            "UPDATE expenses SET paid_amount = amount WHERE is_paid = 1 AND COALESCE(paid_amount, 0) <= 0"
        )

    if not statements:
        return

    with engine.begin() as connection:
        for statement in statements:
            connection.exec_driver_sql(statement)


def init_app(app):
    global engine

    database_uri = app.config["DATABASE_URI"]
    connect_args = {"check_same_thread": False} if database_uri.startswith("sqlite") else {}
    engine = create_engine(database_uri, future=True, connect_args=connect_args)
    SessionLocal.configure(bind=engine)

    from models.expense import Expense
    from models.inventory_allocation import InventoryAllocation
    from models.payment import Payment
    from models.retail_transaction import RetailTransaction
    from models.settings import Settings
    from models.special_retailer import SpecialRetailer
    from models.supplier import Supplier

    Base.metadata.create_all(bind=engine)
    ensure_sqlite_columns()

    @app.teardown_appcontext
    def shutdown_session(exception=None):
        SessionLocal.remove()


def get_session():
    return SessionLocal()
