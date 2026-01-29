# auth.py - РЕКОМЕНДУЕМЫЙ ДЛЯ СЕЙЧАС
from passlib.context import CryptContext

# Используем sha256_crypt - нет ограничения по длине, проще
pwd_context = CryptContext(schemes=["sha256_crypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)