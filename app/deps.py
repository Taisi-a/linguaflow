from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app.security import COOKIE_NAME, decode_access_token


class NotAuthenticated(Exception):
    """Перехватывается в main.py и превращается в редирект на /login."""


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get(COOKIE_NAME)
    user_id = decode_access_token(token) if token else None
    user = db.get(User, user_id) if user_id else None
    if user is None:
        raise NotAuthenticated
    return user
