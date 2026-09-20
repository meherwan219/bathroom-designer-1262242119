"""SQLAlchemy declarative base + engine/session wiring.
Phase 1 fills in the ORM models (products, designs, design_items, ...)
per the schema in plan.md."""
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    pass


engine = create_engine(settings.database_url, echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
