from pathlib import Path

from flask import Flask, redirect, url_for

from config import Config
from models import init_app as init_db
from routes.admin_routes import admin_bp
from routes.expense_routes import expense_bp
from routes.payment_routes import payment_bp
from routes.retail_routes import retail_bp
from routes.special_retailer_routes import special_retailer_bp
from routes.supplier_routes import supplier_bp
from utils.helpers import currency_filter, date_filter, datetime_input_filter


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)

    Path(app.config["DATA_DIR"]).mkdir(parents=True, exist_ok=True)

    init_db(app)

    app.register_blueprint(admin_bp)
    app.register_blueprint(supplier_bp)
    app.register_blueprint(retail_bp)
    app.register_blueprint(special_retailer_bp)
    app.register_blueprint(payment_bp)
    app.register_blueprint(expense_bp)

    app.jinja_env.filters["currency"] = currency_filter
    app.jinja_env.filters["date_ar"] = date_filter
    app.jinja_env.filters["datetime_input"] = datetime_input_filter

    @app.route("/")
    def index():
        return redirect(url_for("admin.dashboard"))

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
