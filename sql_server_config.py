import os
from urllib.parse import quote_plus, urlencode


# Edit these values directly for your SQL Server setup.
SERVER = os.getenv("MSSQL_HOST", "127.0.0.1")
PORT = os.getenv("MSSQL_PORT", "1433")
DATABASE = os.getenv("MSSQL_DATABASE", "cashier")
USERNAME = os.getenv("MSSQL_USERNAME", "sa")
PASSWORD = os.getenv("MSSQL_PASSWORD", "123@123qwe")
DRIVER = os.getenv("MSSQL_DRIVER", "FreeTDS")
TDS_VERSION = os.getenv("MSSQL_TDS_VERSION", "").strip()
CHARSET = os.getenv("MSSQL_CHARSET", "UTF-8").strip()
TRUST_SERVER_CERTIFICATE = os.getenv("MSSQL_TRUST_SERVER_CERTIFICATE", "yes").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
ENCRYPT = os.getenv("MSSQL_ENCRYPT", "").strip()


def build_database_uri(database: str | None = None) -> str:
    target_database = database or DATABASE

    if DRIVER.strip().lower() == "freetds":
        connection_parts = [
            f"DRIVER={{{DRIVER}}}",
            f"SERVER={SERVER}",
            f"PORT={PORT}",
            f"DATABASE={target_database}",
            f"UID={USERNAME}",
            f"PWD={PASSWORD}",
        ]
        if TDS_VERSION:
            connection_parts.append(f"TDS_Version={TDS_VERSION}")
        if CHARSET:
            connection_parts.append(f"ClientCharset={CHARSET}")
        if ENCRYPT:
            connection_parts.append(f"Encrypt={ENCRYPT}")

        odbc_connect = quote_plus(";".join(connection_parts))
        return f"mssql+pyodbc:///?odbc_connect={odbc_connect}"

    query_params = {
        "driver": DRIVER,
    }
    if TDS_VERSION:
        query_params["TDS_Version"] = TDS_VERSION
    if CHARSET:
        query_params["charset"] = CHARSET
    query_params["TrustServerCertificate"] = "yes" if TRUST_SERVER_CERTIFICATE else "no"
    if ENCRYPT:
        query_params["Encrypt"] = ENCRYPT

    credentials = f"{quote_plus(USERNAME)}:{quote_plus(PASSWORD)}@"
    query_string = urlencode(query_params)
    return f"mssql+pyodbc://{credentials}{SERVER}:{PORT}/{quote_plus(target_database)}?{query_string}"


def build_engine_options() -> dict:
    return {
        "future": True,
        "pool_pre_ping": True,
    }
