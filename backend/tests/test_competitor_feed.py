from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.database import Base
from app.models import Competitor, CompetitorSignal
from app.services.competitive import _ArticleLinks, _heuristic_tag, feature_evidence, signal_feed


def test_article_links_exclude_navigation_and_offsite():
    parser = _ArticleLinks('https://voice.example/blog')
    parser.feed('<a href="/blog">Our company blog and updates</a><a href="/blog/launch">Introducing multilingual voice agents</a><a href="https://other.example/blog/launch">Other company product announcement</a>')
    assert len(parser.items) == 1
    assert parser.items[0]['url'] == 'https://voice.example/blog/launch'


def test_landing_pages_are_not_release_announcements():
    row = CompetitorSignal(title='New features in our voice platform', summary='Introducing voice agents', source='blog', url='https://example.com/blog', tag='feature_parity')
    evidence = feature_evidence(row)
    assert evidence['is_snapshot']
    assert evidence['release_status'] != 'Release announcement'
    assert _heuristic_tag('About us', 'Company background') != 'shipping'


def test_feature_feed_filters_and_deduplicates():
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        rival = Competitor(name='Voice Co', slug='voice-co', active=True)
        db.add(rival); db.flush()
        for title, tag, url in [('Introducing WhatsApp journey orchestration', 'shipping', '/blog/launch'), ('Introducing WhatsApp journey orchestration', 'shipping', '/blog/launch'), ('Company investment news', 'positioning', '/blog/funding')]:
            db.add(CompetitorSignal(competitor_id=rival.id, competitor_name=rival.name, title=title, summary=title, tag=tag, source='blog', url='https://example.com'+url))
        db.commit()
        data=signal_feed(db,view='features',focus='Omnichannel orchestration')
        assert data['total']==1
        assert data['signals'][0]['release_status']=='Release announcement'
        assert signal_feed(db,q='investment')['total']==1
        assert signal_feed(db,view='features',offset=1)['signals']==[]


def test_news_merges_market_pricing_and_separates_ai():
    from app.models import MarketWatch, MarketSignal
    engine=create_engine('sqlite://');Base.metadata.create_all(engine)
    with Session(engine) as db:
        rival=Competitor(name='Voice',slug='voice',active=True);db.add(rival);db.flush()
        db.add(CompetitorSignal(competitor_id=rival.id,competitor_name='Voice',title='Voice pricing page changed',source='pricing',url='https://example.com/pricing',tag='pricing',summary='Plan limits changed'))
        for category in ['industry','ai']:
            watch=MarketWatch(name=category,category=category,active=True,url='https://example.com/'+category);db.add(watch);db.flush()
            db.add(MarketSignal(watch_id=watch.id,category=category,source_name=category,title='New voice capability',summary='Voice agents',url='https://example.com/news/'+category))
        db.commit()
        assert {r['news_tag'] for r in signal_feed(db)['signals']}=={'Price Change','Industry News'}
        assert signal_feed(db,tag='Price Change')['total']==1
        ai=signal_feed(db,view='ai')['signals']
        assert len(ai)==1 and ai[0]['news_tag']=='Builder pattern' and ai[0]['id']<0


def test_news_task_reuses_preview_without_writing_jira(monkeypatch):
    from app.models import CopilotPlan
    from app.services import news_ticket
    engine=create_engine('sqlite://');Base.metadata.create_all(engine)
    calls=[]
    def fake_plan(db,**kwargs):
        calls.append(kwargs)
        plan=CopilotPlan(prompt=kwargs['prompt'],notes=kwargs['notes'],answer='Review task',context_json={})
        db.add(plan);db.commit();return {'id':plan.id}
    monkeypatch.setattr(news_ticket,'plan_copilot',fake_plan)
    monkeypatch.setattr(news_ticket,'load_profile',lambda:{'pm_display_name':'Owner'})
    with Session(engine) as db:
        source=CompetitorSignal(title='New voice feature',source='blog',url='https://example.com/blog/voice',summary='A voice update')
        db.add(source);db.commit()
        first=news_ticket.prepare_ticket(db,source.id)
        second=news_ticket.prepare_ticket(db,source.id)
        assert first['id']==second['id'] and len(calls)==1
        assert source.url in calls[0]['notes'] and 'AC' in calls[0]['prompt']
        assert 'Owner' in calls[0]['prompt']


def test_ai_maturity_and_rss_readability():
    from app.services.competitive import ai_capability, clean_summary, is_blocked_news, _parse_rss_items
    assert ai_capability('Preview of a new voice model','Early access')['maturity']=='Preview / upcoming'
    assert ai_capability('Preview of a new voice model','Early access')['news_tag']=='New model'
    assert ai_capability('Speech research','A benchmark study')['maturity']=='Research'
    assert ai_capability('Speech research','A benchmark study')['news_tag']=='Research'
    assert ai_capability('Funding grants for research','Apply now') is None
    hermes = ai_capability('Hermes agent stack goes open source', 'Local LLM setup for builders')
    assert hermes['news_tag'] == 'Agent setup'
    viral = ai_capability('GitHub repo hits 40k stars', 'Open source AI agent framework trending')
    assert viral['news_tag'] == 'Viral repo'
    assert is_blocked_news('Buy GitHub Stars - Los Gatan', 'Los Gatan', 'https://news.google.com/rss/articles/x')
    assert is_blocked_news('', '', 'https://losgatan.com/foo')
    assert not is_blocked_news('OpenAI launches GPT', 'Model release', 'https://openai.com/news')
    xml = '''<rss><item><title>Spam - Los Gatan</title><link>https://news.google.com/x</link>
      <description>Buy stars</description><source url="https://losgatan.com">Los Gatan</source></item>
      <item><title>Real AI news - OpenAI</title><link>https://openai.com/a</link>
      <description>Model</description><source url="https://openai.com">OpenAI</source></item></rss>'''
    items = _parse_rss_items(xml)
    assert len(items) == 1 and items[0]['title'].startswith('Real AI')
    assert clean_summary('&lt;a href="https://example.com"&gt;New feature&lt;/a&gt;')=='New feature'
    assert clean_summary('&lt;a href="https://example.com/very-long', 'News headline')=='News headline'
