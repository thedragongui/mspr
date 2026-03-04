import os
from pathlib import Path

import psycopg2

# Charger .env depuis la racine du projet quand on lance en local (hors Docker)
try:
    from dotenv import load_dotenv
    _root = Path(__file__).resolve().parents[2]
    load_dotenv(_root / ".env")
except ImportError:
    pass

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
