from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi import FastAPI
from app.database import Base, get_db
from app.api.routers.comms import router
from app.models import ReleasePack


def test_comms_draft_create_and_update():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.dependency_overrides[get_db] = lambda: session
    with TestClient(app) as client:
        created = client.post("/api/comms", json={"kind": "release_notes", "title": "All tenants view", "body": "## Summary\nShip the KPI card."}).json()
        assert created["id"]
        assert created["kind"] == "release_notes"
        assert "KPI" in created["release_notes"]
        updated = client.put(f"/api/comms/{created['id']}", json={"kind": "whatsapp", "title": "WhatsApp ping", "body": "Good morning @all\n\n- KPI card is live"}).json()
        assert updated["kind"] == "whatsapp"
        assert "KPI card is live" in updated["whatsapp"]
        news = client.put(f"/api/comms/{created['id']}", json={"kind": "newsletter", "title": "Fortnightly", "body": "Hey everyone,\n\n## Billing\nUsage table shipped."}).json()
        assert news["kind"] == "newsletter"
        assert "Usage table" in news["newsletter_markdown"]
        assert client.put("/api/comms/999", json={"title": "x", "body": "y"}).status_code == 404
        assert session.query(ReleasePack).count() == 1
    session.close()
    engine.dispose()
