from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, scoped_session, sessionmaker


class Base(DeclarativeBase):
    pass


SessionLocal = scoped_session(
    sessionmaker(autoflush=False, autocommit=False, expire_on_commit=False)
)
engine = None


def import_model_modules():
    from models.expense import Expense
    from models.inventory_allocation import InventoryAllocation
    from models.payment import Payment
    from models.retail_transaction import RetailTransaction
    from models.settings import Settings
    from models.special_retailer import SpecialRetailer
    from models.supplier import Supplier
    from models.supplier_payment import SupplierPayment

    return (
        Expense,
        InventoryAllocation,
        Payment,
        RetailTransaction,
        Settings,
        SpecialRetailer,
        Supplier,
        SupplierPayment,
    )


def init_app(app):
    global engine

    database_uri = app.config["DATABASE_URI"]
    engine_options = dict(app.config.get("DATABASE_ENGINE_OPTIONS", {}))
    engine = create_engine(database_uri, **engine_options)
    SessionLocal.configure(bind=engine)

    import_model_modules()
    Base.metadata.create_all(bind=engine)

    @app.teardown_appcontext
    def shutdown_session(exception=None):
        SessionLocal.remove()


def get_session():
    return SessionLocal()
