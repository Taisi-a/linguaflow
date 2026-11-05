import os

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.pop("GEMINI_API_KEY", None)

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app
from app.services.extraction import ExtractedItem, get_extractor


class FakeExtractor:
    name = "llm"

    def __init__(self, items=None, error: Exception | None = None):
        self.items = items or []
        self.error = error
        self.calls = []

    def extract(self, text, topic=""):
        self.calls.append((text, topic))
        if self.error:
            raise self.error
        return self.items


@pytest.fixture
def db_session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = Session()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture
def extractor():
    return FakeExtractor(
        items=[
            ExtractedItem(
                text="come up with",
                translation="придумать",
                example="She came up with a plan.",
                tutor_note="не путать с come across",
            ),
            ExtractedItem(text="give up", translation="бросить, сдаться"),
            ExtractedItem(text="look forward to + -ing", translation="ждать с нетерпением", kind="rule"),
        ]
    )


@pytest.fixture
def client(db_session, extractor):
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_extractor] = lambda: extractor
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def auth_client(client):
    r = client.post(
        "/register", data={"username": "taisia", "password": "password123"}, follow_redirects=False
    )
    assert r.status_code == 303
    return client
