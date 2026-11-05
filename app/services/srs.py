"""Интервальное повторение: SM-2 в варианте Anki.

Новые карточки сначала проходят короткие шаги в минутах («Не помню» — через 1 мин,
«Сложно» — через 10 мин), а после «Помню» или «Легко» переходят в повторение по дням,
где интервал растёт умножением на коэффициент лёгкости (ease).

Модуль не знает ни про БД, ни про FastAPI: на вход состояние и оценка, на выход новое
состояние. Поэтому вся логика проверяется обычными юнит-тестами.
"""

from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from enum import IntEnum

MIN_EASE = 1.3
AGAIN_STEP = timedelta(minutes=1)
HARD_STEP = timedelta(minutes=10)
GRADUATING_INTERVAL = 1  # дней после «Помню» для новой карточки
EASY_INTERVAL = 4  # дней после «Легко» для новой карточки
HARD_MULTIPLIER = 1.2
EASY_BONUS = 1.3


class Grade(IntEnum):
    AGAIN = 1  # Не помню
    HARD = 2  # Сложно
    GOOD = 3  # Помню
    EASY = 4  # Легко


GRADE_LABELS = {
    Grade.AGAIN: "Не помню",
    Grade.HARD: "Сложно",
    Grade.GOOD: "Помню",
    Grade.EASY: "Легко",
}


@dataclass(frozen=True)
class SrsState:
    status: str = "new"  # new | learning | review
    ease: float = 2.5
    interval_days: int = 0
    repetitions: int = 0
    lapses: int = 0


@dataclass(frozen=True)
class Scheduled:
    state: SrsState
    delay: timedelta

    def due_at(self, now: datetime) -> datetime:
        return now + self.delay


def schedule(state: SrsState, grade: Grade) -> Scheduled:
    grade = Grade(grade)
    if state.status in ("new", "learning"):
        return _schedule_learning(state, grade)
    return _schedule_review(state, grade)


def _schedule_learning(state: SrsState, grade: Grade) -> Scheduled:
    if grade == Grade.AGAIN:
        return Scheduled(replace(state, status="learning"), AGAIN_STEP)
    if grade == Grade.HARD:
        return Scheduled(replace(state, status="learning"), HARD_STEP)
    if grade == Grade.GOOD:
        interval = GRADUATING_INTERVAL
        new = replace(state, status="review", interval_days=interval, repetitions=state.repetitions + 1)
        return Scheduled(new, timedelta(days=interval))
    interval = EASY_INTERVAL
    new = replace(
        state,
        status="review",
        interval_days=interval,
        repetitions=state.repetitions + 1,
        ease=state.ease + 0.15,
    )
    return Scheduled(new, timedelta(days=interval))


def _schedule_review(state: SrsState, grade: Grade) -> Scheduled:
    current = max(state.interval_days, 1)

    if grade == Grade.AGAIN:
        # Забыла — карточка возвращается в короткие шаги, интервал начнётся заново
        new = replace(
            state,
            status="learning",
            interval_days=0,
            lapses=state.lapses + 1,
            ease=max(MIN_EASE, state.ease - 0.2),
        )
        return Scheduled(new, AGAIN_STEP)

    if grade == Grade.HARD:
        interval = max(current + 1, round(current * HARD_MULTIPLIER))
        ease = max(MIN_EASE, state.ease - 0.15)
    elif grade == Grade.GOOD:
        interval = max(current + 1, round(current * state.ease))
        ease = state.ease
    else:
        interval = max(current + 1, round(current * state.ease * EASY_BONUS))
        ease = state.ease + 0.15

    new = replace(state, interval_days=interval, ease=round(ease, 2), repetitions=state.repetitions + 1)
    return Scheduled(new, timedelta(days=interval))


def preview(state: SrsState) -> dict[Grade, timedelta]:
    """Через сколько вернётся карточка при каждой оценке — подписи под кнопками."""
    return {grade: schedule(state, grade).delay for grade in Grade}


def plural(n: int, one: str, few: str, many: str) -> str:
    if n % 10 == 1 and n % 100 != 11:
        return one
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return few
    return many


def humanize_delay(delay: timedelta) -> str:
    minutes = int(delay.total_seconds() // 60)
    if minutes < 60:
        return f"через {minutes} мин"
    days = delay.days
    if days < 30:
        return f"через {days} {plural(days, 'день', 'дня', 'дней')}"
    months = round(days / 30)
    return f"через {months} {plural(months, 'месяц', 'месяца', 'месяцев')}"
