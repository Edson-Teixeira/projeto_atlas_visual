import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
from app.config import Config

_db_pool = None

def get_pool():
    global _db_pool
    if _db_pool is None:
        _db_pool = pool.SimpleConnectionPool(
            minconn=1,
            maxconn=10,
            host=Config.DB_HOST,
            port=Config.DB_PORT,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            dbname=Config.DB_NAME,
            connect_timeout=Config.DB_CONNECT_TIMEOUT
        )
    return _db_pool

@contextmanager
def get_db():
    """Context manager para conexões seguras com retorno automático ao pool."""
    p = get_pool()
    conn = p.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        p.putconn(conn)

@contextmanager
def get_cursor(dict_cursor=True):
    """Context manager que retorna um cursor (por padrão RealDictCursor para dicionários)."""
    with get_db() as conn:
        cursor_factory = RealDictCursor if dict_cursor else None
        cur = conn.cursor(cursor_factory=cursor_factory)
        try:
            yield cur
        finally:
            cur.close()

def query_one(sql, params=None):
    with get_cursor() as cur:
        cur.execute(sql, params or ())
        return cur.fetchone()

def query_all(sql, params=None):
    with get_cursor() as cur:
        cur.execute(sql, params or ())
        return cur.fetchall()

def execute(sql, params=None):
    with get_cursor(dict_cursor=False) as cur:
        cur.execute(sql, params or ())
        return cur.rowcount
