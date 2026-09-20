from pathlib import Path
import json
from types import SimpleNamespace

import fitz
import pytest

from app.services import marketing_quality as quality, marketing_manager as manager


@pytest.fixture(autouse=True)
def no_live_calls(monkeypatch):
    monkeypatch.setattr(quality, 'chat_json', lambda *a, **k: pytest.fail('Mock visual provider explicitly'))


def pdf(path, pages=1):
    with fitz.open() as doc:
        for index in range(pages):
            page=doc.new_page()
            page.insert_text((50,70), f'Agent Testing: session review {index+1}')
        doc.save(path)


def visual_review(**changes):
    return dict(passed=True, issues=[], legibility=5, hierarchy=4, visual_usefulness=4,
        rationale='The pages show a readable, unclipped explanation with clear hierarchy and useful feature detail.', **changes)


def test_visual_review_covers_every_page_and_reuses_identical_output(tmp_path, monkeypatch):
    pdf(tmp_path/'brief.pdf',7)
    calls=[]
    def review(*a, **k):
        calls.append(k['images'])
        return visual_review()
    monkeypatch.setattr(quality, 'chat_json', review)
    args=('feature_brief',{'title':'Agent Testing'},tmp_path,[('brief.pdf','application/pdf')])
    quality.review_rendered(*args)
    assert [len(images) for images in calls] == [8,3]
    report=json.loads((tmp_path/'feature_brief-visual-review.json').read_text())
    assert report['reviewed_images']==7 and report['passed']
    quality.review_rendered(*args)
    assert len(calls)==2
    (tmp_path/'brief.pdf').unlink()
    pdf(tmp_path/'brief.pdf',1)
    quality.review_rendered(*args)
    assert len(calls)==3


def test_visual_defect_cannot_be_marked_deliverable(tmp_path, monkeypatch):
    pdf(tmp_path/'brief.pdf')
    monkeypatch.setattr(quality, 'chat_json', lambda *a, **k: {
        **visual_review(), 'issues':['Page 1 headline overlaps its body.'], 'passed':False})
    with pytest.raises(ValueError,match='overlaps'):
        quality.review_rendered('feature_brief',{'title':'Agent Testing'},tmp_path,[('brief.pdf','application/pdf')])
    assert not (tmp_path/'feature_brief-visual-review.json').exists()
    assert json.loads((tmp_path/'qa/feature_brief/review.json').read_text())['passed'] is False


def test_source_research_reads_actual_implementation_at_original_sha(monkeypatch):
    sha='a'*40
    body='function startTestCall() {\n  const prompt = savedDraft || publishedPrompt;\n}\n' * 4
    calls=[]
    monkeypatch.setattr('app.services.codebase.latest_snapshot',lambda db: SimpleNamespace(branch='release/2026-09-04'))
    monkeypatch.setattr('app.services.codebase._git',lambda root,*args,**kwargs: calls.append(args) or SimpleNamespace(returncode=0,stdout=body))
    brief={'name':'Agent Testing','source':'mastersheet','description':'Try a real test call before publishing.',
           'source_context':{'sha':sha,'hits':[{'path':'convin-activate/static/src/agent-testing/TestCall.tsx','text':'}'},
                                             {'path':'convin-activate/docs/plan.md','text':'planned behavior'}]}}
    researched=manager.research_feature(None,brief)
    assert researched['source_context']['hits'][0]['text']==body.rstrip('\n')
    assert len(researched['source_context']['hits'])==1
    assert calls[0][1].startswith(sha+':')
    assert researched['research_version']==3
