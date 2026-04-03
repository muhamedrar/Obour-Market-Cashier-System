from flask import Flask

from routes.admin_routes import admin_bp
from routes.expense_routes import expense_bp
from routes.payment_routes import payment_bp
from routes.retail_routes import retail_bp
from routes.special_retailer_routes import special_retailer_bp
from routes.supplier_routes import supplier_bp


REGISTERED_BLUEPRINTS = (
    admin_bp,
    supplier_bp,
    retail_bp,
    special_retailer_bp,
    payment_bp,
    expense_bp,
)


def register_blueprints(app: Flask) -> None:
    for blueprint in REGISTERED_BLUEPRINTS:
        app.register_blueprint(blueprint)
