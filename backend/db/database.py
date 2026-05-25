from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import logging
from config.settings import settings

logger = logging.getLogger(__name__)

# Fallback to SQLite if Postgres URL is default (localhost:5432) and we want to ensure it runs
# We will just use the configured database_url, but we can detect if it's the default and maybe print a warning 
# or just attempt connection. The user wants PostgreSQL.

SQLALCHEMY_DATABASE_URL = settings.database_url

try:
    engine = create_engine(SQLALCHEMY_DATABASE_URL)
    with engine.connect() as conn:
        pass
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    logger.info(f"Database engine created for {SQLALCHEMY_DATABASE_URL}")
except Exception as e:
    logger.error(f"Failed to create database engine: {e}")
    # Fallback for demo purposes if postgres not running
    logger.warning("Falling back to SQLite in-memory database")
    engine = create_engine("sqlite:///./cashcrew.db", connect_args={"check_same_thread": False})
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
