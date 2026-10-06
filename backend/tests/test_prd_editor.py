import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.database import Base, get_db
from app.api.routers import prd, knowledge as library
from app.services import knowledge


@pytest.fixture
def client(tmp_path, monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    monkeypatch.setattr(knowledge, "LIBRARY_DIR", tmp_path)
    monkeypatch.setattr(library, "LIBRARY_DIR", tmp_path)
    app = FastAPI()
    app.include_router(prd.router, prefix="/api")
    app.include_router(library.router, prefix="/api")
    app.dependency_overrides[get_db] = lambda: session
    with TestClient(app) as test_client:
        yield test_client
    session.close()
    engine.dispose()


def test_edit_pdf_snapshot_and_library_filters(client):
    draft = client.post("/api/prd", json={"title": "Daily limits", "markdown": "## Goal\nTwo attempts per day."})
    assert draft.status_code == 200
    row = draft.json()
    path = f"/api/prd/{row['id']}"
    first = client.post(path + "/library").json()
    assert "prd" in first["tags"]
    assert client.get(first["url"]).content.startswith(b"%PDF")
    assert client.post(path + "/library").json()["id"] == first["id"]
    updated = client.put(path, json={"title": "Daily limits revised", "markdown": "## Goal\nThree attempts per day."})
    assert updated.status_code == 200
    assert "Three" in client.get(path).json()["markdown"]
    second = client.post(path + "/library").json()
    assert second["id"] != first["id"]
    assert "Two" in client.get(f"/api/library/documents/{first['id']}").json()["text"]
    assert "Three" in client.get(f"/api/library/documents/{second['id']}").json()["text"]
    client.post("/api/library/documents", files={"file": ("guide.md", b"Guide")})
    client.patch(f"/api/library/documents/{first['id']}", json={"status": "completed"})
    assert client.get("/api/library/documents?kind=prd").json()["total"] == 2
    assert client.get("/api/library/documents?kind=prd&status=completed").json()["total"] == 1
    assert client.get("/api/library/documents?kind=pdf&status=to_read&q=revised").json()["total"] == 1
    assert len(client.get("/api/library/documents?kind=prd&limit=1&offset=1").json()["documents"]) == 1
    assert client.get("/api/library/documents?kind=md").json()["total"] == 1
    pdf = client.get(path + "/pdf")
    assert pdf.status_code == 200
    assert pdf.content.startswith(b"%PDF")


def test_missing_draft_and_validation(client):
    assert client.put("/api/prd/999", json={"title": "Missing", "markdown": "Text"}).status_code == 404
    assert client.post("/api/prd/999/library").status_code == 404
    assert client.post("/api/prd", json={"title": ""}).status_code == 422
