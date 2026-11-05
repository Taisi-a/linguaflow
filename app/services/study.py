"""Очередь повторения, применение оценок и статистика."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import Card, CardKind, CardStatus, ReviewLog, User
from app.services.srs import Grade, SrsState, schedule
from app.timeutil import end_of_local_day_utc, local_date, utcnow

# Карточки на коротких шагах (1 и 10 минут) показываем чуть раньше срока,
# чтобы сессия не обрывалась ожиданием — так делает и Anki.
LEARN_AHEAD = timedelta(minutes=20)
LEARNED_INTERVAL = 21  # с какого интервала считаем слово выученным


def state_of(card: Card) -> SrsState:
    return SrsState(
        status=card.status.value,
        ease=card.ease,
        interval_days=card.interval_days,
        repetitions=card.repetitions,
        lapses=card.lapses,
    )


def _due_filter(user: User, now: datetime):
    return (
        Card.user_id == user.id,
        or_(
            Card.due_at <= now,
            (Card.status == CardStatus.learning) & (Card.due_at <= now + LEARN_AHEAD),
        ),
    )


def due_cards(db: Session, user: User, now: datetime | None = None) -> list[Card]:
    now = now or utcnow()
    stmt = select(Card).where(*_due_filter(user, now)).order_by(Card.due_at, Card.id)
    return list(db.scalars(stmt))


def due_count(db: Session, user: User, now: datetime | None = None) -> int:
    now = now or utcnow()
    return db.scalar(select(func.count(Card.id)).where(*_due_filter(user, now))) or 0


def next_due_at(db: Session, user: User) -> datetime | None:
    return db.scalar(select(func.min(Card.due_at)).where(Card.user_id == user.id))


def apply_review(db: Session, card: Card, grade: Grade, now: datetime | None = None) -> Card:
    now = now or utcnow()
    before = card.interval_days
    result = schedule(state_of(card), grade)
    s = result.state
    card.status = CardStatus(s.status)
    card.ease = s.ease
    card.interval_days = s.interval_days
    card.repetitions = s.repetitions
    card.lapses = s.lapses
    card.due_at = result.due_at(now)
    db.add(
        ReviewLog(
            card_id=card.id,
            user_id=card.user_id,
            grade=int(grade),
            reviewed_at=now,
            interval_before=before,
            interval_after=s.interval_days,
        )
    )
    db.commit()
    return card


@dataclass
class SessionProgress:
    position: int
    total: int


def session_progress(db: Session, user: User, started_at: datetime, queue: list[Card]) -> SessionProgress:
    reviewed_ids = set(
        db.scalars(
            select(ReviewLog.card_id).where(ReviewLog.user_id == user.id, ReviewLog.reviewed_at >= started_at)
        )
    )
    queue_ids = {c.id for c in queue}
    # Номер текущей карточки — сколько разных карточек уже встретилось в сессии,
    # включая эту. Забытая карточка при повторном показе номер не увеличивает.
    seen = reviewed_ids | {queue[0].id} if queue else reviewed_ids
    return SessionProgress(position=len(seen), total=len(reviewed_ids | queue_ids))


@dataclass
class SessionSummary:
    total: int
    recalled_first_try: int
    again_today: int
    tomorrow: int


def session_summary(db: Session, user: User, started_at: datetime) -> SessionSummary:
    logs = list(
        db.scalars(
            select(ReviewLog)
            .where(ReviewLog.user_id == user.id, ReviewLog.reviewed_at >= started_at)
            .order_by(ReviewLog.reviewed_at)
        )
    )
    first_grade: dict[int, int] = {}
    for log in logs:
        first_grade.setdefault(log.card_id, log.grade)

    today = local_date(utcnow())
    end_today = end_of_local_day_utc(today)
    end_tomorrow = end_of_local_day_utc(today + timedelta(days=1))
    cards = list(db.scalars(select(Card).where(Card.id.in_(first_grade.keys())))) if first_grade else []

    return SessionSummary(
        total=len(first_grade),
        recalled_first_try=sum(1 for g in first_grade.values() if g >= Grade.GOOD),
        again_today=sum(1 for c in cards if c.due_at < end_today),
        tomorrow=sum(1 for c in cards if end_today <= c.due_at < end_tomorrow),
    )


def review_days(db: Session, user: User, since_days: int = 400) -> set[date]:
    since = utcnow() - timedelta(days=since_days)
    times = db.scalars(
        select(ReviewLog.reviewed_at).where(ReviewLog.user_id == user.id, ReviewLog.reviewed_at >= since)
    )
    return {local_date(t) for t in times}


def streak(db: Session, user: User) -> int:
    """Сколько дней подряд были повторения. Если сегодня ещё не повторяла,
    серия не сгорает, а считается до вчерашнего дня."""
    days = review_days(db, user)
    day = local_date(utcnow())
    if day not in days:
        day -= timedelta(days=1)
    count = 0
    while day in days:
        count += 1
        day -= timedelta(days=1)
    return count


@dataclass
class Stats:
    cards: int
    words: int
    rules: int
    learned: int
    reviews: int
    accuracy_30d: int | None
    streak: int


def user_stats(db: Session, user: User) -> Stats:
    def count(*where) -> int:
        return db.scalar(select(func.count(Card.id)).where(Card.user_id == user.id, *where)) or 0

    since = utcnow() - timedelta(days=30)
    recent = list(
        db.scalars(
            select(ReviewLog.grade).where(ReviewLog.user_id == user.id, ReviewLog.reviewed_at >= since)
        )
    )
    accuracy = round(100 * sum(g >= Grade.GOOD for g in recent) / len(recent)) if recent else None
    reviews = db.scalar(select(func.count(ReviewLog.id)).where(ReviewLog.user_id == user.id)) or 0

    return Stats(
        cards=count(),
        words=count(Card.kind == CardKind.word),
        rules=count(Card.kind == CardKind.rule),
        learned=count(Card.interval_days >= LEARNED_INTERVAL),
        reviews=reviews,
        accuracy_30d=accuracy,
        streak=streak(db, user),
    )
