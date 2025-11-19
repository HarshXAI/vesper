"""
Database connection and session management

Provides SQLAlchemy engine and session creation.
"""
from contextlib import contextmanager
from typing import Generator
from sqlalchemy import create_engine, Engine, text
from sqlalchemy.orm import sessionmaker, Session
import structlog

from vesper_ingestion.config import get_config

logger = structlog.get_logger()


# Global engine instance
_engine: Engine | None = None
_SessionLocal: sessionmaker | None = None


def get_engine() -> Engine:
    """
    Get or create SQLAlchemy engine
    
    Returns:
        SQLAlchemy Engine instance
    """
    global _engine
    
    if _engine is None:
        config = get_config()
        connection_string = config.database.connection_string
        
        _engine = create_engine(
            connection_string,
            pool_pre_ping=True,  # Verify connections before using
            pool_size=5,
            max_overflow=10,
            echo=False  # Set to True for SQL debugging
        )
        
        logger.info(
            "database_engine_created",
            host=config.database.postgres_host,
            port=config.database.postgres_port,
            database=config.database.postgres_db
        )
    
    return _engine


def get_session_maker() -> sessionmaker:
    """
    Get or create session maker
    
    Returns:
        SQLAlchemy session maker
    """
    global _SessionLocal
    
    if _SessionLocal is None:
        engine = get_engine()
        _SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=engine
        )
    
    return _SessionLocal


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """
    Get database session with automatic cleanup
    
    Usage:
        with get_session() as session:
            session.query(FilingRecord).all()
    
    Yields:
        SQLAlchemy Session
    """
    SessionLocal = get_session_maker()
    session = SessionLocal()
    
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db():
    """
    Initialize database - create tables if they don't exist
    
    Note: In production, use Alembic migrations instead.
    """
    from vesper_ingestion.db.models import Base
    
    engine = get_engine()
    
    # Create bronze schema if it doesn't exist
    with engine.connect() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS bronze"))
        conn.commit()
    
    # Create tables
    Base.metadata.create_all(bind=engine)
    
    logger.info("database_initialized")


def close_engine():
    """Close database engine and clean up connections"""
    global _engine, _SessionLocal
    
    if _engine is not None:
        _engine.dispose()
        _engine = None
        _SessionLocal = None
        logger.info("database_engine_closed")
