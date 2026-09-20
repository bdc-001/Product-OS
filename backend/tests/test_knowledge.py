from io import BytesIO
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from pypdf import PdfWriter
from app.database import Base
from app.models import DailyNote, CopilotPlan
from app.services import knowledge, roadmap, copilot

@pytest.fixture
def db(tmp_path, monkeypatch):
    engine=create_engine('sqlite://')
    Base.metadata.create_all(engine)
    session=sessionmaker(bind=engine)()
    monkeypatch.setattr(knowledge,'LIBRARY_DIR',tmp_path/'library')
    monkeypatch.setattr(roadmap,'ROADMAP_FILES',tmp_path/'roadmap')
    yield session
    session.close();engine.dispose()

def test_notes_and_documents_are_retrievable(db):
    note=DailyNote(day='2026-09-08',title='Learning',body='Decisions',learning='Workflow orchestration')
    db.add(note);db.commit()
    doc=knowledge.store_document(db,'guide.md',b'# Workflow\nUse idempotent retries.')
    assert doc['indexed']
    assert 'idempotent' in knowledge.context(db,'idempotent retries')[0]['text']
    assert any(e['kind']=='note' for e in knowledge.context(db,'orchestration'))
    with pytest.raises(ValueError):knowledge.store_document(db,'bad.pdf',b'bad')

def test_pdf_storage_and_readability(db):
    buf=BytesIO();writer=PdfWriter();writer.add_blank_page(width=100,height=100);writer.write(buf)
    doc=knowledge.store_document(db,'scan.pdf',buf.getvalue())
    assert not doc['indexed'] and 'OCR' in doc['extraction_note']
    result=roadmap.store_ticket_pdf(original_name='meeting.pdf',data=buf.getvalue())
    assert roadmap.resolve_ticket_pdf(result['id']).read_bytes()==buf.getvalue()
    with pytest.raises(RuntimeError):roadmap.store_ticket_pdf(original_name='bad.pdf',data=b'%PDF-bad')
    with pytest.raises(RuntimeError):roadmap.resolve_ticket_pdf('../meeting.pdf')

def test_conversation_context_isolated(db):
    a=CopilotPlan(prompt='First topic',answer='First answer');b=CopilotPlan(prompt='Other topic',answer='Other answer')
    db.add_all([a,b]);db.commit()
    c=CopilotPlan(prompt='Follow up',answer='Next answer',parent_plan_id=a.id);db.add(c);db.commit()
    assert copilot.conversation_history(db,0)==[]
    assert [r['text'] for r in copilot.conversation_history(db,c.id)]==['First topic','First answer','Follow up','Next answer']

def test_notes_document_http_routes(tmp_path,monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from sqlalchemy.pool import StaticPool
    from app.api.routers.knowledge import router
    from app.database import get_db
    engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
    Base.metadata.create_all(engine);session=sessionmaker(bind=engine)()
    monkeypatch.setattr(knowledge,'LIBRARY_DIR',tmp_path/'library')
    from app.api.routers import knowledge as knowledge_router
    monkeypatch.setattr(knowledge_router,"LIBRARY_DIR",tmp_path/"library")
    app=FastAPI();app.include_router(router,prefix='/api');app.dependency_overrides[get_db]=lambda:session
    with TestClient(app) as client:
        row=client.post('/api/notes',json={'day':'2026-09-08','title':'Daily learning','learning':'Retries'}).json()
        assert client.get('/api/notes?q=Retries').json()['total']==1
        assert client.put(f"/api/notes/{row['id']}",json={'day':'2026-09-08','title':'Updated','learning':'Idempotency'}).status_code==200
        assert client.get(f"/api/notes/{row['id']}").json()['learning']=='Idempotency'
        assert client.post('/api/notes',json={'day':'bad'}).status_code==422
        r=client.post('/api/library/documents',files={'file':('guide.md',b'Reliable retries','text/markdown')})
        assert r.status_code==200
        doc=r.json()
        assert client.get(doc['url']).content==b'Reliable retries'
        assert client.patch(f"/api/library/documents/{doc['id']}",json={'status':'completed'}).json()['status']=='completed'
    session.close();engine.dispose()


def test_note_blocks_filters_and_heuristic_assist():
    blocks=knowledge.blocks_from_legacy("Standup dump\n\nNeed to file a ticket for MCP\n\nWe decided to keep Copilot as the write path", "Retries matter")
    types=[item["type"] for item in blocks]
    assert "paragraph" in types and "learning" in types
    structured=knowledge.heuristic_assist("structure","Standup",blocks,"","")
    assert any(item["type"]=="actionable" for item in structured["blocks"])
    assert any(item["type"]=="decision" for item in structured["blocks"])
    extracted=knowledge.heuristic_assist("extract","Standup",[{"type":"paragraph","text":"Need to follow up with Sourabh"}],"","")
    assert extracted["blocks"][-1]["type"]=="actionable"
    summarized=knowledge.heuristic_assist("summarize","Standup",[{"type":"paragraph","text":"Long meeting about MCP access"}],"","")
    assert summarized["blocks"][0]["type"]=="heading" and summarized["blocks"][0]["text"]=="Summary"


def test_typed_notes_http(tmp_path,monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from sqlalchemy.pool import StaticPool
    from app.api.routers.knowledge import router
    from app.database import get_db
    engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
    Base.metadata.create_all(engine);session=sessionmaker(bind=engine)()
    app=FastAPI();app.include_router(router,prefix='/api');app.dependency_overrides[get_db]=lambda:session
    with TestClient(app) as client:
        row=client.post('/api/notes',json={
            "day":"2026-09-19",
            "title":"MCP scoping",
            "kind":"meeting",
            "blocks":[
                {"type":"heading","text":"Sense MCP"},
                {"type":"actionable","text":"File a read-only MCP spike"},
                {"type":"decision","text":"Copilot remains the Jira write path"},
            ],
        }).json()
        assert "Actionable:" in row["body"]
        assert row["kind"]=="meeting"
        assert row["actionable_count"]==1
        assert client.get('/api/notes?kind=meeting').json()['total']==1
        assert client.get('/api/notes?kind=actionable').json()['total']==1
        assert client.get('/api/notes?kind=decision').json()['total']==1
        assert client.get('/api/notes?kind=learning').json()['total']==0
        assert client.get('/api/notes?day=2026-09-19').json()['total']==1
        assert client.get('/api/notes?day=2026-01-01').json()['total']==0
        assert client.delete(f"/api/notes/{row['id']}").status_code==200
        assert client.get('/api/notes?kind=meeting').json()['total']==0
        assert client.delete(f"/api/notes/{row['id']}").status_code==404
        assist=client.post('/api/notes/assist',json={"action":"extract","title":"MCP scoping","blocks":[{"type":"paragraph","text":"Need to follow up with platform"}]}).json()
        assert any(item["type"]=="actionable" for item in assist["blocks"])
    session.close();engine.dispose()
