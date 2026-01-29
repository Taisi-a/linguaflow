# main.py
from datetime import datetime

from fastapi import FastAPI, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import database
import auth

app = FastAPI(title="English Learning")

# Подключаем статику и шаблоны
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


# Зависимость для БД
def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Простое хранилище сессий в памяти (для MVP)
sessions = {}  # {session_id: user_id}


# ========== РОУТЫ ==========

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Главная страница"""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    """Страница регистрации"""
    return templates.TemplateResponse("register.html", {"request": request})


@app.post("/register")
async def register(
        request: Request,
        username: str = Form(...),
        email: str = Form(...),
        password: str = Form(...),
        db: Session = Depends(get_db)
):
    """Регистрация пользователя"""
    # Проверяем, существует ли пользователь
    existing_user = db.query(database.User).filter(
        (database.User.username == username) | (database.User.email == email)
    ).first()

    if existing_user:
        raise HTTPException(status_code=400, detail="Username or email already exists")

    # Создаем пользователя
    user = database.User(
        username=username,
        email=email,
        hashed_password=auth.hash_password(password)
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    # Создаем простую сессию
    session_id = str(hash(f"{user.id}{datetime.utcnow()}"))
    sessions[session_id] = user.id

    # Редирект в личный кабинет
    response = RedirectResponse(url="/dashboard", status_code=303)
    response.set_cookie(key="session_id", value=session_id)
    return response


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Страница входа"""
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/login")
async def login(
        request: Request,
        username: str = Form(...),
        password: str = Form(...),
        db: Session = Depends(get_db)
):
    """Вход пользователя"""
    user = db.query(database.User).filter(database.User.username == username).first()

    if not user or not auth.verify_password(password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Создаем сессию
    session_id = str(hash(f"{user.id}{datetime.utcnow()}"))
    sessions[session_id] = user.id

    response = RedirectResponse(url="/dashboard", status_code=303)
    response.set_cookie(key="session_id", value=session_id)
    return response


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(
        request: Request,
        db: Session = Depends(database.get_db)
):
    """Личный кабинет"""
    user = get_current_user(request, db)

    if not user:
        # Если пользователь не авторизован, перенаправляем на вход
        return RedirectResponse("/login", status_code=303)

    # Получаем слова пользователя
    words = db.query(database.Word).filter(
        database.Word.user_id == user.id
    ).order_by(database.Word.added_date.desc()).limit(20).all()

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": user,
        "words": words,
        "word_count": len(words)
    })


@app.get("/logout")
async def logout():
    """Выход"""
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie(key="session_id")
    return response


# ========== ЗАЩИЩЕННЫЕ РОУТЫ ==========

def get_current_user(request: Request, db: Session = Depends(get_db)):
    """Получаем текущего пользователя из сессии"""
    session_id = request.cookies.get("session_id")

    if not session_id or session_id not in sessions:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user_id = sessions[session_id]
    user = db.query(database.User).filter(database.User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return user


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(
        request: Request,
        current_user: database.User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Личный кабинет"""
    # Получаем слова пользователя
    words = db.query(database.Word).filter(
        database.Word.user_id == current_user.id
    ).order_by(database.Word.added_date.desc()).limit(20).all()

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": current_user,
        "words": words,
        "word_count": len(words)
    })


@app.post("/words/add")
async def add_word(
        english: str = Form(...),
        russian: str = Form(...),
        example: str = Form(None),
        category: str = Form("general"),
        current_user: database.User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Добавление нового слова"""
    word = database.Word(
        user_id=current_user.id,
        english=english.strip(),
        russian=russian.strip(),
        example=example,
        category=category
    )

    db.add(word)
    db.commit()

    return RedirectResponse(url="/dashboard", status_code=303)


@app.get("/words/delete/{word_id}")
async def delete_word(
        word_id: int,
        current_user: database.User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Удаление слова"""
    word = db.query(database.Word).filter(
        database.Word.id == word_id,
        database.Word.user_id == current_user.id
    ).first()

    if word:
        db.delete(word)
        db.commit()

    return RedirectResponse(url="/dashboard", status_code=303)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)