from datetime import datetime

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app.deps import get_current_user
from app.models import Card, Note, User
from app.services import study
from app.services.srs import GRADE_LABELS, Grade, humanize_delay, preview
from app.templating import templates
from app.timeutil import utcnow

router = APIRouter()

SESSION_COOKIE = "review_started"


def _session_start(request: Request) -> datetime | None:
    raw = request.cookies.get(SESSION_COOKIE)
    try:
        return datetime.fromisoformat(raw) if raw else None
    except ValueError:
        return None


@router.get("/")
def today(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    notes = list(
        db.scalars(
            select(Note)
            .where(Note.user_id == user.id)
            .options(selectinload(Note.cards))
            .order_by(Note.lesson_date.desc(), Note.id.desc())
            .limit(5)
        )
    )
    has_cards = db.scalar(select(Card.id).where(Card.user_id == user.id).limit(1)) is not None
    return templates.TemplateResponse(
        request,
        "today.html",
        {
            "due": study.due_count(db, user),
            "next_due": study.next_due_at(db, user),
            "streak": study.streak(db, user),
            "notes": notes,
            "has_cards": has_cards,
            "tab": "today",
        },
    )


@router.get("/review/start")
def review_start():
    response = RedirectResponse("/review", status_code=303)
    response.set_cookie(SESSION_COOKIE, utcnow().isoformat(), httponly=True, samesite="lax")
    return response


@router.get("/review")
def review(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    started = _session_start(request)
    if started is None:
        return RedirectResponse("/review/start", status_code=303)

    queue = study.due_cards(db, user)
    if not queue:
        return RedirectResponse("/review/summary", status_code=303)

    card = queue[0]
    progress = study.session_progress(db, user, started, queue)
    buttons = [
        {"grade": int(g), "label": GRADE_LABELS[g], "hint": humanize_delay(d)}
        for g, d in preview(study.state_of(card)).items()
    ]
    return templates.TemplateResponse(
        request,
        "review/card.html",
        {"card": card, "progress": progress, "buttons": buttons, "hide_tabs": True},
    )


@router.post("/review/{card_id}")
def grade_card(
    card_id: int,
    grade: int = Form(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    card = db.get(Card, card_id)
    if card is None or card.user_id != user.id:
        raise HTTPException(404, "Карточка не найдена")
    try:
        g = Grade(grade)
    except ValueError:
        raise HTTPException(400, "Неизвестная оценка") from None
    study.apply_review(db, card, g)
    return RedirectResponse("/review", status_code=303)


@router.get("/review/summary")
def review_summary(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    started = _session_start(request)
    if started is None:
        return RedirectResponse("/", status_code=303)
    summary = study.session_summary(db, user, started)
    response = templates.TemplateResponse(
        request,
        "review/summary.html",
        {"summary": summary, "streak": study.streak(db, user), "hide_tabs": True},
    )
    response.delete_cookie(SESSION_COOKIE)
    return response


@router.get("/profile")
def profile(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        request, "profile.html", {"user": user, "stats": study.user_stats(db, user), "tab": "profile"}
    )
