from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import User
from app.security import COOKIE_NAME, create_access_token, hash_password, verify_password
from app.templating import templates

router = APIRouter()

MIN_PASSWORD = 8


def _login_response(user: User) -> RedirectResponse:
    settings = get_settings()
    response = RedirectResponse("/", status_code=303)
    response.set_cookie(
        COOKIE_NAME,
        create_access_token(user.id),
        max_age=settings.access_token_days * 24 * 3600,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
    )
    return response


@router.get("/login")
def login_page(request: Request):
    return templates.TemplateResponse(request, "auth/login.html", {})


@router.post("/login")
def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = db.scalar(select(User).where(User.username == username.strip().lower()))
    if user is None or not verify_password(password, user.hashed_password):
        return templates.TemplateResponse(
            request,
            "auth/login.html",
            {"error": "Неверное имя пользователя или пароль", "username": username},
            status_code=400,
        )
    return _login_response(user)


@router.get("/register")
def register_page(request: Request):
    return templates.TemplateResponse(request, "auth/register.html", {})


@router.post("/register")
def register(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    username = username.strip().lower()
    error = None
    if not 3 <= len(username) <= 50:
        error = "Имя пользователя — от 3 до 50 символов"
    elif len(password) < MIN_PASSWORD:
        error = f"Пароль — не короче {MIN_PASSWORD} символов"
    elif db.scalar(select(User).where(User.username == username)):
        error = "Такое имя уже занято"
    if error:
        return templates.TemplateResponse(
            request, "auth/register.html", {"error": error, "username": username}, status_code=400
        )

    user = User(username=username, hashed_password=hash_password(password))
    db.add(user)
    db.commit()
    return _login_response(user)


@router.post("/logout")
def logout():
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie(COOKIE_NAME)
    return response
