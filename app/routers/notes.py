import re
from datetime import date

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app.deps import get_current_user
from app.models import Card, CardKind, Note, User
from app.services.extraction import (
    ExtractionError,
    ExtractionUnavailable,
    Extractor,
    LineExtractor,
    get_extractor,
    normalize,
)
from app.templating import templates
from app.timeutil import local_date, utcnow

router = APIRouter(prefix="/notes")


def _get_note(db: Session, user: User, note_id: int) -> Note:
    note = db.get(Note, note_id)
    if note is None or note.user_id != user.id:
        raise HTTPException(404, "Заметка не найдена")
    return note


def known_texts(db: Session, user: User) -> set[str]:
    return {normalize(t) for t in db.scalars(select(Card.text).where(Card.user_id == user.id))}


@router.get("")
def notes_list(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    notes = list(
        db.scalars(
            select(Note)
            .where(Note.user_id == user.id)
            .options(selectinload(Note.cards))
            .order_by(Note.lesson_date.desc(), Note.id.desc())
        )
    )
    return templates.TemplateResponse(request, "notes/list.html", {"notes": notes, "tab": "notes"})


@router.get("/new")
def new_note_page(request: Request, user: User = Depends(get_current_user)):
    return templates.TemplateResponse(
        request,
        "notes/new.html",
        {"today": local_date(utcnow()).isoformat(), "form": {}, "tab": "today"},
    )


@router.post("")
def create_note(
    request: Request,
    lesson_date: date = Form(...),
    topic: str = Form(""),
    text: str = Form(""),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    extractor: Extractor = Depends(get_extractor),
):
    if not text.strip():
        return templates.TemplateResponse(
            request,
            "notes/new.html",
            {
                "today": lesson_date.isoformat(),
                "form": {"topic": topic},
                "error": "Заметка пустая — напиши хотя бы пару слов с занятия",
                "tab": "today",
            },
            status_code=400,
        )

    note = Note(user_id=user.id, lesson_date=lesson_date, topic=topic.strip(), text=text.strip())
    fallback_reason = None
    try:
        items = extractor.extract(note.text, note.topic)
        source = extractor.name
    except (ExtractionUnavailable, ExtractionError) as e:
        fallback_reason = "offline" if isinstance(e, ExtractionUnavailable) else "bad_answer"
        items = LineExtractor().extract(note.text, note.topic)
        source = "lines"

    note.extracted = [i.model_dump() for i in items]
    note.extracted_by = source
    db.add(note)
    db.commit()

    url = f"/notes/{note.id}/words"
    if fallback_reason:
        url += f"?fallback={fallback_reason}"
    return RedirectResponse(url, status_code=303)


@router.get("/{note_id}/words")
def words_page(
    request: Request,
    note_id: int,
    fallback: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    note = _get_note(db, user, note_id)
    known = known_texts(db, user)
    items = [dict(item, known=normalize(item["text"]) in known) for item in (note.extracted or [])]
    return templates.TemplateResponse(
        request,
        "notes/words.html",
        {"note": note, "items": items, "fallback": fallback, "tab": "today"},
    )


_FIELD = re.compile(r"^items-(\d+)-(\w+)$")
CARD_FIELDS = ("text", "translation", "kind", "transcription", "example", "tutor_note")


def parse_items_form(form) -> list[dict]:
    rows: dict[int, dict] = {}
    for key, value in form.multi_items():
        m = _FIELD.match(key)
        if m:
            rows.setdefault(int(m.group(1)), {})[m.group(2)] = str(value).strip()
    return [rows[i] for i in sorted(rows)]


@router.post("/{note_id}/cards")
async def save_cards(
    request: Request,
    note_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    note = _get_note(db, user, note_id)
    known = known_texts(db, user)
    created = 0
    for row in parse_items_form(await request.form()):
        if row.get("include") != "on" or not row.get("text") or not row.get("translation"):
            continue
        key = normalize(row["text"])
        if key in known:
            continue
        known.add(key)
        db.add(
            Card(
                user_id=user.id,
                note_id=note.id,
                kind=CardKind.rule if row.get("kind") == "rule" else CardKind.word,
                **{f: row.get(f, "")[:300] for f in CARD_FIELDS if f != "kind"},
            )
        )
        created += 1
    note.extracted = None
    db.commit()
    return RedirectResponse(f"/notes/{note.id}?added={created}", status_code=303)


@router.get("/{note_id}")
def note_detail(
    request: Request,
    note_id: int,
    added: int | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    note = _get_note(db, user, note_id)
    return templates.TemplateResponse(
        request, "notes/detail.html", {"note": note, "added": added, "tab": "notes"}
    )


@router.post("/{note_id}/delete")
def delete_note(note_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    note = _get_note(db, user, note_id)
    db.delete(note)  # карточки остаются в словаре, у них просто пропадёт ссылка на заметку
    db.commit()
    return RedirectResponse("/notes", status_code=303)
