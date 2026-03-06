from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import NullPool
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

Base = declarative_base()

_engine = None
_SessionLocal = None


def _normalize_postgres_url(db_uri: str) -> str:
    if not db_uri.startswith("postgresql"):
        return db_uri
    parsed = urlparse(db_uri)
    params = dict(parse_qsl(parsed.query, keep_blank_values=True))
    params.setdefault("sslmode", "require")
    new_query = urlencode(params)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))


def init_engine(db_uri: str):
    global _engine, _SessionLocal

    if not db_uri:
        raise RuntimeError("DATABASE_URL is required")

    create_kwargs = {"future": True, "pool_pre_ping": True}
    if db_uri.startswith("postgresql"):
        db_uri = _normalize_postgres_url(db_uri)
        create_kwargs["poolclass"] = NullPool
        create_kwargs["connect_args"] = {
            "connect_timeout": 10,
            "options": "-c statement_timeout=30000",
        }

    _engine = create_engine(db_uri, **create_kwargs)
    _SessionLocal = sessionmaker(
        bind=_engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
        future=True,
    )
    return _engine


def get_session():
    if _SessionLocal is None:
        raise RuntimeError("Database not initialized")
    return _SessionLocal()


def init_db():
    if _engine is None:
        raise RuntimeError("Engine not initialized")
    try:
        Base.metadata.create_all(_engine)
    except OperationalError as exc:
        msg = str(exc).lower()
        if "could not translate host name" in msg:
            raise RuntimeError(
                "Could not resolve DATABASE_URL host. If using Supabase direct host "
                "(db.<project-ref>.supabase.co), switch to the Supabase pooler host "
                "(aws-*.pooler.supabase.com) or ensure IPv6 DNS/network is available."
            ) from exc
        raise


def upsert_reel_fts(*_args, **_kwargs):
    """No-op in PostgreSQL mode; search_vector is generated in-model."""
    return None
