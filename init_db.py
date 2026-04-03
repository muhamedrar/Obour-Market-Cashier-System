from sqlalchemy import create_engine, text

from sql_server_config import DATABASE, build_database_uri, build_engine_options


def quoted_identifier(name: str) -> str:
    return f"[{name.replace(']', ']]')}]"


def ensure_database_exists() -> None:
    engine_options = dict(build_engine_options())
    engine_options["isolation_level"] = "AUTOCOMMIT"
    master_engine = create_engine(build_database_uri("master"), **engine_options)

    with master_engine.connect() as connection:
        database_exists = connection.scalar(
            text("SELECT 1 FROM sys.databases WHERE name = :database_name"),
            {"database_name": DATABASE},
        )
        if database_exists:
            print(f"Database '{DATABASE}' already exists.")
            return

        connection.execute(text(f"CREATE DATABASE {quoted_identifier(DATABASE)}"))
        print(f"Database '{DATABASE}' created successfully.")


def initialize_schema() -> None:
    from app import app
    from models import get_session
    from utils.helpers import get_or_create_settings

    with app.app_context():
        session = get_session()
        try:
            get_or_create_settings(session)
            print("Tables and default settings initialized successfully.")
        finally:
            session.close()


if __name__ == "__main__":
    ensure_database_exists()
    initialize_schema()
