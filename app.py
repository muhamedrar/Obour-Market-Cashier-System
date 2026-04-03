from flask import Flask, redirect, url_for

from config import Config
from models import init_app as init_db
from routes import register_blueprints
from utils.helpers import currency_filter, date_filter, datetime_input_filter


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)

    init_db(app)

    register_blueprints(app)

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
