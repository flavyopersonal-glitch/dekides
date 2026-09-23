import os
from contextlib import contextmanager
from threading import Lock

from dotenv import load_dotenv
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

load_dotenv(os.getenv("DEKIDS_ENV_FILE", ".env"))
_pool = None
_lock = Lock()


def pool():
    global _pool
    with _lock:
        if _pool is None:
            url = os.getenv("DATABASE_URL")
            if not url:
                raise RuntimeError("Configure DATABASE_URL para o Neon.")
            _pool = ConnectionPool(url, min_size=0, max_size=5, timeout=15,
                                   max_idle=60, kwargs={"row_factory": dict_row,
                                   "connect_timeout": 10, "application_name": "dekids"})
        return _pool


@contextmanager
def connection():
    with pool().connection() as conn:
        with conn.transaction():
            conn.execute("SET LOCAL search_path = dekids, public")
            conn.execute("SET LOCAL statement_timeout = '15s'")
            yield conn


def close_pool():
    global _pool
    with _lock:
        if _pool:
            _pool.close()
            _pool = None
