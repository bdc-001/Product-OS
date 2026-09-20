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


def test_brief_design_must_render_every_element_of_the_visual_pack():
    content={'title':'Read a campaign channel by channel','dek':'See which channel deserves a closer look.',
        'stats':[{'value':'1 view','label':'Every channel in the campaign'}],
        'blocks':[{'kind':'why','heading':'Why you need this','risk':'One total hides the channel that needs attention.',
            'items':[{'lead':'A specific start','text':'Open the breakdown and see which channel differs.'}]}],
        'cta':'Open a recent campaign.','review':{'evidence':'Internal source excerpt'}}
    assert design.approved_text('feature_brief',content)==[
        'Read a campaign channel by channel','See which channel deserves a closer look.','1 view',
        'Every channel in the campaign','Why you need this','One total hides the channel that needs attention.',
        'A specific start','Open the breakdown and see which channel differs.','Open a recent campaign.']


def test_visual_formats_get_device_specific_design_direction():
    assert 'connected sequence with visible order' in design.FORMAT_DESIGN['feature_brief']
    assert 'stacked text cards' in design.FORMAT_DESIGN['linkedin_carousel']
    assert 'article' not in design.FORMAT_DESIGN


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
    first=design.compose_design('feature_brief',content,tmp_path)
    assert [c[0] for c in calls]==['marketing_design','marketing_design_polish']
    assert calls[0][3]['images'][0]['name']=='design_ref_1'
    assert 'full-bleed navy masthead' in calls[0][1]
    assert renders==[{'export':False}]
    assert design.compose_design('feature_brief',content,tmp_path)==first
    assert len(calls)==2


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
    design.compose_design('feature_brief',{'title':'Agent Testing','body':'Approved text'},tmp_path)
    assert requests[-1]['repair']=='Page 1 clips a heading.'


def test_visual_failure_revises_design_and_preserves_approved_copy(tmp_path, monkeypatch):
    from app.services import marketing_content, marketing_quality
    calls = []
    content = {'title': 'Agent Testing', 'body': 'Approved words', 'review': {'evidence': 'internal'}}
    def compose(key, approved, folder, **kwargs):
        assert approved is content
        calls.append(kwargs)
        return f'<html>Layout {len(calls)}</html>'
    monkeypatch.setattr(design, 'compose_design', compose)
    monkeypatch.setattr(design, 'render_design', lambda *a, **kw: [('feature_brief.pdf', 'application/pdf')])
    def review(*args):
        if len(calls) == 1:
            raise ValueError('Page 1 has generic cards instead of a meaningful flow.')
        return [('feature_brief-visual-review.json', 'application/json')]
    monkeypatch.setattr(marketing_quality, 'review_rendered', review)
    assets = marketing_content.render_format('feature_brief', content, tmp_path)
    assert len(calls) == 2
    assert calls[1]['repair'] == 'Page 1 has generic cards instead of a meaningful flow.'
    assert calls[1]['previous_html'] == '<html>Layout 1</html>'
    assert any(a['filename'].endswith('-visual-review.json') for a in assets)
    assert content['body'] == 'Approved words'


def test_failed_design_does_not_trigger_campaign_copy_rewrite(tmp_path, monkeypatch):
    from app.services import marketing_content, marketing_quality
    monkeypatch.setattr(design, 'compose_design', lambda *a, **kw: '<html>Layout</html>')
    monkeypatch.setattr(design, 'render_design', lambda *a, **kw: [('feature_brief.pdf', 'application/pdf')])
    def fail(*args):
        raise ValueError('Visual quality below threshold')
    monkeypatch.setattr(marketing_quality, 'review_rendered', fail)
    with pytest.raises(design.DesignQualityError):
        marketing_content.render_format('feature_brief', {'title': 'Agent Testing', 'body': 'Approved words'}, tmp_path)
    assert not issubclass(design.DesignQualityError, ValueError)
