import uuid

import pytest
from fastapi.testclient import TestClient

from app import context
from app.connections import store
from app.database import SessionLocal
from app.models import AvatarVideo
from app.storage import WorkspaceDir
from app.tenancy import TenancyError
from app.workspaces import create_workspace


def _ctx(workspace_id: int, slug: str) -> context.WorkspaceContext:
    return context.WorkspaceContext(id=workspace_id, slug=slug, name=slug, role="owner")


@pytest.fixture
def pair():
    with context.system():
        db = SessionLocal()
        try:
            alpha = create_workspace(db, f"Alpha {uuid.uuid4().hex[:6]}")
            beta = create_workspace(db, f"Beta {uuid.uuid4().hex[:6]}")
            db.commit()
            return _ctx(alpha.id, alpha.slug), _ctx(beta.id, beta.slug)
        finally:
            db.close()


def _video(title: str) -> AvatarVideo:
    return AvatarVideo(title=title, status="draft", options={}, result={}, assets=[])


def test_queries_and_lookups_only_see_the_active_workspace(pair):
    alpha, beta = pair
    db = SessionLocal()
    try:
        with context.use(alpha):
            db.add(_video("alpha only"))
            db.commit()
        with context.use(beta):
            row = _video("beta only")
            db.add(row)
            db.commit()
            beta_id = row.id
    finally:
        db.close()

    fresh = SessionLocal()
    try:
        with context.use(alpha):
            titles = {video.title for video in fresh.query(AvatarVideo).all()}
            assert "alpha only" in titles and "beta only" not in titles
            assert fresh.get(AvatarVideo, beta_id) is None
    finally:
        fresh.close()


def test_scoped_query_without_a_workspace_is_refused():
    db = SessionLocal()
    try:
        with context.use(None), pytest.raises(TenancyError):
            db.query(AvatarVideo).all()
    finally:
        db.close()


def test_connections_and_secrets_stay_in_their_workspace(pair):
    alpha, beta = pair
    db = SessionLocal()
    try:
        with context.use(alpha):
            store.save_connection(db, "heygen", {"api_key": "sk-alpha-only-secret"})
            db.commit()
            row = store.get_connection(db, "heygen")
            assert row is not None
            assert "sk-alpha-only-secret" not in (row.secrets or "")
            assert store.read_secrets(db, row).get("api_key") == "sk-alpha-only-secret"
        with context.use(beta):
            assert store.get_connection(db, "heygen") is None
            assert all(item.provider != "heygen" for item in store.list_connections(db))
    finally:
        db.close()


def test_workspace_files_resolve_to_separate_folders(pair):
    alpha, beta = pair
    folder = WorkspaceDir("marketing", "avatar")
    with context.use(alpha):
        alpha_path = folder.path()
    with context.use(beta):
        beta_path = folder.path()
    assert alpha_path != beta_path
    assert alpha.slug in str(alpha_path) and beta.slug in str(beta_path)


def test_api_cannot_read_or_change_another_workspace_rows(pair):
    alpha, beta = pair
    from app.main import app

    with context.system():
        client = TestClient(app)
        created = client.post("/api/avatar-videos", json={"title": "alpha api"}, headers={"X-Workspace": alpha.slug})
        assert created.status_code == 201, created.text
        video_id = created.json()["id"]

        listed = client.get("/api/avatar-videos", headers={"X-Workspace": beta.slug})
        assert listed.status_code == 200
        assert all(video["id"] != video_id for video in listed.json()["videos"])
        assert client.put(f"/api/avatar-videos/{video_id}", json={"title": "taken"}, headers={"X-Workspace": beta.slug}).status_code == 404
        assert client.delete(f"/api/avatar-videos/{video_id}", headers={"X-Workspace": beta.slug}).status_code == 404

        mine = client.get("/api/avatar-videos", headers={"X-Workspace": alpha.slug}).json()["videos"]
        assert any(video["id"] == video_id and video["title"] == "alpha api" for video in mine)
