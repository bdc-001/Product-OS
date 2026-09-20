from io import BytesIO
import zipfile

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.services import prototype as proto


def test_sanitize_path_allowlist():
    assert proto.sanitize_path("pages/Foo.jsx") == "src/pages/Foo.jsx"
    assert proto.sanitize_path("src/App.jsx") == "src/App.jsx"
    assert proto.sanitize_path("src/features/campaigns/CampaignsListPage.tsx") == "src/features/campaigns/CampaignsListPage.tsx"
    assert proto.sanitize_path("package.json") == "package.json"
    assert proto.sanitize_path("index.html") == "index.html"
    assert proto.sanitize_path("convin-activate/static/src/components/Bar.jsx") == "src/components/Bar.jsx"
    for bad in ("../.env", "src/pages/../../etc/passwd", "node_modules/x.js", "src/secret.key", "backend/main.go"):
        try:
            proto.sanitize_path(bad)
            raise AssertionError(bad)
        except proto.PrototypePathError:
            pass


def test_merge_heuristic_and_zip(tmp_path, monkeypatch):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    monkeypatch.setattr(proto, "PROTO_DIR", tmp_path / "prototypes")
    row = proto.seed_prototype(db, title="Billing", prompt="billing history")
    paths = {f["path"] for f in proto.prototype_out(row, db, detail=True)["files"]}
    assert "src/features/campaigns/CampaignsListPage.tsx" in paths
    assert "src/pages/Campaigns.jsx" in paths
    assert "src/pages/AgentManagement.jsx" in paths
    assert "src/pages/Tools.jsx" in paths
    assert "src/pages/KnowledgeBase.jsx" in paths
    assert "src/pages/AgentWorkspace.jsx" in paths
    assert "src/App.jsx" in paths
    assert "src/lib/nav.ts" in paths
    assert "index.html" in paths
    assert "src/features/agents/AgentsListPage.tsx" in paths
    assert "src/features/agents/AgentWizardPage.tsx" in paths
    assert "src/features/analytics/AnalyticsPage.tsx" in paths
    assert "src/features/customers/CustomersPage.tsx" in paths
    assert "src/components/layout/AppSidebar.tsx" in paths
    assert "src/components/filters/FilterBar.tsx" in paths
    shell = next(f["content"] for f in proto.prototype_out(row, db, detail=True)["files"] if f["path"] == "src/components/layout/AppSidebar.tsx")
    assert "Main" in shell and "Human" in shell and "AI Agents" in shell
    assert "Human Agent" in shell
    assert "agent-workspace" in shell
    assert "sense-logo.svg" in shell
    app = next(f["content"] for f in proto.prototype_out(row, db, detail=True)["files"] if f["path"] == "src/App.jsx")
    assert "/tenant/:tenantId" in app
    assert "react-router-dom" in app
    campaigns = next(f["content"] for f in proto.prototype_out(row, db, detail=True)["files"] if f["path"] == "src/features/campaigns/CampaignsListPage.tsx")
    assert "Create Campaign" in campaigns
    assert "react-router-dom" in campaigns
    assert "@tanstack/react-router" not in campaigns
    blob = proto.export_zip(db, row.id)
    names = zipfile.ZipFile(BytesIO(blob)).namelist()
    assert "README.md" in names
    assert "PORTING.md" in names
    assert any(n.endswith("Campaigns.jsx") for n in names)
    db.close()
    engine.dispose()


def test_run_turn_heuristic_without_llm(tmp_path, monkeypatch):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    monkeypatch.setattr(proto, "PROTO_DIR", tmp_path / "prototypes")

    def boom(*_a, **_k):
        from app.clients.llm import LLMJsonError
        raise LLMJsonError("down")

    monkeypatch.setattr(proto, "chat_json", boom)
    monkeypatch.setattr(proto, "sense_kit_context", lambda prompt="": "")
    row = proto.seed_prototype(db, title="Start")
    result = proto.run_turn(db, row.id, "Show campaign list with a create button")
    assert result["ok"]
    assert result["llm_used"] is False
    db.refresh(row)
    assert row.status == "ready"
    detail = proto.prototype_out(row, db, detail=True)
    assert len(detail["messages"]) >= 2
    assert any(f["path"] == "src/features/campaigns/CampaignsListPage.tsx" for f in detail["files"])
    db.close()
    engine.dispose()


def test_put_file_rejects_escape(tmp_path, monkeypatch):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    monkeypatch.setattr(proto, "PROTO_DIR", tmp_path / "prototypes")
    row = proto.seed_prototype(db)
    try:
        proto.put_file(db, row.id, "../.env", "x")
        raise AssertionError("should reject")
    except proto.PrototypePathError:
        pass
    updated = proto.put_file(db, row.id, "src/pages/Extra.jsx", "export default function Extra(){return null}")
    assert any(f["path"] == "src/pages/Extra.jsx" for f in updated["files"])
    db.close()
    engine.dispose()


def test_run_turn_sets_error_status(tmp_path, monkeypatch):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    monkeypatch.setattr(proto, "PROTO_DIR", tmp_path / "prototypes")
    monkeypatch.setattr(proto, "sense_kit_context", lambda prompt="": "")
    monkeypatch.setattr(
        proto,
        "chat_json",
        lambda *_a, **_k: {"title": "x", "notes": "", "files": [{"path": "src/App.jsx", "content": "x"}]},
    )
    row = proto.seed_prototype(db, title="Start")

    def boom(*_a, **_k):
        raise RuntimeError("disk full")

    monkeypatch.setattr(proto, "_merge_files", boom)
    try:
        proto.run_turn(db, row.id, "Show a table")
        raise AssertionError("should raise")
    except RuntimeError:
        pass
    db.refresh(row)
    assert row.status == "error"
    assert "disk full" in (row.error or "")
    db.close()
    engine.dispose()


def test_preview_html_runs_sense_shell(tmp_path, monkeypatch):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    monkeypatch.setattr(proto, "PROTO_DIR", tmp_path / "prototypes")
    monkeypatch.setattr(proto, "ensure_preview", lambda *_a, **_k: ("http://127.0.0.1:41701/", ""))
    row = proto.seed_prototype(db, title="Campaigns")
    html = proto.preview_html(db, row.id)
    assert "http://127.0.0.1:41701/" in html
    assert "iframe" in html
    assert "text/babel" not in html
    db.close()
    engine.dispose()


def test_target_component_is_complete_and_imports_are_followed():
    from app.models import Prototype, PrototypeFile
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    row = Prototype(title='Sense', status='ready')
    db.add(row); db.flush()
    long_source = "import {RetryControl} from './RetryControl';\n" + '// existing behavior\n' * 600 + 'export const RetrySettings = RetryControl;'
    for path, content in [('src/features/settings/RetrySettings.tsx', long_source),
                          ('src/features/settings/RetryControl.tsx', 'export const RetryControl = () => null;'),
                          ('src/App.jsx', 'export default function App(){return null}')]:
        db.add(PrototypeFile(prototype_id=row.id, path=path, content=content))
    db.flush()
    context = proto._turn_files(db, row.id, 'Change the RetrySettings daily limit')
    files = {f['path']: f['content'] for f in context if 'path' in f}
    assert files['src/features/settings/RetrySettings.tsx'] == long_source
    assert 'src/features/settings/RetryControl.tsx' in files
    db.close(); engine.dispose()


def test_exact_edits_preserve_unrelated_code_and_reject_ambiguous_or_unseen_changes():
    import pytest
    current = [{'path': 'src/App.jsx', 'content': 'const limit = 2;\nconst earlierChange = true;\n'}]
    result = proto._generated_files({'edits': [{'path': 'src/App.jsx', 'old': 'const limit = 2;', 'new': 'const limit = 3;'}]}, current)
    assert result[0]['content'] == 'const limit = 3;\nconst earlierChange = true;\n'
    for edits in [
        [{'path': 'src/App.jsx', 'old': 'const ', 'new': 'let '}],
        [{'path': 'src/Unseen.jsx', 'old': 'old', 'new': 'new'}],
        [{'path': 'src/App.jsx', 'old': 'const limit = 2;', 'new': 'const limit = 3;'}, {'path': 'src/App.jsx', 'old': 'absent', 'new': ''}],
    ]:
        with pytest.raises(ValueError):
            proto._generated_files({'edits': edits}, current)
        assert current[0]['content'].startswith('const limit = 2;')


def test_model_can_fetch_missing_source_before_an_exact_edit(tmp_path, monkeypatch):
    from app.models import Prototype, PrototypeFile
    engine = create_engine('sqlite://'); Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    row = Prototype(title='Sense', status='ready'); db.add(row); db.flush()
    for path, content in [('src/App.jsx', 'shell'), ('src/features/Other.tsx', 'const limit = 2;')]:
        db.add(PrototypeFile(prototype_id=row.id, path=path, content=content))
    db.commit()
    monkeypatch.setattr(proto, '_turn_files', lambda *a: [{'tree': 'src/App.jsx\nsrc/features/Other.tsx'}, {'path': 'src/App.jsx', 'content': 'shell'}])
    monkeypatch.setattr(proto, '_write_disk', lambda *a: None)
    calls = []
    def reply(surface, system, payload, **kwargs):
        calls.append(payload)
        assert kwargs['max_chars'] >= len(__import__('json').dumps(payload))
        if len(calls) == 1:
            return {'read_paths': ['src/features/Other.tsx']}
        assert any(f.get('content') == 'const limit = 2;' for f in payload['current_files'])
        return {'notes': 'Set the limit to three.', 'edits': [{'path': 'src/features/Other.tsx', 'old': 'const limit = 2;', 'new': 'const limit = 3;'}]}
    monkeypatch.setattr(proto, 'chat_json', reply)
    result = proto.run_turn(db, row.id, 'Set the limit to three', target='Settings')
    assert result['files'] == ['src/features/Other.tsx']
    assert calls[-1]['target'] == 'Settings'
    assert db.query(PrototypeFile).filter(PrototypeFile.path == 'src/features/Other.tsx').one().content == 'const limit = 3;'
    db.close(); engine.dispose()


def test_generation_preserves_manual_edit_made_during_model_call(monkeypatch):
    import pytest
    from app.models import Prototype, PrototypeFile
    engine = create_engine('sqlite://'); Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    row = Prototype(title='Sense',status='ready');db.add(row);db.flush()
    db.add(PrototypeFile(prototype_id=row.id,path='src/App.jsx',content='const limit = 2;'))
    db.commit()
    def reply(*a,**kw):
        file=db.query(PrototypeFile).filter(PrototypeFile.path=='src/App.jsx').one()
        file.content='const limit = 7;';db.commit()
        return {'edits':[{'path':'src/App.jsx','old':'const limit = 2;','new':'const limit = 3;'}]}
    monkeypatch.setattr(proto,'chat_json',reply)
    with pytest.raises(ValueError,match='manual changes are preserved'):
        proto.run_turn(db,row.id,'Set the limit to three')
    assert db.query(PrototypeFile).one().content=='const limit = 7;'
    db.close();engine.dispose()


def test_prd_from_prototype_without_codebase(tmp_path, monkeypatch):
    from app.models import Prd
    from app.services import copilot as copilot_mod
    from app.services import prd as prd_mod

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    monkeypatch.setattr(proto, "PROTO_DIR", tmp_path / "prototypes")
    class FakeLLM:
        configured = False
        def __init__(self, *a, **k):
            pass
    monkeypatch.setattr(prd_mod, "LLMClient", FakeLLM)
    monkeypatch.setattr(copilot_mod, "LLMClient", FakeLLM)
    monkeypatch.setattr(prd_mod, "latest_snapshot", lambda _db: None)
    monkeypatch.setattr(prd_mod, "retrieve_modules", lambda *_a, **_k: [])
    monkeypatch.setattr(prd_mod, "grep_codebase", lambda *_a, **_k: [])
    row = proto.seed_prototype(db, title="Campaign retry")
    pack = proto.prototype_pack(db, row.id, "campaign")
    assert pack["id"] == row.id
    assert pack["files"]
    out = prd_mod.generate_prd(db, title="", problem="Daily attempt limit 1–10", prototype_id=row.id)
    assert any(item.get("type") == "prototype" for item in out["sources"])
    assert out["markdown"]
    plan = copilot_mod.plan_copilot(db, prompt="Write a PRD from this prototype", prototype_ids=[row.id])
    assert "Saved PRD" in plan["answer"]
    assert db.query(Prd).count() == 2
    db.close()
    engine.dispose()
