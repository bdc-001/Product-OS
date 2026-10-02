from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import DailyNote, Prototype, PrototypeFile, ReleasePack
from app.repositories.issues import apply_normalized


def _session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, future=True)(), engine


def test_list_issues_paginates_in_sql_without_descriptions():
    from app.api.routers.issues import list_issues

    db, engine = _session()
    for i in range(3):
        apply_normalized(
            None,
            {
                "issue_key": f"AC-{i + 1}",
                "summary": f"Ticket {i}",
                "status": "To Do",
                "issue_type": "Task",
                "description": "long secret",
                "comments_json": [],
                "changelog_json": [],
                "extra_json": {},
            },
            db,
        )
    apply_normalized(
        None,
        {
            "issue_key": "PS-1",
            "summary": "Support",
            "status": "To Do",
            "issue_type": "Bug",
            "description": "other",
            "comments_json": [],
            "changelog_json": [],
            "extra_json": {},
        },
        db,
    )
    db.commit()
    page = list_issues(board="AC", compact=True, limit=2, db=db)
    assert page["total"] == 3
    assert len(page["issues"]) == 2
    assert "description" not in page["issues"][0]
    db.close()
    engine.dispose()


def test_notes_list_is_compact_and_detail_keeps_blocks():
    from app.api.routers.knowledge import notes as list_notes, note as note_detail

    db, engine = _session()
    row = DailyNote(
        day="2026-09-20",
        title="Standup",
        body="Ship the preview",
        learning="",
        kind="meeting",
        blocks=[{"id": "a", "type": "paragraph", "text": "Ship the preview"}],
        tags=[],
    )
    db.add(row)
    db.commit()
    listed = list_notes(db=db)
    assert listed["total"] == 1
    assert listed["notes"][0]["blocks"] == []
    assert listed["notes"][0]["body"] == ""
    assert "Ship" in listed["notes"][0]["preview"]
    detail = note_detail(row.id, db=db)
    assert detail["blocks"][0]["text"] == "Ship the preview"
    db.close()
    engine.dispose()


def test_comms_list_omits_bodies():
    from app.services.comms import list_packs, pack_out

    db, engine = _session()
    row = ReleasePack(
        kind="release_notes",
        title="KPI card",
        release_notes="## Summary\nShip the KPI card to clients.",
        internal_update="",
        newsletter={},
    )
    db.add(row)
    db.commit()
    listed = list_packs(db)
    assert listed[0]["release_notes"] == ""
    assert "KPI" in listed[0]["preview"]
    full = pack_out(row)
    assert "KPI" in full["release_notes"]
    db.close()
    engine.dispose()


def test_snapshot_out_can_skip_live_git(monkeypatch):
    from app.services import codebase as codebase_svc
    from app.models import CodebaseSnapshot

    db, engine = _session()
    snap = CodebaseSnapshot(branch="release/2026-09-20", commit_sha="abc1234", module_count=0)
    db.add(snap)
    db.commit()

    def boom(*_a, **_k):
        raise AssertionError("git_status should not run")

    monkeypatch.setattr(codebase_svc, "git_status", boom)
    out = codebase_svc.snapshot_out(db, snap, live=False, include_modules=False)
    assert out["indexed_branch"] == "release/2026-09-20"
    assert out["modules"] == []
    db.close()
    engine.dispose()


def test_parse_short_status_reads_ahead_behind():
    from app.services.codebase import _parse_short_status

    branch, ahead, behind, dirty = _parse_short_status("## main...origin/main [ahead 1, behind 2]\n M file.py\n")
    assert (branch, ahead, behind, dirty) == ("main", 1, 2, True)


def test_link_node_modules_repairs_broken_symlink(tmp_path):
    from app.services import prototype_lovable as kit

    dest = tmp_path / "proto"
    dest.mkdir()
    broken = dest / "node_modules"
    broken.symlink_to(tmp_path / "missing")
    (tmp_path / "kit" / "node_modules" / "vite").mkdir(parents=True)
    monkey_root = tmp_path / "kit"
    original = kit.KIT_ROOT
    kit.KIT_ROOT = monkey_root
    try:
        link = kit.link_node_modules(dest)
        assert (link / "vite").exists()
    finally:
        kit.KIT_ROOT = original


def test_ensure_preview_drops_ci_and_uses_local_vite(tmp_path, monkeypatch):
    from app.services import prototype_runtime as rt
    from app.services import prototype_lovable as kit_mod

    kit = tmp_path / "kit"
    proto = tmp_path / "proto"
    bin_dir = kit / "node_modules" / ".bin"
    bin_dir.mkdir(parents=True)
    (kit / "node_modules" / "vite").mkdir()
    vite_bin = bin_dir / "vite"
    vite_bin.write_text("#!/bin/sh\n")
    vite_bin.chmod(0o755)
    proto.mkdir()
    (proto / "package.json").write_text("{}")
    captured = {}

    class FakeProc:
        def __init__(self, cmd, cwd=None, env=None, **_k):
            captured["cmd"] = cmd
            captured["env"] = env
            captured["cwd"] = cwd
            self.pid = 4242

        def poll(self):
            return None

        def terminate(self):
            return None

        def kill(self):
            return None

    monkeypatch.setattr(kit_mod, "KIT_ROOT", kit)
    monkeypatch.setattr(rt, "ensure_kit_install", lambda: "")
    monkeypatch.setattr(rt, "_port_open", lambda _p: False)
    monkeypatch.setattr(rt, "_http_ok", lambda _u: True)
    monkeypatch.setattr(rt.subprocess, "Popen", FakeProc)
    url, err = rt.ensure_preview(proto, 2)
    assert err == rt.PREVIEW_STARTING
    assert url == ""
    assert "CI" not in (captured.get("env") or {})
    assert Path(captured["cmd"][0]).name == "vite"


def test_get_prototype_can_omit_file_bodies():
    from app.api.routers.prototypes import get_prototype

    db, engine = _session()
    row = Prototype(title="Voice", status="ready")
    db.add(row)
    db.flush()
    db.add(PrototypeFile(prototype_id=row.id, path="src/App.jsx", content="export default function App() { return null }"))
    db.commit()
    slim = get_prototype(row.id, files=False, db=db)
    assert slim["files"] == []
    assert slim["file_count"] == 1
    full = get_prototype(row.id, files=True, db=db)
    assert full["files"][0]["content"].startswith("export")
    db.close()
    engine.dispose()


def test_preview_ready_url_skips_spawn_when_port_is_open(monkeypatch):
    from app.services import prototype_runtime as rt

    monkeypatch.setattr(rt, "_port_open", lambda _p: True)
    assert rt.preview_ready_url(2).startswith("http://127.0.0.1:")
