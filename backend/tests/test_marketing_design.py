import pytest

from app.services import marketing_design as design


def test_embedded_design_strips_page_scripts_and_remote_fonts():
    source='''<html><head><link href="https://fonts.example/font.css"><style>@import url(https://fonts.example/a);</style></head>
    <body><script>alert(1)</script><div onclick="alert(1)"><img src="{{brand_on_dark}}">Approved text</div></body></html>'''
    result=design.prepare_design(source)
    assert '<script' not in result and 'onclick=' not in result
    assert '<link' not in result and '@import' not in result
    assert 'data:image/svg+xml;base64,' in result
    assert 'font/ttf' not in result  # Do not send embedded font binaries back to designers.
    printed=design.prepare_design(result,embed_fonts=True)
    assert printed.count('data-marketing-fonts')==1
    assert design.prepare_design(printed,embed_fonts=True).count('data-marketing-fonts')==1


def test_external_media_cannot_enter_designed_artifacts():
    with pytest.raises(ValueError,match='self-contained'):
        design.prepare_design('<html><head></head><body><img src="https://example.com/unapproved.png"></body></html>')


def test_approved_display_copy_excludes_internal_evidence_and_upload_caption():
    content={'title':'Agent Testing','body':'Separate upload caption','slides':[
        {'headline':'Test the conversation','body':'Examine the actual test session.',
         'points':['Choose a scenario','Inspect the result'],'evidence':'Internal source excerpt'}]}
    assert design.approved_text('linkedin_carousel',content)==[
        'Test the conversation','Examine the actual test session.','Choose a scenario','Inspect the result']


def _onepager(**overrides):
    return {'product': 'Analytics', 'feature': 'Channel Breakdown',
        'positioning': {'problem': 'Reviews start from one blended total, so nobody knows which channel moved.',
                        'buyer': 'Heads of campaign operations; used by campaign managers.',
                        'why_pay': 'Budget goes to the channel that works instead of being spread on guesswork.'},
        'title': 'See which channel carries each campaign',
        'dek': 'Channel Breakdown splits every campaign result by channel, so reviews start from the channel that moved.',
        'audience': 'Campaign managers who review outbound campaigns',
        'problem': {'heading': 'One total hides the channel that moved', 'text': 'A campaign total shows how much happened, not which channel did the work.'},
        'solution': {'heading': 'Every result, split by channel', 'text': 'Read calling, WhatsApp, SMS and email side by side for the same period.'},
        'visuals': [{'kind': 'diagram', 'heading': 'How a channel review runs', 'diagram': {'kind': 'flow', 'nodes': [
            {'label': 'Open the campaign', 'text': 'Pick the campaign under review.'},
            {'label': 'Read by channel', 'text': 'Compare channels in the same window.'},
            {'label': 'Carry one question', 'text': 'Bring that difference into the review.'}]}}],
        'value': [{'icon': 'layers', 'title': 'Spot the channel that dips', 'text': 'Each channel keeps its own row.'},
                  {'icon': 'filter', 'title': 'Filters that carry over', 'text': 'Uses the period and conditions you applied.'},
                  {'icon': 'chart', 'title': 'Totals that reconcile', 'text': 'Channel rows add up to the campaign total.'}],
        'cta': 'Ask your Acme team for a walkthrough.', **overrides}


def test_one_pager_approved_copy_excludes_internal_evidence():
    content = _onepager(review={'evidence': 'Internal source excerpt'}, body='Separate Markdown export')
    texts = design.approved_text('feature_brief', content)
    assert texts[:3] == ['Analytics', 'Channel Breakdown', 'See which channel carries each campaign']
    assert 'Bring that difference into the review.' in texts and 'Channel rows add up to the campaign total.' in texts
    assert texts[-1] == 'Ask your Acme team for a walkthrough.'
    assert 'Internal source excerpt' not in texts and 'Separate Markdown export' not in texts
    assert not any('guesswork' in text for text in texts)


def test_one_pager_split_diagram_separates_sides_without_an_arrow():
    from app.services.marketing_onepager import onepager_html
    split = {'kind': 'diagram', 'heading': 'Drafts tested, live calls untouched', 'diagram': {'kind': 'split', 'nodes': [
        {'label': 'Test sessions', 'text': 'Run the draft prompt.'},
        {'label': 'Live campaigns', 'text': 'Keep the published prompt.'}]}}
    page = onepager_html(_onepager(visuals=[split]))
    assert 'link apart' in page and 'M13 6l6 6-6 6' not in page
    flow = _onepager()['visuals'][0]
    assert 'M13 6l6 6-6 6' in onepager_html(_onepager(visuals=[flow, split]))


def test_one_pager_lone_flow_reads_as_numbered_steps():
    from app.services.marketing_onepager import onepager_html
    page = onepager_html(_onepager())
    assert 'class="dia rows"' in page and '<b>3</b><strong>Carry one question</strong>' in page
    assert page.count('class="node last"') == 1 and 'M13 6l6 6-6 6' not in page


def test_carousel_boards_use_a_filled_phone_grid():
    from app.services.marketing_layouts import carousel_html
    html = carousel_html({"slides": [
        {"layout": "hook", "visual": "statement", "headline": "See why an agent misses outcomes",
         "body": "Improve an AI voice agent from its own recent calls.", "points": []},
        {"layout": "steps", "visual": "steps", "headline": "Open Agent Monitoring on one agent",
         "body": "Review past runs, then start a new one.", "points": ["Open agent", "Review past runs", "Start a run"]},
    ]})
    assert "1080px" in html and "1350px" in html
    assert html.count('class="page') == 2
    assert 'class="visual"' in html
    assert "Open agent" in html
    assert 'feature_brief' not in design.FORMAT_DESIGN
    assert 'stacked text cards' in design.FORMAT_DESIGN['linkedin_carousel']
    assert 'Exactly two A4 pages' in design.FORMAT_DESIGN['article']


def test_design_uses_artifact_references_polish_and_saved_layout(tmp_path, monkeypatch):
    calls=[]
    monkeypatch.setattr(design,'_design_ref_blocks',lambda:[{'name':'design_ref_1','role':'Approved artifact craft','data':'AAAA'}])
    def chat(surface,prompt,payload,**kwargs):
        calls.append((surface,prompt,payload,kwargs))
        return {'html':'<html><head></head><body><section class="page">Approved text</section></body></html>'}
    monkeypatch.setattr(design,'chat_json',chat)
    renders=[]
    monkeypatch.setattr(design,'render_design',lambda *args,**kwargs:renders.append(kwargs))
    content={'title':'Agent Testing','body':'Approved text'}
    first=design.compose_design('feature_image',content,tmp_path)
    assert [c[0] for c in calls]==['marketing_design','marketing_design_polish']
    assert calls[0][3]['images'][0]['name']=='design_ref_1'
    assert 'full-bleed navy masthead' in calls[0][1]
    assert renders==[{'export':False}, {'export':False}]  # Preflight then polished layout.
    assert design.compose_design('feature_image',content,tmp_path)==first
    assert len(calls)==2


def test_copy_comparison_allows_typography_but_not_changed_claims():
    assert design.normalized_copy("FREE PLAN\n  ﬁndings") == design.normalized_copy("Free plan findings")
    assert design.normalized_copy("Paid plan") != design.normalized_copy("Free plan")


def test_layout_repair_returns_to_designer_without_rewriting_approved_copy(tmp_path,monkeypatch):
    monkeypatch.setattr(design,'_design_ref_blocks',lambda:[{'name':'ref','role':'layout','data':'AAAA'}])
    requests=[]
    def chat(surface,prompt,payload,**kwargs):
        requests.append(payload)
        return {'html':'<html><head></head><body><section class="page">Approved text</section></body></html>'}
    monkeypatch.setattr(design,'chat_json',chat)
    def render(*args,**kwargs):
        if len(requests)==2:raise ValueError('Page 1 clips a heading.')
    monkeypatch.setattr(design,'render_design',render)
    design.compose_design('feature_image',{'title':'Agent Testing','body':'Approved text'},tmp_path)
    assert requests[-1]['repair']=='Page 1 clips a heading.'


def _brief():
    return {'title': 'Read a campaign channel by channel', 'dek': 'See which channel deserves a closer look.',
        'stats': [{'value': '1 view', 'label': 'Every channel in the campaign'}],
        'blocks': [{'kind': 'why', 'heading': 'Why you need this', 'risk': 'One total hides the channel that needs attention.',
            'items': [{'lead': 'A specific start', 'text': 'Open the breakdown and see which channel differs.'},
                      {'lead': 'A useful question', 'text': 'Bring the observed difference into your campaign review.'}]},
                   {'kind':'flow','heading':'Review the campaign','items':[
                       {'lead':'Open the campaign','text':'Choose a campaign whose channel results you want to understand.'},
                       {'lead':'Compare channels','text':'Read the results in the same time window before drawing conclusions.'},
                       {'lead':'Investigate differences','text':'Audience and timing may explain a gap; the breakdown alone does not establish causation.'}]}],
        'cta': 'Open a recent campaign.', 'body': 'Approved words'}


def test_two_pager_requires_full_reference_composition_and_polish(tmp_path, monkeypatch):
    key = 'article'
    content = _brief()
    calls = []
    monkeypatch.setattr(design, '_design_ref_blocks', lambda: [{'name':'ref','role':'craft','data':'AAAA'}])
    monkeypatch.setattr(design, 'render_design', lambda *a, **k: [])
    def compose(surface, prompt, payload, **kwargs):
        calls.append((surface, payload, kwargs))
        return {'html': '<html><head></head><body>Approved composition</body></html>'}
    monkeypatch.setattr(design, 'chat_json', compose)
    design.compose_design(key, content, tmp_path)
    assert [call[0] for call in calls] == ['marketing_design', 'marketing_design_polish']
    assert [call[2]['reasoning_effort'] for call in calls] == ['xhigh', 'high']
    assert all(call[2]['images'][0]['name'] == 'ref' for call in calls)
    assert calls[0][1]['approved_copy'] == content


def test_rejected_legacy_layout_is_not_resumed(tmp_path, monkeypatch):
    from app.services import marketing_quality
    legacy = tmp_path / 'design' / 'article' / 'legacy'
    legacy.mkdir(parents=True)
    (legacy / 'approved.html').write_text('Rejected generic seed')
    calls = []
    monkeypatch.setattr(design, 'compose_design', lambda *a, **kw: calls.append('compose') or 'New composition')
    monkeypatch.setattr(design, 'render_design', lambda key, content, source, *a, **kw: calls.append(source) or [])
    monkeypatch.setattr(marketing_quality, 'review_rendered', lambda *a: [])
    design.render_artifact_design('article', _brief(), tmp_path)
    assert calls == ['compose', 'New composition']


def test_feature_brief_is_one_page_and_article_is_two(tmp_path, monkeypatch):
    import html
    from app.services import marketing_content
    from app.services.marketing_layouts import document_html, layout_html
    from app.services.marketing_onepager import onepager_html
    brief = _onepager(body='Approved Markdown export')
    one = onepager_html(brief)
    assert one.count('class="page"') == 1 and '794px 1123px' in one
    assert 'class="dia' in one and 'Why teams pay for it' in one and 'The problem' in one
    for text in design.approved_text('feature_brief', brief):
        assert text in html.unescape(one)
    article = {'title': 'How channel breakdowns change a review', 'dek': 'A two-page look at what the breakdown shows.',
        'sections': [{'heading': 'What changed', 'body': 'The review starts from the channel, not from one total.'},
                     {'heading': 'How to use it', 'body': 'Open the breakdown before the meeting and note the differences.'},
                     {'heading': 'Boundaries', 'body': 'A difference is a question, not proof that one channel caused the result.'},
                     {'heading': 'Next step', 'body': 'Bring the differing channels into the review.'}],
        'cta': 'Open a recent campaign.', 'body': 'Approved document'}
    two = layout_html('article', article)
    assert two.count('class="page"') == 2
    for text in design.approved_text('article', article):
        assert text in two
    notes = document_html({'title': 'Voice cloning notes', 'dek': 'What changed for operators.',
        'sections': [{'heading': 'What changed', 'body': 'Operators can create a voice from a short clip.'}],
        'cta': 'See the workspace.'})
    assert 'class="page"' not in notes and 'Voice cloning notes' in notes and 'Operators can create a voice from a short clip.' in notes
    captured = []
    def artifact(key, content, folder, set_step=None):
        captured.append(key)
        (folder / f'{key}.pdf').write_bytes(b'%PDF')
        return [(f'{key}.pdf', 'application/pdf')]
    monkeypatch.setattr('app.services.marketing_design.render_artifact_design', artifact)
    assets = marketing_content.render_format('feature_brief', brief, tmp_path)
    assert captured == ['feature_brief']
    assert any(item['filename'] == 'feature_brief.pdf' for item in assets)
    message = tmp_path / 'post'
    message.mkdir()
    post = marketing_content.render_format('linkedin_post', {'title': 'A consistent voice', 'body': 'Paste this message into LinkedIn.'}, message)
    assert (message / 'linkedin_post.txt').read_text().strip() == 'Paste this message into LinkedIn.'
    assert captured == ['feature_brief']
    assert any(item['filename'] == 'linkedin_post.txt' for item in post)


def test_one_pager_steps_down_density_but_never_rewrites_copy(tmp_path, monkeypatch):
    from app.services.marketing_onepager import render_onepager
    sources = []
    def render(key, content, source, folder, export=True):
        sources.append(source)
        if len(sources) < 3:
            raise ValueError('Page 1 exceeds its 794x1123 board')
        return [('feature_brief.pdf', 'application/pdf')]
    monkeypatch.setattr(design, 'render_design', render)
    steps = []
    render_onepager(_onepager(), tmp_path, lambda *a: steps.append(a[1]))
    assert 'font-size:40px;line-height:1.08' in sources[0] and 'font-size:36px;line-height:1.08' in sources[2]
    assert [s['design_repair_attempt'] for s in steps] == [1, 2]

    def reject(*args, **kwargs):
        raise ValueError('Design omitted or rewrote approved copy: title')
    monkeypatch.setattr(design, 'render_design', reject)
    with pytest.raises(ValueError, match='omitted or rewrote'):
        render_onepager(_onepager(), tmp_path)


def test_one_pager_proof_must_be_a_verified_capture():
    from app.services.marketing_onepager import onepager_html
    shot = {'kind': 'screenshot', 'screenshot': 'branch/not-a-release/missing-shot', 'heading': 'Every channel, side by side',
            'caption': 'Channel Breakdown on a campaign. Data is illustrative.'}
    with pytest.raises(ValueError, match='verified product capture'):
        onepager_html(_onepager(visuals=[shot]))


def test_captures_match_the_market_name_or_the_code_name(tmp_path, monkeypatch):
    import json
    from PIL import Image
    from app.services import marketing_onepager as onepager
    folder = tmp_path / 'branch' / 'agent-monitoring'
    (folder / 'raw').mkdir(parents=True)
    Image.new('RGB', (40, 20), 'white').save(folder / 'raw' / 'findings.png')
    (folder / 'note.json').write_text(json.dumps({'feature': 'Agent Monitoring', 'title': 'Agent Analysis',
        'aliases': ['AI Call Quality Review'],
        'sections': [{'heading': 'Findings', 'screenshot': {'id': 'findings', 'caption': 'Root causes of a run.'}}]}))
    monkeypatch.setattr(onepager, 'ASSETS', tmp_path)
    for name in ('Agent Monitoring', 'Agent Analysis v2', 'AI Call Quality Review'):
        assert [s['id'] for s in onepager.verified_screenshots(name)] == ['branch/agent-monitoring/findings']
    assert onepager.verified_screenshots('Campaign Health') == []


def test_locked_layout_shrinks_to_fit_and_does_not_rewrite_copy(tmp_path, monkeypatch):
    from app.services.marketing_layouts import render_locked
    calls = []
    def render(key, content, source, folder, export=True):
        calls.append(source)
        if len(calls) == 1:
            raise ValueError('Page 1 exceeds its 794x1123 board')
        return [('feature_brief.pdf', 'application/pdf')]
    monkeypatch.setattr(design, 'render_design', render)
    render_locked('feature_brief', _brief(), tmp_path)
    assert '13px' in calls[0] and '12px' in calls[1]
    assert _brief()['title'] in calls[1]

    def reject(*args, **kwargs):
        raise ValueError('Design omitted or rewrote approved copy: title')
    monkeypatch.setattr(design, 'render_design', reject)
    with pytest.raises(ValueError, match='omitted or rewrote'):
        render_locked('feature_brief', _brief(), tmp_path)
