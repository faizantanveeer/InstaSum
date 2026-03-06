from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db import init_engine
from app.models import Base


def main() -> None:
    load_dotenv(ROOT / ".env")

    db_url = (os.getenv("DATABASE_URL") or "").strip()
    if not db_url:
        raise RuntimeError("DATABASE_URL is missing in .env")

    engine = init_engine(db_url)

    with engine.begin() as conn:
        conn.execute(
            text(
                "DROP TABLE IF EXISTS reel_errors, reels, jobs, profiles, users CASCADE"
            )
        )

    Base.metadata.create_all(engine)
    print("Supabase schema initialized")


if __name__ == "__main__":
    main()
