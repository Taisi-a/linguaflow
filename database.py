# database.py
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

# SQLite база
engine = create_engine("sqlite:///english_learning.db")
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    level = Column(String, default="beginner")  # beginner, intermediate, advanced


class Word(Base):
    __tablename__ = "words"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True)
    english = Column(String, nullable=False)
    russian = Column(String, nullable=False)
    example = Column(Text)  # Пример использования
    added_date = Column(DateTime, default=datetime.utcnow)
    category = Column(String, default="general")  # general, business, travel...


# Создаем таблицы
Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()