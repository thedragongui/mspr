import os
import psycopg2

def _get_env(name, default=None, required=False):
    value = os.getenv(name, default)
    if required and not value:
        raise RuntimeError(f"Missing env var: {name}")
    return value

def get_conn():
    return psycopg2.connect(
        host=_get_env("DB_HOST", "localhost"),
        port=_get_env("DB_PORT", "5432"),
        dbname=_get_env("DB_NAME", "mspr_electio"),
        user=_get_env("DB_USER", "mspr"),
        password=_get_env("DB_PASSWORD", required=True),
    )
