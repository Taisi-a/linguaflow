from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app.deps import get_current_user
from app.models import Card, CardKind, User
from app.services.study import LEARNED_INTERVAL
from app.templating import templates

router = APIRouter(prefix="/words")


def _get_card(db: Session, user: User, card_id: int) -> Card:
    card = db.get(Card, card_id)
    if card is None or card.user_id != user.id:
        raise HTTPException(404, "Карточка не найдена")
    return card


@router.get("")
def words_list(
    request: Request,
    q: str = "",
    kind: str = "",
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stmt = select(Card).where(Card.user_id == user.id).options(selectinload(Card.note))
    if q.strip():
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Card.text.ilike(like), Card.translation.ilike(like)))
    if kind in ("word", "rule"):
        stmt = stmt.where(Card.kind == CardKind(kind))
    cards = list(db.scalars(stmt.order_by(Card.created_at.desc(), Card.id.desc())))
    return templates.TemplateResponse(
        request,
        "words/list.html",
        {"cards": cards, "q": q, "kind": kind, "learned_interval": LEARNED_INTERVAL, "tab": "words"},
    )


@router.get("/{card_id}/edit")
def edit_page(
    request: Request, card_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    card = _get_card(db, user, card_id)
    return templates.TemplateResponse(request, "words/edit.html", {"card": card, "tab": "words"})


@router.post("/{card_id}")
def update_card(
    card_id: int,
    text: str = Form(...),
    translation: str = Form(...),
    kind: str = Form("word"),
    transcription: str = Form(""),
    example: str = Form(""),
    tutor_note: str = Form(""),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    card = _get_card(db, user, card_id)
    card.text = text.strip()
    card.translation = translation.strip()
    card.kind = CardKind.rule if kind == "rule" else CardKind.word
    card.transcription = transcription.strip()
    card.example = example.strip()
    card.tutor_note = tutor_note.strip()
    db.commit()
    return RedirectResponse("/words", status_code=303)


@router.post("/{card_id}/delete")
def delete_card(card_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.delete(_get_card(db, user, card_id))
    db.commit()
    return RedirectResponse("/words", status_code=303)
