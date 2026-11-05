from datetime import timedelta

from sqlalchemy import select

from app.models import Card, ReviewLog
from app.services import study
from app.services.extraction import ExtractionUnavailable
from app.timeutil import utcnow


def create_note(client, text="come up with — придумать\ngive up — сдаться", topic="Phrasal verbs"):
    return client.post(
        "/notes", data={"lesson_date": "2026-10-21", "topic": topic, "text": text}, follow_redirects=False
    )


def confirm_all(client, note_id, items):
    data = {}
    for i, item in enumerate(items):
        data[f"items-{i}-include"] = "on"
        for key, value in item.items():
            data[f"items-{i}-{key}"] = value
    return client.post(f"/notes/{note_id}/cards", data=data, follow_redirects=False)


# ---------- авторизация ----------


def test_pages_redirect_to_login_without_auth(client):
    for url in ("/", "/notes", "/words", "/review", "/profile"):
        r = client.get(url, follow_redirects=False)
        assert r.status_code == 303 and r.headers["location"] == "/login", url


def test_register_sets_httponly_jwt_cookie(client):
    r = client.post(
        "/register", data={"username": "Taisia", "password": "password123"}, follow_redirects=False
    )
    assert r.status_code == 303
    cookie = r.headers["set-cookie"]
    assert "access_token=" in cookie and "HttpOnly" in cookie


def test_register_rejects_short_password_and_duplicates(client):
    assert client.post("/register", data={"username": "anna", "password": "123"}).status_code == 400
    client.post("/register", data={"username": "anna", "password": "password123"})
    client.cookies.clear()
    assert client.post("/register", data={"username": "ANNA", "password": "password123"}).status_code == 400


def test_login_and_logout(client):
    client.post("/register", data={"username": "anna", "password": "password123"})
    client.cookies.clear()
    assert client.post("/login", data={"username": "anna", "password": "wrong-pass"}).status_code == 400
    r = client.post("/login", data={"username": "anna", "password": "password123"}, follow_redirects=False)
    assert r.status_code == 303
    assert client.get("/", follow_redirects=False).status_code == 200
    client.post("/logout")
    client.cookies.clear()
    assert client.get("/", follow_redirects=False).status_code == 303


def test_forged_token_is_rejected(client):
    client.cookies.set("access_token", "not-a-jwt")
    assert client.get("/", follow_redirects=False).status_code == 303


# ---------- заметки и карточки ----------


def test_first_launch_state(auth_client):
    assert "Первый запуск" in auth_client.get("/").text


def test_note_flow_creates_cards(auth_client, db_session, extractor):
    r = create_note(auth_client)
    assert r.status_code == 303
    words_url = r.headers["location"]
    assert words_url.endswith("/words")

    page = auth_client.get(words_url).text
    assert "Нашли 3 слова" in page and "come up with" in page

    note_id = int(words_url.split("/")[2])
    items = [i.model_dump() for i in extractor.items]
    r = confirm_all(auth_client, note_id, items)
    assert r.headers["location"] == f"/notes/{note_id}?added=3"

    cards = list(db_session.scalars(select(Card)))
    assert {c.text for c in cards} == {"come up with", "give up", "look forward to + -ing"}
    assert next(c for c in cards if c.text == "come up with").tutor_note == "не путать с come across"
    assert "3 слова ждут" in auth_client.get("/").text


def test_unchecked_and_known_words_are_not_added(auth_client, db_session, extractor):
    note_id = int(create_note(auth_client).headers["location"].split("/")[2])
    items = [i.model_dump() for i in extractor.items]
    confirm_all(auth_client, note_id, items[:1])

    # Вторая заметка с тем же словом: на экране оно помечено как уже известное
    note2 = int(create_note(auth_client).headers["location"].split("/")[2])
    assert "уже есть в словаре" in auth_client.get(f"/notes/{note2}/words").text

    data = {
        "items-0-include": "on",
        "items-0-text": "Come up with",
        "items-0-translation": "придумать",
        "items-1-text": "give up",
        "items-1-translation": "сдаться",  # галочка снята
        "items-2-include": "on",
        "items-2-text": "turn down",
        "items-2-translation": "отказаться",
    }
    auth_client.post(f"/notes/{note2}/cards", data=data)
    assert sorted(db_session.scalars(select(Card.text))) == ["come up with", "turn down"]


def test_empty_note_is_rejected(auth_client):
    r = create_note(auth_client, text="   ")
    assert r.status_code == 400 and "Заметка пустая" in r.text


def test_falls_back_to_line_parser_when_llm_unavailable(auth_client, extractor):
    extractor.error = ExtractionUnavailable("no network")
    r = create_note(auth_client, text="come up with — придумать\nкакой-то текст")
    assert r.headers["location"].endswith("?fallback=offline")
    page = auth_client.get(r.headers["location"]).text
    assert "ИИ сейчас недоступен" in page and "Нашли 1 слово" in page


def test_cannot_access_other_users_data(auth_client, client, db_session, extractor):
    note_id = int(create_note(auth_client).headers["location"].split("/")[2])
    confirm_all(auth_client, note_id, [i.model_dump() for i in extractor.items])
    card_id = db_session.scalar(select(Card.id))

    client.cookies.clear()
    client.post("/register", data={"username": "other", "password": "password123"})
    assert client.get(f"/notes/{note_id}").status_code == 404
    assert client.get(f"/words/{card_id}/edit").status_code == 404
    assert client.post(f"/review/{card_id}", data={"grade": 3}).status_code == 404


def test_edit_and_delete_card(auth_client, db_session, extractor):
    note_id = int(create_note(auth_client).headers["location"].split("/")[2])
    confirm_all(auth_client, note_id, [i.model_dump() for i in extractor.items[:1]])
    card = db_session.scalar(select(Card))
    auth_client.post(f"/words/{card.id}", data={"text": "come up with", "translation": "выдумать"})
    db_session.refresh(card)
    assert card.translation == "выдумать"
    assert "выдумать" in auth_client.get("/words?q=выдум").text
    auth_client.post(f"/words/{card.id}/delete")
    assert db_session.scalar(select(Card)) is None


# ---------- повторение ----------


def test_review_session_and_summary(auth_client, db_session, extractor):
    note_id = int(create_note(auth_client).headers["location"].split("/")[2])
    confirm_all(auth_client, note_id, [i.model_dump() for i in extractor.items])

    page = auth_client.get("/review/start").text
    assert "Карточка 1 из 3" in page and "через 4 дня" in page

    ids = list(db_session.scalars(select(Card.id).order_by(Card.due_at, Card.id)))
    auth_client.post(f"/review/{ids[0]}", data={"grade": 3})  # Помню → завтра
    auth_client.post(f"/review/{ids[1]}", data={"grade": 1})  # Не помню → через минуту, ещё сегодня
    assert "Карточка 3 из 3" in auth_client.get("/review").text
    auth_client.post(f"/review/{ids[2]}", data={"grade": 4})  # Легко → через 4 дня

    # Забытая карточка возвращается в эту же сессию
    assert "Карточка 3 из 3" in auth_client.get("/review").text
    r = auth_client.post(f"/review/{ids[1]}", data={"grade": 3}, follow_redirects=False)
    assert r.headers["location"] == "/review"

    r = auth_client.get("/review", follow_redirects=False)
    assert r.headers["location"] == "/review/summary"
    summary = auth_client.get("/review/summary").text
    assert "Повторено" in summary and "3 слова" in summary
    assert db_session.scalar(select(ReviewLog.id).where(ReviewLog.grade == 1)) is not None


def test_invalid_grade_is_rejected(auth_client, db_session, extractor):
    note_id = int(create_note(auth_client).headers["location"].split("/")[2])
    confirm_all(auth_client, note_id, [i.model_dump() for i in extractor.items[:1]])
    card_id = db_session.scalar(select(Card.id))
    assert auth_client.post(f"/review/{card_id}", data={"grade": 7}).status_code == 400


def test_streak_counts_consecutive_days(auth_client, db_session, extractor):
    note_id = int(create_note(auth_client).headers["location"].split("/")[2])
    confirm_all(auth_client, note_id, [i.model_dump() for i in extractor.items[:1]])
    card = db_session.scalar(select(Card))
    now = utcnow()
    for days_ago in (1, 2, 3, 5):  # разрыв на 4-й день
        db_session.add(
            ReviewLog(
                card_id=card.id, user_id=card.user_id, grade=3, reviewed_at=now - timedelta(days=days_ago)
            )
        )
    db_session.commit()
    user = card.user
    assert study.streak(db_session, user) == 3  # сегодня ещё не повторяла — серия не сгорела
    study.apply_review(db_session, card, study.Grade.GOOD)
    assert study.streak(db_session, user) == 4


def test_profile_shows_stats(auth_client, extractor):
    note_id = int(create_note(auth_client).headers["location"].split("/")[2])
    confirm_all(auth_client, note_id, [i.model_dump() for i in extractor.items])
    page = auth_client.get("/profile").text
    assert "taisia" in page and "2 / 1" in page


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}
