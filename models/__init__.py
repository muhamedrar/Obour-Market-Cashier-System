from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, scoped_session, sessionmaker


class Base(DeclarativeBase):
    pass


SessionLocal = scoped_session(
    sessionmaker(autoflush=False, autocommit=False, expire_on_commit=False)
)
engine = None


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

    @app.teardown_appcontext
    def shutdown_session(exception=None):
        SessionLocal.remove()


def get_session():
    return SessionLocal()
