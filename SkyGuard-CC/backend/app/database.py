from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import database_url
from app.db.base import Base


engine = create_engine(
    database_url(),
    pool_pre_ping=True,
    pool_recycle=1800,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
