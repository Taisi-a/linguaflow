from datetime import timedelta

import pytest

from app.services.srs import Grade, SrsState, humanize_delay, preview, schedule

NEW = SrsState()


def review_state(interval=10, ease=2.5):
    return SrsState(status="review", ease=ease, interval_days=interval, repetitions=3)


def test_new_card_matches_design_labels():
    # Подписи под кнопками в макете: 1 мин, 10 мин, 1 день, 4 дня
    labels = {g: humanize_delay(d) for g, d in preview(NEW).items()}
    assert labels == {
        Grade.AGAIN: "через 1 мин",
        Grade.HARD: "через 10 мин",
        Grade.GOOD: "через 1 день",
        Grade.EASY: "через 4 дня",
    }


def test_again_and_hard_keep_new_card_in_learning():
    for grade in (Grade.AGAIN, Grade.HARD):
        result = schedule(NEW, grade)
        assert result.state.status == "learning"
        assert result.state.interval_days == 0


def test_good_graduates_card_to_review():
    result = schedule(NEW, Grade.GOOD)
    assert result.state.status == "review"
    assert result.state.interval_days == 1
    assert result.delay == timedelta(days=1)


def test_easy_increases_ease():
    assert schedule(NEW, Grade.EASY).state.ease == pytest.approx(2.65)


def test_review_good_multiplies_interval_by_ease():
    result = schedule(review_state(interval=10, ease=2.5), Grade.GOOD)
    assert result.state.interval_days == 25


def test_review_intervals_are_ordered():
    state = review_state(interval=10)
    hard, good, easy = (schedule(state, g).state.interval_days for g in (Grade.HARD, Grade.GOOD, Grade.EASY))
    assert 10 < hard < good < easy


def test_interval_always_grows_even_with_low_ease():
    state = review_state(interval=1, ease=1.3)
    assert schedule(state, Grade.HARD).state.interval_days >= 2
    assert schedule(state, Grade.GOOD).state.interval_days >= 2


def test_lapse_resets_interval_and_lowers_ease():
    result = schedule(review_state(interval=30, ease=2.5), Grade.AGAIN)
    assert result.state.status == "learning"
    assert result.state.interval_days == 0
    assert result.state.lapses == 1
    assert result.state.ease == pytest.approx(2.3)
    assert result.delay == timedelta(minutes=1)


def test_ease_never_drops_below_minimum():
    state = review_state(ease=1.3)
    assert schedule(state, Grade.AGAIN).state.ease == 1.3
    assert schedule(state, Grade.HARD).state.ease == 1.3


def test_relearned_card_graduates_back_to_one_day():
    lapsed = schedule(review_state(interval=30), Grade.AGAIN).state
    assert schedule(lapsed, Grade.GOOD).state.interval_days == 1


@pytest.mark.parametrize(
    "delay, text",
    [
        (timedelta(minutes=1), "через 1 мин"),
        (timedelta(days=1), "через 1 день"),
        (timedelta(days=3), "через 3 дня"),
        (timedelta(days=11), "через 11 дней"),
        (timedelta(days=21), "через 21 день"),
        (timedelta(days=90), "через 3 месяца"),
    ],
)
def test_humanize_delay(delay, text):
    assert humanize_delay(delay) == text
