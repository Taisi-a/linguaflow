import enum
from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.timeutil import utcnow


class CardKind(str, enum.Enum):
    word = "word"
    rule = "rule"


class CardStatus(str, enum.Enum):
    new = "new"
    learning = "learning"
    review = "review"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    notes: Mapped[list["Note"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    cards: Mapped[list["Card"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Note(Base):
    """Заметка с занятия — как страница в тетради."""

    __tablename__ = "notes"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    lesson_date: Mapped[date] = mapped_column(Date)
    topic: Mapped[str] = mapped_column(String(120), default="")
    text: Mapped[str] = mapped_column(Text)
    # Что нашёл экстрактор, пока пользователь не подтвердил список слов
    extracted: Mapped[list | None] = mapped_column(JSON, nullable=True)
    extracted_by: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    user: Mapped[User] = relationship(back_populates="notes")
    cards: Mapped[list["Card"]] = relationship(back_populates="note")


class Card(Base):
    __tablename__ = "cards"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    note_id: Mapped[int | None] = mapped_column(
        ForeignKey("notes.id", ondelete="SET NULL"), nullable=True, index=True
    )

    kind: Mapped[CardKind] = mapped_column(Enum(CardKind), default=CardKind.word)
    text: Mapped[str] = mapped_column(String(200))
    translation: Mapped[str] = mapped_column(String(300))
    transcription: Mapped[str] = mapped_column(String(100), default="")
    example: Mapped[str] = mapped_column(Text, default="")
    tutor_note: Mapped[str] = mapped_column(Text, default="")

    # Состояние интервального повторения
    status: Mapped[CardStatus] = mapped_column(Enum(CardStatus), default=CardStatus.new)
    ease: Mapped[float] = mapped_column(Float, default=2.5)
    interval_days: Mapped[int] = mapped_column(Integer, default=0)
    repetitions: Mapped[int] = mapped_column(Integer, default=0)
    lapses: Mapped[int] = mapped_column(Integer, default=0)
    due_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    user: Mapped[User] = relationship(back_populates="cards")
    note: Mapped[Note | None] = relationship(back_populates="cards")
    reviews: Mapped[list["ReviewLog"]] = relationship(back_populates="card", cascade="all, delete-orphan")


class ReviewLog(Base):
    """Каждый ответ на карточку. Из этой таблицы считается вся статистика."""

    __tablename__ = "review_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    card_id: Mapped[int] = mapped_column(ForeignKey("cards.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    grade: Mapped[int] = mapped_column(Integer)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    interval_before: Mapped[int] = mapped_column(Integer, default=0)
    interval_after: Mapped[int] = mapped_column(Integer, default=0)

    card: Mapped[Card] = relationship(back_populates="reviews")
