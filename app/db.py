from __future__ import annotations

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, declarative_base

Base = declarative_base()

_engine = None
_SessionLocal = None


def init_engine(db_uri: str):
    global _engine, _SessionLocal
    create_kwargs = {"future": True, "pool_pre_ping": True}
    if db_uri.startswith("sqlite"):
        create_kwargs["connect_args"] = {"check_same_thread": False, "timeout": 30}
    _engine = create_engine(db_uri, **create_kwargs)
    if db_uri.startswith("sqlite"):
        _configure_sqlite_engine(_engine)
    _SessionLocal = sessionmaker(
        bind=_engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
        future=True,
    )
    return _engine


def _configure_sqlite_engine(engine):
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA busy_timeout=30000")
        finally:
            cursor.close()


def get_session():
    if _SessionLocal is None:
        raise RuntimeError("Database not initialized")
    return _SessionLocal()


def init_db():
    if _engine is None:
        raise RuntimeError("Engine not initialized")
    Base.metadata.create_all(_engine)
    # FTS5 table for search
    with _engine.begin() as conn:
        conn.execute(
            text(
                "CREATE VIRTUAL TABLE IF NOT EXISTS reel_fts USING fts5("
                "reel_id UNINDEXED, ai_title, ai_summary, summary_detail, transcript)"
            )
        )
        _ensure_profiles_columns(conn)
        _ensure_jobs_columns(conn)
        _ensure_reels_columns(conn)
        _ensure_users_indexes(conn)
        _ensure_reel_indexes(conn)
        _ensure_reel_fts_columns(conn)


def _ensure_profiles_columns(conn):
    cols = conn.execute(text("PRAGMA table_info(profiles)")).mappings().all()
    col_names = {c["name"] for c in cols}
    additions = {
        "full_name": "TEXT",
        "biography": "TEXT",
        "profile_pic_url": "TEXT",
        "followers": "INTEGER",
        "following": "INTEGER",
        "post_count": "INTEGER",
        "last_fetched_at": "DATETIME",
    }
    for name, ddl in additions.items():
        if name not in col_names:
            conn.execute(text(f"ALTER TABLE profiles ADD COLUMN {name} {ddl}"))


def _ensure_jobs_columns(conn):
    cols = conn.execute(text("PRAGMA table_info(jobs)")).mappings().all()
    col_names = {c["name"] for c in cols}
    additions = {
        "user_id": "INTEGER",
        "job_type": "TEXT DEFAULT 'batch'",
        "target_profile_id": "INTEGER",
        "target_reel_id": "INTEGER",
    }
    for name, ddl in additions.items():
        if name not in col_names:
            conn.execute(text(f"ALTER TABLE jobs ADD COLUMN {name} {ddl}"))


def _ensure_reels_columns(conn):
    cols = conn.execute(text("PRAGMA table_info(reels)")).mappings().all()
    col_names = {c["name"] for c in cols}
    additions = {
        "user_id": "INTEGER",
        "username": "TEXT",
        "thumbnail_path": "TEXT",
        "audio_path": "TEXT",
        "caption": "TEXT",
        "video_duration": "INTEGER",
        "processed": "INTEGER DEFAULT 0",
        "created_at": "DATETIME",
        "summary_detail": "TEXT",
    }
    for name, ddl in additions.items():
        if name not in col_names:
            conn.execute(text(f"ALTER TABLE reels ADD COLUMN {name} {ddl}"))


def _ensure_users_indexes(conn):
    conn.execute(
        text(
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_users_email ON users(email)"
        )
    )


def _ensure_reel_indexes(conn):
    sql = (
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_reels_user_profile_shortcode "
        "ON reels(user_id, profile_id, shortcode)"
    )
    try:
        conn.execute(text(sql))
    except Exception:
        # Clean up pre-index duplicates created by older versions, then retry.
        conn.execute(
            text(
                "DELETE FROM reels "
                "WHERE id IN ("
                "  SELECT r1.id FROM reels r1 "
                "  JOIN reels r2 "
                "    ON r1.user_id = r2.user_id "
                "   AND r1.profile_id = r2.profile_id "
                "   AND r1.shortcode = r2.shortcode "
                "   AND r1.id > r2.id "
                "  WHERE r1.user_id IS NOT NULL"
                ")"
            )
        )
        conn.execute(text(sql))


def _ensure_reel_fts_columns(conn):
    cols = conn.execute(text("PRAGMA table_info(reel_fts)")).mappings().all()
    col_names = {c["name"] for c in cols}
    if "summary_detail" not in col_names:
        try:
            conn.execute(text("ALTER TABLE reel_fts ADD COLUMN summary_detail"))
        except Exception:
            # Keep backward compatibility with older FTS layout.
            pass


def upsert_reel_fts(conn, reel_id: int, ai_title: str, ai_summary: str, transcript: str, summary_detail: str = ""):
    # Simple delete/insert to keep FTS in sync
    conn.execute(text("DELETE FROM reel_fts WHERE reel_id = :rid"), {"rid": reel_id})
    params = {
        "rid": reel_id,
        "t": ai_title or "",
        "s": ai_summary or "",
        "sd": summary_detail or "",
        "tr": transcript or "",
    }
    try:
        conn.execute(
            text(
                "INSERT INTO reel_fts(reel_id, ai_title, ai_summary, summary_detail, transcript) "
                "VALUES (:rid, :t, :s, :sd, :tr)"
            ),
            params,
        )
    except Exception:
        conn.execute(
            text(
                "INSERT INTO reel_fts(reel_id, ai_title, ai_summary, transcript) "
                "VALUES (:rid, :t, :s, :tr)"
            ),
            params,
        )


