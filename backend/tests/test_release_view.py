import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models import MarketingCampaign, MarketingFeature, ReleaseJob, ReleasePack
from app.services import release_view as view
from app.api.routers.releases import router
from app.api.routers.comms import router as comms_router

SHA = "a" * 40
BRANCH = "release/2026-09-22"


@pytest.fixture
def db(tmp_path, monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    monkeypatch.setattr(view, "ARTIFACT_DIR", tmp_path / "artifacts")
    monkeypatch.setattr(view, "CAMPAIGN_DIR", tmp_path / "marketing")
    monkeypatch.setattr(view, "detect_release_merges", lambda **kw: [dict(branch=BRANCH, sha=SHA, merged_at="2026-09-22", parents=["b" * 40, "c" * 40])])
    yield session
    session.close()
    engine.dispose()


def feature(db, name="Phone rotation", evidence=None, **kwargs):
    row = MarketingFeature(name=name, identity=name, evidence=evidence if evidence is not None else [dict(branch=BRANCH, sha=SHA)], **kwargs)
    db.add(row)
    db.flush()
    return row


def test_joins_release_feature_artifact_and_draft_without_writes(db, tmp_path):
    row = feature(db, decision={"verdict": "approve"})
    pack = ReleasePack(title="Release notes", branch=BRANCH, commit_sha="c" * 12)
    db.add(pack)
    db.flush()
    pdf = tmp_path / "release.pdf"
    pdf.write_bytes(b"pdf")
    job = ReleaseJob(branch=BRANCH, sha=SHA, pack_id=pack.id, status="pending_review", pdf_path=str(pdf), extraction={"features": [{"name": "Phone rotation", "what": "Rotate numbers"}]})
    db.add(job)
    db.add(MarketingCampaign(feature_id=row.id, feature_revision=1, feature_snapshot={"name": row.name, "evidence": row.evidence}, status="completed", assets=[]))
    db.commit()
    statements = []
    def record(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement.split()[0].upper())
    event.listen(db.bind, "before_cursor_execute", record)
    try:
        out = view.release_workspace(db)
    finally:
        event.remove(db.bind, "before_cursor_execute", record)
    assert set(statements) == {"SELECT"}
    release = out["releases"][0]
    assert release["counts"] == {"buyer_facing": 1, "drafts": 1, "artifacts": 1}
    assert release["state"] == "awaiting_review"
    assert release["comms"][0]["state"] == "draft"
    assert release["campaigns"][0]["association"] == "commit"
    assert job.status == "pending_review"
    assert release["jobs"][0]["url"] == f"/comms?release_job={job.id}"


def test_same_name_and_wrong_sha_do_not_link(db):
    feature(db, evidence=[dict(branch=BRANCH, sha="d" * 40)])
    db.add(ReleasePack(title="Phone rotation", branch=BRANCH, commit_sha="e" * 40))
    db.commit()
    out = view.release_workspace(db)
    assert out["releases"][0]["features"] == []
    assert out["releases"][0]["comms"] == []
    assert out["unlinked"]["features"] == out["unlinked"]["comms"] == 1


def test_repeated_branch_does_not_guess_branch_only_records(db, monkeypatch):
    monkeypatch.setattr(view, "detect_release_merges", lambda **kw: [dict(branch=BRANCH, sha=s) for s in [SHA, "d" * 40]])
    db.add(ReleasePack(title="Unpinned draft", branch=BRANCH))
    db.commit()
    out = view.release_workspace(db)
    assert len(out["releases"]) == 2
    assert all(not r["comms"] for r in out["releases"])
    assert out["unlinked"]["comms"] == 1


def test_missing_git_keeps_failed_job_and_does_not_publish(db, monkeypatch):
    monkeypatch.setattr(view, "detect_release_merges", lambda **kw: None)
    pack = ReleasePack(title="Draft")
    db.add(pack)
    db.flush()
    db.add(ReleaseJob(branch=BRANCH, sha=SHA, pack_id=pack.id, status="error:publishing"))
    db.commit()
    out = view.release_workspace(db)
    assert out["warnings"]
    assert out["releases"][0]["state"] == "needs_attention"
    assert out["releases"][0]["comms"][0]["state"] == "draft"
    assert not out["releases"][0]["merge_verified"]


def test_short_sha_deduplicates_and_local_approval_is_not_publication(db):
    pack = ReleasePack(title="Saved locally")
    db.add(pack)
    db.flush()
    db.add(ReleaseJob(branch=BRANCH, sha=SHA[:12], pack_id=pack.id, status="uploaded", drive_file_id="dryrun"))
    db.commit()
    out = view.release_workspace(db)
    assert len(out["releases"]) == 1
    assert out["releases"][0]["comms"][0]["state"] == "approved_locally"


def test_dismissed_and_unassessed_rows_are_not_buyer_facing(db):
    feature(db, status="dismissed", decision={"verdict": "approve"})
    feature(db, name="Needs assessment", decision={})
    db.commit()
    release = view.release_workspace(db)["releases"][0]
    assert len(release["features"]) == 2
    assert release["counts"]["buyer_facing"] == 0


def test_existing_files_audit_and_association_strength(db):
    row = feature(db)
    db.add(MarketingCampaign(feature_id=row.id, feature_revision=1, feature_snapshot={"name": row.name}, assets=[{"filename": "missing.pdf"}, {"filename": "old.pdf", "drive_url": "https://drive.google.com/file/d/old/view"}], status="partial"))
    db.commit()
    view.ARTIFACT_DIR.mkdir()
    (view.ARTIFACT_DIR / "brief.pdf").write_bytes(b"pdf")
    (view.ARTIFACT_DIR / "brief.json").write_text(json.dumps({"branch": BRANCH, "title": "Brief"}))
    audit = view.CAMPAIGN_DIR / "discovery"
    audit.mkdir(parents=True)
    (audit / "scan.json").write_text(json.dumps({"release": BRANCH, "sha": SHA, "assessments": [{"name": "Infrastructure", "decision": {"verdict": "skip", "rationale": "Internal"}}]}))
    (audit / "broken.json").write_text("bad json")
    release = view.release_workspace(db)["releases"][0]
    assert release["assessments"][0]["verdict"] == "skip"
    assert {a["association"] for a in release["artifacts"]} == {"feature", "branch"}
    assert len(release["artifacts"]) == 2
    assert release["state"] == "needs_attention"


def test_artifacts_without_a_local_pdf_link_to_their_drive_copy(db, monkeypatch):
    from app.api.routers import artifacts

    monkeypatch.setattr(artifacts, "ARTIFACT_DIR", view.ARTIFACT_DIR)
    drive = "https://drive.google.com/file/d/abc/view"
    view.ARTIFACT_DIR.mkdir()
    (view.ARTIFACT_DIR / "Local_Brief.pdf").write_bytes(b"pdf")
    (view.ARTIFACT_DIR / "Local_Brief.json").write_text(json.dumps({"branch": BRANCH, "title": "Local"}))
    (view.ARTIFACT_DIR / "Moved_Brief.json").write_text(json.dumps({"branch": BRANCH, "title": "Moved", "url": drive, "file_id": "abc"}))
    (view.ARTIFACT_DIR / "Gone_Brief.json").write_text(json.dumps({"branch": BRANCH, "title": "Gone"}))
    (view.ARTIFACT_DIR / "Moved_Brief.opus.json").write_text(json.dumps({"html": "<p/>"}))

    rows = {row["feature"]: row for row in artifacts.list_artifact_rows()}
    assert set(rows) == {"Local", "Moved"}
    assert rows["Local"]["local"] is True and rows["Local"]["url"] == ""
    assert rows["Moved"]["local"] is False and rows["Moved"]["url"] == drive and rows["Moved"]["pdf_path"] == ""

    feature(db)
    links = {a["name"]: a for a in view.release_workspace(db)["releases"][0]["artifacts"]}
    assert links["Local"]["url"] == "/api/artifacts/files/Local_Brief.pdf"
    assert links["Moved"]["url"] == drive and links["Moved"]["drive_url"] == drive
    assert "Gone" not in links

    app = FastAPI()
    app.include_router(artifacts.router, prefix="/api")
    with TestClient(app) as http:
        assert http.get("/api/artifacts/files/Local_Brief.pdf").content == b"pdf"
        moved = http.get("/api/artifacts/files/Moved_Brief.pdf", follow_redirects=False)
        assert moved.status_code == 307 and moved.headers["location"] == drive
        assert http.get("/api/artifacts/files/Gone_Brief.pdf").status_code == 404


def test_endpoints_and_exact_old_job_lookup(db):
    db.add(ReleaseJob(branch=BRANCH, sha=SHA, status="pending_review"))
    db.commit()
    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.include_router(comms_router, prefix="/api")
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as client:
        assert client.get("/api/releases").status_code == 200
        assert client.get("/api/comms/release-jobs/1").json()["status"] == "pending_review"
        assert client.get("/api/comms/release-jobs/999").status_code == 404
        assert client.post("/api/releases").status_code == 405
