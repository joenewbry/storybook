"""SQLAlchemy engine, session factory, and init."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.config import DATABASE_URL

engine = create_engine(DATABASE_URL, echo=False, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)


def get_session() -> Session:
    return SessionLocal()


def init_db():
    from app.models import Base
    Base.metadata.create_all(engine)
    _migrate_add_video_columns()
    _migrate_add_scene_assets_table()


def _migrate_add_video_columns():
    """Add video columns to shots table if they don't exist (SQLite migration)."""
    from sqlalchemy import text
    with engine.connect() as conn:
        # Check existing columns
        result = conn.execute(text("PRAGMA table_info(shots)"))
        existing = {row[1] for row in result}
        if "video_prompt" not in existing:
            conn.execute(text("ALTER TABLE shots ADD COLUMN video_prompt TEXT DEFAULT ''"))
        if "video_generation_status" not in existing:
            conn.execute(text("ALTER TABLE shots ADD COLUMN video_generation_status VARCHAR(50) DEFAULT 'pending'"))
        conn.commit()


def _migrate_add_scene_assets_table():
    """Create scene_assets table if it doesn't exist."""
    from sqlalchemy import inspect as sa_inspect
    table_names = sa_inspect(engine).get_table_names()
    if "scene_assets" not in table_names:
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE scene_assets (
                    id INTEGER PRIMARY KEY,
                    scene_id INTEGER NOT NULL REFERENCES scenes(id),
                    asset_type VARCHAR(50) DEFAULT 'shot_map',
                    file_path VARCHAR(500) DEFAULT '',
                    generation_params JSON DEFAULT '{}',
                    is_current BOOLEAN DEFAULT 1,
                    created_at DATETIME
                )
            """))
            conn.commit()
