import math
import wave
from array import array
from pathlib import Path
from typing import get_args

import pytest

from app.services.marketing_content import UiScreen, Video, VoicePerformance
from app.services.marketing_film_gates import LAUNCH_BACKGROUNDS, LAUNCH_LAYOUTS, LAUNCH_THEMES, launch_craft, launch_layouts, launch_theme
from app.services.marketing_performance import LAUNCH_GAPS, RING_SECONDS, gap_between, narration_passages, performance_profile
from app.services.marketing_score import RATE, launch_sfx_cues, message_arrivals, mix_under_voice, write_sfx
from app.services.marketing_video import VOICE_PROFILE
from app.services.marketing_voice import bind_launch_cues


def narrator(text, **extra):
    return {'narration': text, **extra}


def test_consecutive_narrator_scenes_share_one_read_and_dialogue_breaks_it():
    scenes = [narrator('Your agent is on calls all day.'), narrator('Your team hears a handful.'),
              {'narration': 'Hi Rahul, your EMI is due today.', 'voice': 'agent'},
              {'narration': 'I already paid it yesterday.', 'voice': 'customer'},
              narrator('One missed cue, and a paying borrower gets chased.'), narrator('Agent Monitoring catches it.')]
    assert narration_passages(scenes, continuous=True) == [[0, 1], [2], [3], [4, 5]]
    assert narration_passages(scenes) == [[i] for i in range(6)]


def test_pauses_only_direction_inherits_the_narrator_delivery():
    pauses = VoicePerformance(pauses=[{'after': 'chased.', 'milliseconds': 400}]).model_dump()
    assert pauses['speed'] is None and pauses['emotion'] is None
    paused = narrator('One missed cue, and a paying borrower gets chased.', performance=pauses)
    assert performance_profile(paused)['speed'] == VOICE_PROFILE['speed']
    assert narration_passages([narrator('Your team hears a handful.'), paused], continuous=True) == [[0, 1]]


def test_a_real_delivery_change_or_hold_starts_a_new_read():
    brighter = narrator('Agent Monitoring catches it.', performance={'emotion': 'enthusiastic'})
    assert narration_passages([narrator('Your team hears a handful.'), brighter], continuous=True) == [[0], [1]]
    held = narrator('Your team hears a handful.', hold_after=1.0)
    assert narration_passages([held, narrator('Agent Monitoring catches it.')], continuous=True) == [[0], [1]]


def test_launch_gaps_are_tighter_than_diagram_holds():
    agent, customer, voice = {'voice': 'agent'}, {'voice': 'customer'}, {'visual': 'kinetic'}
    assert gap_between(agent, customer, launch=True) == LAUNCH_GAPS['turn']
    assert gap_between(customer, voice, launch=True) == LAUNCH_GAPS['hangup']
    assert gap_between(voice, agent, launch=True) == LAUNCH_GAPS['enter_call']
    assert gap_between(voice, {'voice': 'agent', 'visual': 'call'}, launch=True) == RING_SECONDS
    assert gap_between({'visual': 'presenting'}, {'visual': 'ui'}, launch=True) == LAUNCH_GAPS['presenting']
    assert gap_between(voice, {'visual': 'ui'}, launch=True) == LAUNCH_GAPS['beat'] < gap_between(voice, {'visual': 'ui'})


def timings(text, start, step=0.3):
    return [{'word': w, 'start': start + i * step, 'end': start + i * step + 0.25} for i, w in enumerate(text.split())]


def test_cursor_clicks_on_its_spoken_word_and_the_call_hangs_up_after_the_last_turn():
    agent = {'visual': 'call', 'voice': 'agent', 'from': 0, 'frames': 60, 'wordTimings': timings('Please pay today.', 0.2)}
    customer = {'visual': 'call', 'voice': 'customer', 'from': 60, 'frames': 60, 'wordTimings': timings('I already paid.', 2.2)}
    review = {'visual': 'call', 'voice': None, 'from': 120, 'frames': 60, 'wordTimings': timings('A paying borrower gets chased.', 4.2)}
    screen = {'visual': 'ui', 'from': 180, 'frames': 120, 'click_cue': 'accept or decline',
              'wordTimings': timings('Draft a patch you can accept or decline.', 6.2)}
    bind_launch_cues([agent, customer, review, screen], audio_lead=3)
    assert customer['hangupFrame'] == 3 + math.ceil(customer['wordTimings'][-1]['end'] * 30) + 8
    assert 'hangupFrame' not in agent and 'hangupFrame' not in review
    assert screen['clickAt'] == 3 + round(screen['wordTimings'][5]['start'] * 30)


def test_a_click_that_cannot_show_its_result_before_the_cut_fails():
    screen = {'visual': 'ui', 'from': 0, 'frames': 40, 'click_cue': 'decline', 'wordTimings': timings('Accept or decline.', 1.0)}
    with pytest.raises(ValueError, match='too late'):
        bind_launch_cues([screen])


def test_calls_and_screens_hold_one_field_and_the_film_closes_on_white():
    scenes = [{'visual': 'volume'}, {'visual': 'kinetic', 'kind': 'problem'}, {'visual': 'call'}, {'visual': 'call'},
              {'visual': 'kinetic', 'kind': 'benefit'}, {'visual': 'ui'}, {'visual': 'ui'}, {'visual': 'endcard'}]
    fields = [c['field'] for c in launch_craft(scenes)]
    assert fields == ['dark', 'light', 'stage', 'stage', 'brand', 'brand', 'brand', 'light']
    assert [c.get('look') for c in launch_craft(scenes)][2:4] == ['handset', 'handset']
    glass = launch_craft(scenes, style='chat')
    assert [c['field'] for c in glass][2:4] == ['dark', 'dark'] and glass[2]['look'] == 'glass'
    assert launch_craft([{'visual': 'presenting'}])[0]['field'] == 'light'
    assert {c['transition'] for c in launch_craft(scenes)} >= {'slide', 'wipe', 'fade', 'push'}


def test_back_to_back_type_cards_alternate_off_brand_blue():
    scenes = [{'visual': 'kinetic', 'kind': 'benefit'}, {'visual': 'ui'}, {'visual': 'kinetic', 'kind': 'benefit'},
              {'visual': 'orbit'}, {'visual': 'kinetic', 'kind': 'benefit'}, {'visual': 'kinetic', 'kind': 'benefit'},
              {'visual': 'endcard'}]
    assert [c['field'] for c in launch_craft(scenes)] == ['light', 'brand', 'light', 'dark', 'brand', 'light', 'light']


def test_every_classic_theme_draws_one_background_per_field_and_aura_has_its_own():
    from app.services.marketing_film_gates import AURA_THEME, CLASSIC_THEMES
    source = (Path(__file__).resolve().parents[2] / 'render/remotion/src/marketing/launch/core.tsx').read_text()
    classic_fields = set(LAUNCH_BACKGROUNDS) - {'aura'}
    used = set()
    for name in CLASSIC_THEMES:
        plan = LAUNCH_THEMES[name]
        assert set(plan['bg']) == classic_fields, name
        for field, bg in plan['bg'].items():
            assert bg in LAUNCH_BACKGROUNDS[field], (name, field, bg)
            used.add(bg)
    assert LAUNCH_THEMES[AURA_THEME]['bg'] == {'aura': 'aura'} and LAUNCH_BACKGROUNDS['aura'] == ('aura',)
    every = {bg for field in classic_fields for bg in LAUNCH_BACKGROUNDS[field]}
    assert len(every) == 12 and used == every
    assert all(f'"{bg}"' in source for bg in every | {'aura'})
    assert set(get_args(get_args(Video.model_fields['look'].annotation)[0])) == set(LAUNCH_THEMES)


def test_aura_is_the_default_and_a_look_pins_a_classic_theme():
    film = {'title': 'Campaign Health: See How Much Effort Each Lead Really Takes'}
    assert launch_theme(film) == launch_theme({'title': ''}) == 'aura'
    assert launch_theme({**film, 'look': 'night'}) == 'night'
    assert launch_theme({**film, 'look': 'not-a-theme'}) == 'aura'


def test_new_films_render_in_aura_rotate_the_score_and_rerenders_keep_their_theme(monkeypatch, tmp_path):
    import json, types
    from app.services import marketing_video
    from app.services.marketing_film_gates import AURA_SCORES

    path = tmp_path / 'film-log.json'
    # A film rendered before Aura keeps its classic world on re-render.
    path.write_text(json.dumps([{'title': 'Old film', 'feature': 'Old', 'theme': 'horizon', 'score': 'launch-drive-v1'}]))
    monkeypatch.setattr(marketing_video, 'FILM_LOG', types.SimpleNamespace(path=lambda: path))
    film = lambda title: {'title': title, 'scenes': [{'kind': 'hook', 'narration': f'{title} opens here.'}]}
    worlds = [marketing_video.film_world(film(f'Feature {i}: launch film')) for i in range(3)]
    assert {w['theme'] for w in worlds} == {'aura'}
    assert all(a['score'] != b['score'] for a, b in zip(worlds, worlds[1:])) and {w['score'] for w in worlds} == set(AURA_SCORES)
    assert marketing_video.film_world(film('Feature 2: launch film')) == worlds[2]
    # An Aura re-render drops a slow bed it was first logged with; a classic film keeps its own.
    log = json.loads(path.read_text())
    log[-1]['score'] = 'launch-pulse-v1'
    path.write_text(json.dumps(log))
    assert marketing_video.film_world(film('Feature 2: launch film'))['score'] in AURA_SCORES
    assert json.loads(path.read_text())[-1]['score'] in AURA_SCORES
    assert marketing_video.film_world(film('Old film'))['score'] == 'launch-drive-v1'
    assert marketing_video.film_world(film('Old film'))['theme'] == 'horizon'
    assert marketing_video.film_world({**film('Pinned: film'), 'look': 'night'})['theme'] == 'night'
    marketing_video.film_world(film('Next feature: launch film'))
    assert [f['title'] for f in marketing_video.recent_films(2)] == ['Pinned: film', 'Next feature: launch film']
    assert marketing_video.next_film_style() == 'chat'
    marketing_video.film_world({**film('Chat film'), 'style': 'chat'})
    assert marketing_video.next_film_style() == 'signal'


def chat_film(**change):
    def shot(kind, visual, headline, narration, **extra):
        return {'kind': kind, 'visual': visual, 'headline': headline, 'body': 'Illustrative scene for the film.', 'narration': narration,
                'evidence': 'Supported by the feature brief.', 'visual_reason': 'Shows the situation in the chat style devices.', **extra}
    scenes = [
        shot('hook', 'chat', 'She asked for a person', 'She typed it twice, politely: can I talk to someone?',
             labels=['Can I talk to someone?', 'I can help with that!'], label_cues=['She typed it twice', 'talk to someone']),
        shot('problem', 'call', 'The agent kept answering', 'I can help with your account right here.', voice='agent'),
        shot('problem', 'call', 'She asked again', 'Please, can I just talk to a person?', voice='customer'),
        shot('problem', 'search', 'Then she searched for a number', 'So she searched for a phone number, and found an old one.',
             labels=['support phone number', 'Contact us, old page'], label_cues=['searched for a phone', 'found an old one']),
        shot('problem', 'docs', 'The notes stayed behind', 'Every note from that chat stayed behind, with nobody to read it.',
             labels=['Chat transcript', 'Handover note'], label_cues=['Every note', 'nobody to read']),
        shot('problem', 'kinetic', 'Nobody picked it up', 'Nobody picked it up.'),
        shot('proof', 'presenting', 'Live Transfer', 'Presenting Live Transfer by Acme.'),
        shot('proof', 'pulse', 'A person joins with context', 'A person joins the conversation, with the full context already open.',
             labels=['Agent joined', 'Context passed'], label_cues=['person joins', 'full context'], screen={'title': 'Transfer'}),
        shot('benefit', 'chat', 'She got her answer', 'She got her answer, from a person, in the same chat.',
             labels=['Can I talk to someone?', 'Hi, I am here now.'], label_cues=['She got her answer', 'from a person']),
        shot('cta', 'endcard', 'Ask once. Get a person.', 'Ask once, and get a person.'),
    ]
    return {'title': 'Live Transfer: Get a person when it matters', 'body': 'A story-led launch film about live transfer. ' * 4,
            'filmKind': 'launch', 'style': 'chat', 'scenes': scenes, **change}


def test_style_films_open_on_their_own_device_and_cannot_borrow_another_style():
    Video.model_validate(chat_film())
    scenes = chat_film()['scenes']
    with pytest.raises(ValueError, match='opens on one of'):
        Video.model_validate(chat_film(scenes=[{**scenes[0], 'visual': 'kinetic', 'labels': [], 'label_cues': []}, *scenes[1:]]))
    with pytest.raises(ValueError, match='compose only from'):
        Video.model_validate(chat_film(scenes=[*scenes[:4], {**scenes[4], 'visual': 'fields'}, *scenes[5:]]))
    with pytest.raises(ValueError, match='three of the chat'):
        Video.model_validate(chat_film(scenes=[*scenes[:3], {**scenes[3], 'visual': 'kinetic', 'labels': [], 'label_cues': []}, {**scenes[4], 'visual': 'kinetic', 'labels': [], 'label_cues': []}, *scenes[5:]]))


def test_every_style_plays_a_live_call_and_presents_the_feature_once():
    scenes = chat_film()['scenes']
    with pytest.raises(ValueError, match='plays one live call'):
        Video.model_validate(chat_film(scenes=[scenes[0], *scenes[3:]]))
    presenting = scenes[6]
    with pytest.raises(ValueError, match='presenting card'):
        Video.model_validate(chat_film(scenes=[*scenes[:6], {**presenting, 'visual': 'kinetic'}, *scenes[7:]]))
    with pytest.raises(ValueError, match='presenting card'):
        Video.model_validate(chat_film(scenes=[*scenes[:6], scenes[7], presenting, *scenes[8:]]))
    with pytest.raises(ValueError, match='Presenting <feature> by <company>'):
        Video.model_validate(chat_film(scenes=[*scenes[:6], {**presenting, 'narration': 'Meet Live Transfer from Acme.'}, *scenes[7:]]))


def test_a_ringing_call_rings_until_the_pickup_then_connects():
    scenes = [{'visual': 'kinetic', 'kind': 'hook', 'from': 0},
              {'visual': 'call', 'voice': 'agent', 'from': 60, 'wordTimings': timings('Hello, how can I help?', 4.0)}]
    cues = launch_sfx_cues(scenes, launch_craft(scenes), audio_lead=3)
    pickup = (3 + round(4.0 * 30) - 10) / 30
    ring = next(kind for _, kind in cues if kind.startswith('ring:'))
    assert float(ring.split(':')[1]) == pytest.approx(pickup - 2 - 0.35, abs=0.01)
    assert (pytest.approx(pickup), 'connect') in [(at, kind) for at, kind in cues]


def test_themes_move_type_and_product_but_keep_calls_scale_and_close_in_role():
    scenes = [{'visual': 'volume'}, {'visual': 'kinetic', 'kind': 'problem'}, {'visual': 'call'}, {'visual': 'ui'},
              {'visual': 'kinetic', 'kind': 'benefit'}, {'visual': 'endcard'}]
    night = launch_craft(scenes, 'night')
    assert [c['field'] for c in night] == ['dark', 'dark', 'stage', 'dark', 'brand', 'light']
    assert [c['bg'] for c in night] == ['ink', 'ink', 'stage', 'ink', 'deep', 'cloud']
    editorial = launch_craft(scenes, 'editorial')
    assert editorial[3]['field'] == 'stage' and editorial[3]['luma'] == 'light'
    eclipse = launch_craft([{'visual': 'ui'}, {'visual': 'kinetic', 'kind': 'benefit'}], 'eclipse')
    assert [c['field'] for c in eclipse] == ['brand', 'dark']
    assert {c['theme'] for c in night} == {'night'}


def test_same_field_cuts_still_swipe_and_the_impact_lands_on_the_reveal():
    scenes = [{'visual': 'messages', 'kind': 'hook', 'from': 0}, {'visual': 'kinetic', 'kind': 'problem', 'from': 90},
              {'visual': 'messages', 'kind': 'problem', 'from': 180}, {'visual': 'kinetic', 'kind': 'benefit', 'from': 270},
              {'visual': 'ui', 'kind': 'proof', 'from': 330}, {'visual': 'ui', 'kind': 'proof', 'from': 420}]
    cues = launch_sfx_cues(scenes, launch_craft(scenes, 'night'))
    assert [at for at, kind in cues if kind == 'swipe'] == [90 / 30 + 0.2, 180 / 30 + 0.2, 270 / 30 + 0.2, 330 / 30 + 0.2]
    assert [at for at, kind in cues if kind == 'impact'] == [270 / 30 + 0.05]
    blueprint = launch_sfx_cues(scenes, launch_craft(scenes, 'blueprint'))
    assert [at for at, kind in blueprint if kind == 'impact'] == [270 / 30 + 0.05]


def test_a_filters_screen_can_show_a_lead_list_with_idle_quick_chips():
    screen = UiScreen.model_validate({
        'view': 'filters', 'title': 'Customers', 'controls': [{'label': 'Lead state'}],
        'conditions': [{'field': 'Lead Connectivity', 'operator': 'is', 'value': 'Not Connected'}],
        'records': [{'cells': ['Priya Raman', 'Active', 'EMI Reminders', 'Last: Sep 30']},
                    {'cells': ['Rohit Mehra', 'Active'], 'keep': False}, {'cells': ['Meena Krishnan']}],
        'meta': '2,480 leads', 'meta_after': '184 leads', 'action': 'Apply'})
    assert screen.controls[0].value == '' and not screen.columns
    with pytest.raises(ValueError, match='no more cells'):
        UiScreen.model_validate({**screen.model_dump(), 'records': [{'cells': ['a', 'b', 'c', 'd', 'e']}] * 3})


METRICS = [{'label': 'Total Attempted', 'value': '48,210', 'note': 'send attempts'},
           {'label': 'Delivered', 'value': '12,550', 'status': 'delivered'},
           {'label': 'Failed', 'value': '4,966', 'status': 'failed'}]


def test_a_metrics_click_must_open_a_real_popup():
    screen = UiScreen.model_validate({'view': 'metrics', 'metrics': METRICS, 'action': 'View failure reasons', 'modal_title': 'Failure Reasons',
                                      'bars': [{'label': 'Undeliverable / blocked', 'value': '2,140', 'share': 43.1},
                                               {'label': 'Ecosystem limit', 'value': '574', 'share': 11.6}]})
    assert screen.metrics[-1].status == 'failed'
    with pytest.raises(ValueError, match='popup'):
        UiScreen.model_validate({'view': 'metrics', 'metrics': METRICS, 'action': 'View failure reasons'})
    with pytest.raises(ValueError, match='summary cards'):
        UiScreen.model_validate({'view': 'metrics', 'metrics': METRICS[:2]})
    with pytest.raises(ValueError, match='more than two stats'):
        UiScreen.model_validate({'view': 'cards', 'cards': [{'title': 'Root cause', 'stats': [{'label': f's{i}', 'value': '1'} for i in range(3)]}]})


def test_table_and_chart_screens_need_whole_rows_and_matching_series():
    rows = [{'cells': ['+91 80 4718 2200', '18,420', 'Healthy']}] * 3
    UiScreen.model_validate({'view': 'table', 'columns': ['Number', 'Sent', 'Health'], 'records': rows})
    with pytest.raises(ValueError, match='one cell per column'):
        UiScreen.model_validate({'view': 'table', 'columns': ['Number', 'Sent', 'Read %', 'Health'], 'records': rows})
    series = [{'label': name, 'value': '10', 'points': [1, 2, 3, 4]} for name in ('Attempted', 'Read', 'Responded')]
    chart = {'view': 'chart', 'series': series, 'toggle': ['Funnel', 'Trend'], 'titles': ['Delivery Funnel', 'Message Trend']}
    UiScreen.model_validate(chart)
    with pytest.raises(ValueError, match='same number of points'):
        UiScreen.model_validate({**chart, 'series': [*series[:2], {**series[2], 'points': [1, 2, 3, 4, 5]}]})


def scene(**extra):
    return {'kind': 'proof', 'headline': 'Every message, accounted for', 'body': 'Illustrative recreation.',
            'narration': 'Your team sees every reminder delivered, read or failed.', 'evidence': 'WhatsApp Analytics summary cards.',
            'visual_reason': 'The summary cards light up on the words that name them.', **extra}


def story_film(**changes):
    beat = lambda kind, visual, headline, narration, **extra: scene(kind=kind, visual=visual, headline=headline, narration=narration, **extra)
    scenes = [
        beat('hook', 'volume', 'Hundreds of calls, all fine', 'Hundreds of calls go out today, and every one sounds fine.'),
        beat('problem', 'volume', 'A callback that never comes', 'Until a customer asks for a callback that never comes.'),
        beat('problem', 'call', 'Can someone call me back?', 'Can someone call me back after six today?', voice='customer'),
        beat('problem', 'call', 'Of course, noted', 'Of course, I have noted a callback after six.', voice='agent'),
        beat('problem', 'kinetic', 'Nobody on the team heard it', 'Nobody on the team heard it.'),
        beat('problem', 'volume', 'Gone by Monday', 'By Monday, that customer has already moved on to someone else.'),
        beat('proof', 'presenting', 'Agent Monitoring', 'Presenting Agent Monitoring by Acme.'),
        beat('proof', 'orbit', 'The missed promise, flagged', 'It flags the call where a callback was promised, and missed.',
             labels=['Callback promised', 'Missed'], label_cues=['callback was promised', 'missed']),
        beat('benefit', 'kinetic', 'Called back the same day', 'Your team lead hears it that afternoon, and calls back the same day.'),
        beat('cta', 'endcard', 'Every call, finally heard', 'Every call, finally heard.'),
    ]
    # The classic grammar (orbit as the mechanism shot) holds whenever a look pins a classic theme.
    return {'title': 'Agent Monitoring by Acme', 'filmKind': 'launch', 'look': 'horizon', 'scenes': scenes,
            'body': 'A callback promised on a call and never made. See how Agent Monitoring flags the missed promise so your team can act the same day.', **changes}


def test_launch_films_tell_a_story_and_keep_the_feature_brief():
    from app.services.marketing_content import Video
    film = story_film()
    Video.model_validate(film)
    s = film['scenes']
    orbit = s[7]
    with pytest.raises(ValueError, match='three feature shots'):
        Video.model_validate({**film, 'scenes': [*s[:7], orbit, s[8], {**orbit, 'headline': 'Second orbit'},
                                                  {**orbit, 'headline': 'Third orbit'}, {**orbit, 'headline': 'Fourth orbit'}, s[9]]})
    with pytest.raises(ValueError, match='three shots on the situation'):
        Video.model_validate({**film, 'scenes': [s[0], orbit, *s[1:7], s[8], s[9]]})
    with pytest.raises(ValueError, match='a third of the spoken words'):
        long = {**orbit, 'narration': 'It flags every call where a callback was promised, missed, and routes it to your lead.'}
        Video.model_validate({**film, 'scenes': [*s[:7], long, {**long, 'headline': 'Routed to the lead'},
                                                  {**long, 'headline': 'Flagged for the lead'}, *s[8:]]})


def test_launch_films_open_on_a_picture_and_pool_shots_show_who_dials():
    from app.services.marketing_content import Scene, Video
    film = story_film()
    with pytest.raises(ValueError, match='opens on one of: call, messages, pool, volume'):
        Video.model_validate({**film, 'scenes': [{**film['scenes'][0], 'visual': 'kinetic'}, *film['scenes'][1:]]})
    contacts = ['Asha', 'Ravi', 'Meera', 'Kabir']
    Scene.model_validate(scene(visual='pool', pool={'mode': 'single', 'numbers': ['+91 80000 10001'], 'contacts': contacts}))
    with pytest.raises(ValueError, match='exactly one caller number'):
        Scene.model_validate(scene(visual='pool', pool={'mode': 'single', 'numbers': ['+91 80000 10001', '+91 80000 10002'], 'contacts': contacts}))
    with pytest.raises(ValueError, match='per-number cap'):
        Scene.model_validate(scene(visual='pool', pool={'mode': 'limit', 'numbers': ['+91 80000 10001', '+91 80000 10002', '+91 80000 10003'], 'contacts': contacts}))
    with pytest.raises(ValueError, match='needs its pool'):
        Scene.model_validate(scene(visual='pool'))
    rotate = {**film['scenes'][7], 'visual': 'pool', 'labels': [], 'label_cues': [],
              'pool': {'mode': 'rotate', 'numbers': ['+91 80000 10001', '+91 80000 10002', '+91 80000 10003'], 'contacts': contacts}}
    Video.model_validate({**film, 'scenes': [*film['scenes'][:7], rotate, *film['scenes'][8:]]})
    single = {**rotate, 'pool': {**rotate['pool'], 'mode': 'single', 'numbers': ['+91 80000 10001']}}
    with pytest.raises(ValueError, match='product screen or mechanism shot'):
        Video.model_validate({**film, 'scenes': [*film['scenes'][:7], single, *film['scenes'][8:]]})


def test_launch_films_are_industry_neutral():
    from app.services.marketing_content import Video
    film = story_film()
    with pytest.raises(ValueError, match='audience tag'):
        Video.model_validate({**film, 'scenes': [*film['scenes'][:5], {**film['scenes'][5], 'tag': 'Team leads'}, *film['scenes'][6:]]})
    hook = {**film['scenes'][0], 'narration': 'Hundreds of EMI reminders go out today, and every one sounds fine.'}
    with pytest.raises(ValueError, match='industry-neutral; remove emi'):
        Video.model_validate({**film, 'scenes': [hook, *film['scenes'][1:]]})
    with pytest.raises(ValueError, match='remove borrowers'):
        Video.model_validate({**film, 'body': film['body'] + ' Built for borrowers.'})
    # Source evidence may quote the product's own wording; only what the viewer sees or hears is checked.
    Video.model_validate({**film, 'scenes': [{**film['scenes'][0], 'evidence': 'Collections teams asked for this.'}, *film['scenes'][1:]]})


def test_screen_highlights_and_message_walls_name_what_is_on_screen():
    from app.services.marketing_content import Scene
    Scene.model_validate(scene(visual='ui', labels=['Failed'], label_cues=['failed'], screen={'view': 'metrics', 'metrics': METRICS}))
    with pytest.raises(ValueError, match='Highlighted labels'):
        Scene.model_validate(scene(visual='ui', labels=['Responded'], label_cues=['failed'], screen={'view': 'metrics', 'metrics': METRICS}))
    wall = [{'label': 'Your EMI is due on 5 Oct', 'tag': 'Collections', 'hint': 'read'},
            {'label': 'Your policy renews in 7 days', 'tag': 'Insurance', 'hint': 'failed'}] * 2
    Scene.model_validate(scene(kind='hook', visual='messages', screen={'rows': wall}))
    with pytest.raises(ValueError, match='two or more message types'):
        Scene.model_validate(scene(kind='hook', visual='messages', screen={'rows': [{**wall[0]}] * 4}))
    with pytest.raises(ValueError, match='real WhatsApp status'):
        Scene.model_validate(scene(kind='hook', visual='messages', screen={'rows': [{**r, 'hint': 'opened'} for r in wall]}))


def test_message_shots_sit_on_the_dark_field_and_tick_as_each_message_lands():
    rows = [{'label': 'Your EMI is due', 'tag': 'Collections', 'hint': 'read'}, {'label': 'Renew today', 'tag': 'Insurance', 'hint': 'failed'}] * 3
    scenes = [{'visual': 'messages', 'kind': 'hook', 'from': 0, 'frames': 200, 'screen': {'rows': rows}, 'layout': 'thread'},
              {'visual': 'messages', 'kind': 'problem', 'from': 200, 'frames': 120, 'screen': {'rows': rows}, 'layout': 'wall'}]
    craft = launch_craft(scenes)
    assert craft[0]['field'] == 'dark' and craft[0]['transition'] == 'slide'
    ticks = [at for at, kind in launch_sfx_cues(scenes, craft) if kind == 'tick']
    assert [round(at * 30) for at in ticks if at < 200 / 30] == [6 + 20 * k + 2 for k in range(6)]
    assert len([at for at in ticks if at >= 200 / 30]) == 6
    assert message_arrivals({'screen': {'rows': rows}, 'frames': 200}, 'phone') == [12, 30, 48]
    assert message_arrivals({'screen': {'rows': rows}, 'frames': 100}, 'lanes') == [12, 20, 96]


def test_scale_shots_rotate_single_object_layouts_per_film_and_never_default_to_the_wall():
    rows = [{'label': 'Your EMI is due', 'tag': 'Collections', 'hint': 'read'}, {'label': 'Renew today', 'tag': 'Insurance', 'hint': 'delivered'}] * 2
    failing = [{**row, 'hint': 'failed'} for row in rows]
    scenes = [{'visual': 'volume'}, {'visual': 'messages', 'screen': {'rows': rows}}, {'visual': 'kinetic', 'kind': 'problem'},
              {'visual': 'messages', 'screen': {'rows': rows}}, {'visual': 'messages', 'screen': {'rows': failing}}]
    picks = {}
    for i in range(30):
        layouts = launch_layouts(scenes, f'Feature {i}: launch film')
        assert layouts[2] is None and 'wall' not in layouts
        assert layouts[1] != layouts[3]
        assert layouts[4] != 'phone'
        picks.setdefault('volume', set()).add(layouts[0])
        picks.setdefault('messages', set()).add(layouts[1])
    assert picks == {visual: set(options) for visual, options in LAUNCH_LAYOUTS.items()}
    assert launch_layouts(scenes, 'x') == launch_layouts(scenes, 'x')
    assert launch_layouts([{'visual': 'volume', 'layout': 'wall'}], 'x') == ['wall']
    assert launch_craft(scenes, seed='x')[0]['layout'] == launch_layouts(scenes, 'x')[0]
    source = (Path(__file__).resolve().parents[2] / 'render/remotion/src/marketing/launch/ScaleShots.tsx').read_text()
    assert 'thread: [6, 20], phone: [10, 18], lanes: [8, 8, 84]' in source
    assert all(f'layout === "{name}"' in source for options in LAUNCH_LAYOUTS.values() for name in options)


def test_a_layout_belongs_to_its_shot_type():
    from app.services.marketing_content import Scene
    rows = [{'label': 'Your EMI is due on 5 Oct', 'tag': 'Collections', 'hint': 'read'},
            {'label': 'Your policy renews in 7 days', 'tag': 'Insurance', 'hint': 'failed'}] * 2
    Scene.model_validate(scene(kind='hook', visual='messages', screen={'rows': rows}, layout='lanes'))
    with pytest.raises(ValueError, match='does not belong'):
        Scene.model_validate(scene(kind='hook', visual='messages', screen={'rows': rows}, layout='timeline'))


def test_the_drive_score_is_an_original_faster_bed(tmp_path):
    from app.services.marketing_score import DRIVE, LAUNCH, write_score
    meta = write_score('launch-drive-v1', tmp_path / 'drive.wav', 8.0)
    samples, channels, seconds = read(tmp_path / 'drive.wav')
    assert meta['source'] == 'original' and DRIVE['bpm'] > LAUNCH['bpm']
    assert channels == 2 and seconds >= 8.0 and max(abs(s) for s in samples) > 10000


def test_the_surge_score_pumps_on_every_kick(tmp_path):
    from app.services.marketing_score import DRIVE, SURGE, write_score
    meta = write_score('launch-surge-v1', tmp_path / 'surge.wav', 8.0)
    samples, channels, seconds = read(tmp_path / 'surge.wav')
    assert meta['source'] == 'original' and meta['version'] == SURGE['version'] and SURGE['bpm'] >= 124
    assert channels == 2 and seconds >= 8.0 and max(abs(s) for s in samples) > 12000
    # Energy is dense, not peaky: the bed's RMS sits well above the slower drive bed's at the same length.
    write_score(DRIVE['version'], tmp_path / 'drive.wav', 8.0)
    rms = lambda s: (sum(v * v for v in s) / len(s)) ** 0.5
    assert rms(samples) > rms(read(tmp_path / 'drive.wav')[0])


def test_aura_narration_reads_at_launch_pace_but_calls_keep_their_voice():
    from app.services.marketing_performance import LAUNCH_PACE, launch_paced
    scenes = [narrator('Agent Monitoring catches it.'), {'voice': 'agent', 'narration': 'Hello, this is Geeta.'},
              narrator('Every fix is a version.', performance={'speed': 0.95})]
    paced = launch_paced(scenes)
    assert paced[0]['performance']['speed'] == LAUNCH_PACE and 1.05 < LAUNCH_PACE <= 1.15
    assert 'performance' not in paced[1] and paced[2]['performance']['speed'] == 0.95
    assert 'performance' not in scenes[0]
    assert performance_profile(paced[0])['speed'] == LAUNCH_PACE


def test_every_effect_answers_something_on_screen():
    scenes = [{'visual': 'kinetic', 'kind': 'problem', 'from': 0},
              {'visual': 'call', 'voice': 'agent', 'from': 60, 'hangupFrame': 150},
              {'visual': 'kinetic', 'kind': 'benefit', 'from': 160},
              {'visual': 'ui', 'from': 220, 'clickAt': 280, 'labelFrames': [10], 'screen': {'view': 'compare', 'toast': 'Prompt updated'}},
              {'visual': 'endcard', 'from': 340}]
    cues = launch_sfx_cues(scenes, launch_craft(scenes))
    kinds = [kind for _, kind in cues]
    assert cues == sorted(cues)
    assert kinds.count('impact') == 2 and 'connect' in kinds and 'hangup' in kinds and 'swipe' in kinds
    assert (280 / 30, 'click') in cues and any(kind == 'chime' and at > 280 / 30 for at, kind in cues)
    assert ((220 + 10 + 8) / 30, 'pop') in cues


def read(path):
    with wave.open(str(path), 'rb') as wav:
        samples = array('h'); samples.frombytes(wav.readframes(wav.getnframes()))
        return samples, wav.getnchannels(), wav.getnframes() / wav.getframerate()


def test_effects_track_mixes_under_a_silent_voice_without_a_score(tmp_path):
    sfx, voice, mixed = tmp_path / 'sfx.wav', tmp_path / 'voice.wav', tmp_path / 'mix.wav'
    write_sfx([(0.5, 'click'), (1.0, 'swipe'), (1.5, 'chime')], sfx, 2.0)
    effects, channels, seconds = read(sfx)
    assert channels == 2 and seconds >= 2.0 and max(abs(s) for s in effects) > 500
    with wave.open(str(voice), 'wb') as wav:
        wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(RATE)
        wav.writeframes(array('h', [0] * int(2.0 * RATE)).tobytes())
    mix_under_voice(voice, None, mixed, sfx=sfx)
    out, _, duration = read(mixed)
    assert abs(duration - 2.0) < 0.01 and max(abs(s) for s in out) > 500


TILES = [{'label': 'Avg. calls attempted per lead', 'value': '5.2', 'note': '21,840 calls · 4,200 leads'},
         {'label': 'Avg. calls connected per lead', 'value': '1.1', 'note': '4,750 connected calls'},
         {'label': 'Avg. attempts to connect', 'value': '4.6', 'note': 'Dials needed per connection'}]


def test_a_tiles_click_expands_its_own_section():
    UiScreen(view='tiles', title='Campaign Health', action='Campaign Health', tiles=TILES)
    with pytest.raises(ValueError, match='expands the section'):
        UiScreen(view='tiles', title='Campaign Health', action='Open', tiles=TILES)
    with pytest.raises(ValueError, match='three to six tiles'):
        UiScreen(view='tiles', title='Campaign Health', tiles=TILES[:2])


def test_tile_highlights_must_name_a_tile_on_screen():
    from app.services.marketing_content import Scene
    base = {'kind': 'proof', 'headline': 'Dials needed for every connection', 'body': 'Illustrative recreation.',
            'narration': 'Collections teams see how many dials each connection takes.', 'evidence': 'Tile Avg. attempts to connect.',
            'visual': 'ui', 'visual_reason': 'The attempts tile lights as dials per connection is spoken on the real section.',
            'screen': {'view': 'tiles', 'title': 'Campaign Health', 'tiles': TILES}}
    Scene(**base, labels=['Avg. attempts to connect'], label_cues=['dials each connection takes'])
    with pytest.raises(ValueError, match='must name a card, row or series'):
        Scene(**base, labels=['Dials per lead'], label_cues=['dials each connection takes'])


def test_launch_bed_stays_audible_under_the_voice(tmp_path):
    voice, bed = tmp_path / 'voice.wav', tmp_path / 'bed.wav'
    for path, channels, amp in ((voice, 1, 12000), (bed, 2, 8000)):
        with wave.open(str(path), 'wb') as wav:
            wav.setnchannels(channels); wav.setsampwidth(2); wav.setframerate(RATE)
            wav.writeframes(array('h', [int(amp * math.sin(2 * math.pi * 110 * i / RATE)) for i in range(RATE) for _ in range(channels)]).tobytes())

    def music_under_voice(**gains):
        mix_under_voice(voice, bed, tmp_path / 'mix.wav', **gains)
        mixed, _, _ = read(tmp_path / 'mix.wav')
        alone, _, _ = read(tmp_path / 'voice.wav')
        tail = range(RATE, 2 * RATE, 2)
        return max(abs(mixed[i] - alone[i // 2]) for i in tail)

    assert music_under_voice(music_gain=0.7, duck_floor=0.5) > 2.5 * music_under_voice()


def test_film_kit_rotates_every_set_piece_against_the_log_and_rerenders_keep_theirs(monkeypatch, tmp_path):
    import types
    from app.services import marketing_video
    from app.services.marketing_film_gates import FILM_KIT

    monkeypatch.setattr(marketing_video, 'FILM_LOG', types.SimpleNamespace(path=lambda: tmp_path / 'film-log.json'))
    film = lambda title, look='daylight': {'title': title, 'look': look, 'scenes': [{'kind': 'hook', 'narration': f'{title} opens here.'}]}
    kits = [marketing_video.film_world(film(f'Feature {i}'))['kit'] for i in range(4)]
    for part, options in FILM_KIT.items():
        assert all(a[part] != b[part] for a, b in zip(kits, kits[1:])), part
        assert {k[part] for k in kits[:len(options)]} == set(options[:4])
    assert marketing_video.film_world(film('Feature 2'))['kit'] == kits[2]
    assert marketing_video.recent_films(1)[0]['kit'] == kits[3]
    # Aura films stage Aura's own set pieces; the ringtone keeps rotating against the whole log.
    aura = [marketing_video.film_world(film(f'Aura {i}', None))['kit'] for i in range(2)]
    assert all(k['call'] == 'rings' and k['presenting'] == 'swarm' and k['endcard'] == 'tagline' for k in aura)
    assert aura[0]['ring'] != aura[1]['ring'] != kits[3]['ring']


def test_recuts_of_one_feature_replace_their_draft_and_log_their_shots(monkeypatch, tmp_path):
    import json, types
    from app.services import marketing_video

    path = tmp_path / 'film-log.json'
    monkeypatch.setattr(marketing_video, 'FILM_LOG', types.SimpleNamespace(path=lambda: path))
    film = lambda title, feature: {'title': title, 'feature': feature,
                                   'scenes': [{'kind': 'hook', 'visual': 'pool', 'narration': 'One number calls everyone.'}, {'visual': 'endcard'}]}
    other = marketing_video.film_world(film('Agent Monitoring film', 'Agent Monitoring'))
    first = marketing_video.film_world(film('Round-Robin cut one', 'Round-Robin'))
    second = marketing_video.film_world(film('Round-Robin cut two', 'Round-Robin'))
    log = json.loads(path.read_text())
    assert [e['feature'] for e in log] == ['Agent Monitoring', 'Round-Robin']
    assert log[-1]['title'] == 'Round-Robin cut two' and log[-1]['shots'] == ['pool', 'endcard']
    assert second['kit'] == first['kit'] and second['kit']['ring'] != other['kit']['ring']
    assert [e['title'] for e in marketing_video.recent_films(feature='Round-Robin')] == ['Agent Monitoring film']


def test_legacy_films_count_their_style_call_look():
    from app.services.marketing_film_gates import film_kit
    log = [{'title': 'Agent Monitoring', 'style': 'call'}, {'title': 'Live Call Transfer', 'style': 'signal'}]
    assert film_kit(log) == {'call': 'duet', 'ring': 'classic', 'presenting': 'lockup', 'endcard': 'recap'}
    assert film_kit(log, {'kit': {'call': 'glass'}})['call'] == 'glass'
    assert film_kit(log, aura=True) == {'call': 'rings', 'ring': 'classic', 'presenting': 'swarm', 'endcard': 'tagline'}


def test_kit_sets_the_call_look_ring_and_card_designs_with_their_fields():
    scenes = [{'visual': 'call', 'voice': 'agent'}, {'visual': 'presenting'}, {'visual': 'india'}, {'visual': 'endcard', 'kind': 'cta'}]
    craft = launch_craft(scenes, kit={'call': 'split', 'ring': 'buzz', 'presenting': 'hub', 'endcard': 'ink'})
    assert [(c.get('look'), c['field']) for c in craft] == [('split', 'stage'), ('hub', 'dark'), (None, 'light'), ('ink', 'dark')]
    assert craft[0]['ring'] == 'buzz' and 'ring' not in craft[1]
    assert launch_craft(scenes, style='chat')[0]['look'] == 'glass'


@pytest.mark.parametrize('tone', ['marimba', 'classic', 'pulse', 'buzz'])
def test_each_ringtone_sounds_and_rides_the_ring_cue(tone):
    from app.services.marketing_score import RINGTONES, _sound
    import random
    samples, _ = _sound(f'ring:{tone}:1.80', random.Random(1))
    assert tone in RINGTONES and max(abs(v) for v in samples) > 0.02
    scenes = [{'visual': 'call', 'voice': 'agent', 'from': 0, 'frames': 120, 'wordTimings': [{'word': 'Hi', 'start': 2.5, 'end': 2.7}]}]
    cues = launch_sfx_cues(scenes, [{'field': 'stage', 'ring': tone}])
    assert any(kind.startswith(f'ring:{tone}:') for _, kind in cues)


def test_india_map_pins_only_places_it_can_draw():
    from app.services.marketing_content import INDIA_PLACES, Scene
    base = {'kind': 'proof', 'headline': 'Every region hears its own language', 'body': 'Illustrative map.',
            'narration': 'Your agent speaks Hindi in Delhi and Tamil in Chennai.', 'evidence': 'Supported languages list.',
            'visual': 'india', 'visual_reason': 'The map pins each language as it is spoken.'}
    Scene(**base, labels=['Hindi', 'Tamil'], label_cues=['Hindi', 'Tamil'])
    with pytest.raises(ValueError, match='Indian languages or cities'):
        Scene(**base, labels=['Hindi', 'Atlantis'], label_cues=['Hindi', 'Tamil'])
    geo = (Path(__file__).resolve().parents[2] / 'render/remotion/src/marketing/launch/indiaGeo.ts').read_text()
    assert all(f'"{place}":' in geo for place in INDIA_PLACES)


def aura_film(**changes):
    film = story_film(look=None)
    s = film['scenes']
    network = {**s[7], 'visual': 'network', 'visual_reason': 'The camera pans from the call to the flag on each cue.'}
    return {**film, 'scenes': [*s[:7], network, *s[8:]], **changes}


def test_aura_films_compose_from_the_signature_shots_and_network_replaces_orbit():
    film = aura_film()
    Video.model_validate(film)
    s = film['scenes']
    with pytest.raises(ValueError, match='compose only from'):
        Video.model_validate({**film, 'scenes': [*s[:7], {**s[7], 'visual': 'orbit'}, *s[8:]]})
    with pytest.raises(ValueError, match='compose only from'):
        Video.model_validate({**film, 'look': 'horizon'})
    pills = {**s[0], 'visual': 'pills', 'headline': 'Calls and callbacks, all day',
             'narration': 'Your agents make calls and promise callbacks all day long.',
             'labels': ['Calls', 'Callbacks'], 'label_cues': ['calls', 'callbacks']}
    Video.model_validate({**film, 'scenes': [pills, *s[1:]]})
    with pytest.raises(ValueError, match='opens on one of'):
        Video.model_validate({**film, 'look': 'horizon', 'scenes': [pills, *s[1:7], {**s[7], 'visual': 'orbit'}, *s[8:]]})


def test_aura_shot_labels_follow_their_rules():
    from app.services.marketing_content import Scene
    Scene.model_validate(scene(visual='pills', labels=['Delivered', 'Read'], label_cues=['delivered', 'read']))
    with pytest.raises(ValueError, match='pills shot carries 2-3 labels'):
        Scene.model_validate(scene(visual='pills', labels=['Delivered'], label_cues=['delivered']))
    with pytest.raises(ValueError, match='network shot carries 2-3 labels'):
        Scene.model_validate(scene(visual='network'))
    with pytest.raises(ValueError, match='bloom shot carries 2-3 labels'):
        Scene.model_validate(scene(visual='bloom', labels=['Delivered'], label_cues=['delivered']))


def test_a_stat_figure_and_toggle_settings_come_from_the_evidence():
    from app.services.marketing_content import Scene
    stat = scene(visual='stat', headline='Live in 2 minutes', narration='Your first agent goes live in about 2 minutes.',
                 evidence='Setup completes in 2 minutes from the template.')
    Scene.model_validate(stat)
    with pytest.raises(ValueError, match='must come from the evidence; 2 is not'):
        Scene.model_validate({**stat, 'evidence': 'Setup is quick from the template.'})
    with pytest.raises(ValueError, match='one short figure'):
        Scene.model_validate({**stat, 'headline': 'Live in minutes'})
    toggles = scene(visual='toggles', headline='One switch for retries', narration='Turn on auto retry and every missed call is dialled again.',
                    evidence='Settings > Calling: Auto retry (on/off).', labels=['Auto retry'], label_cues=['auto retry'])
    Scene.model_validate(toggles)
    with pytest.raises(ValueError, match='verbatim product settings'):
        Scene.model_validate({**toggles, 'labels': ['Smart redial'], 'label_cues': ['every missed call']})


def test_bloom_use_cases_stay_industry_neutral():
    film = aura_film()
    s = film['scenes']
    bloom = {**s[8], 'visual': 'bloom', 'headline': 'Every follow-up, on time',
             'narration': 'Use it for callbacks, renewals and escalations, the same afternoon.',
             'labels': ['Callbacks', 'Renewals', 'Escalations'], 'label_cues': ['callbacks', 'renewals', 'escalations']}
    Video.model_validate({**film, 'scenes': [*s[:8], bloom, s[9]]})
    vertical = {**bloom, 'narration': 'Use it for collections, admissions and escalations, the same afternoon.',
                'labels': ['Collections', 'Admissions', 'Escalations'], 'label_cues': ['collections', 'admissions', 'escalations']}
    with pytest.raises(ValueError, match='industry-neutral; remove admissions, collections'):
        Video.model_validate({**film, 'scenes': [*s[:8], vertical, s[9]]})


def test_a_screenshot_shot_names_one_capture_and_a_film_shows_at_most_one():
    from app.services.marketing_content import Scene
    shot = scene(visual='screenshot', shot_id='branch/agent-monitoring/findings')
    Scene.model_validate(shot)
    with pytest.raises(ValueError, match='names one capture from available_screens'):
        Scene.model_validate({**shot, 'shot_id': ''})
    with pytest.raises(ValueError, match='only screenshot shots carry one'):
        Scene.model_validate(scene(visual='kinetic', shot_id='branch/agent-monitoring/findings'))
    with pytest.raises(ValueError, match='shows the capture under its headline; no labels'):
        Scene.model_validate({**shot, 'labels': ['Failed'], 'label_cues': ['failed']})
    film = aura_film()
    s = film['scenes']
    capture = {**s[7], 'visual': 'screenshot', 'shot_id': 'branch/agent-monitoring/findings', 'labels': [], 'label_cues': []}
    Video.model_validate({**film, 'scenes': [*s[:7], capture, *s[8:]]})
    with pytest.raises(ValueError, match='at most one real product capture'):
        Video.model_validate({**film, 'scenes': [*s[:7], capture, {**capture, 'headline': 'Flagged in the report'}, *s[8:]]})


def test_the_writer_sees_verified_captures_and_must_pick_one_of_them(monkeypatch, tmp_path):
    import types
    from app.services import marketing_content as content, marketing_video
    monkeypatch.setattr(marketing_video, 'FILM_LOG', types.SimpleNamespace(path=lambda: tmp_path / 'film-log.json'))
    captures = [{'id': 'branch/agent-monitoring/findings', 'caption': 'Findings list with the missed callback flagged.',
                 'section': 'Findings', 'uri': 'file:///x.png', 'width': 1280, 'height': 720}]
    monkeypatch.setattr(content, 'verified_screenshots', lambda *names: captures)
    film = aura_film()
    s = film['scenes']
    capture = {**s[7], 'visual': 'screenshot', 'labels': [], 'label_cues': []}
    replies = [{**film, 'scenes': [*s[:7], {**capture, 'shot_id': 'branch/agent-monitoring/invented'}, *s[8:]]},
               {**film, 'scenes': [*s[:7], {**capture, 'shot_id': captures[0]['id']}, *s[8:]]}]
    seen = []
    def writer(surface, prompt, payload, **kwargs):
        seen.append(payload)
        return replies[len(seen) - 1]
    monkeypatch.setattr(content, 'chat_json', writer)
    brief = {'name': 'Agent Monitoring', 'description': 'Flags calls where a callback was promised and missed.'}
    out = content.write_format(brief, {'cta': 'See it live.'}, {'format': 'youtube_landscape_video', 'angle': 'Missed callbacks'})
    assert seen[0]['available_screens'] == [{k: captures[0][k] for k in ('id', 'caption', 'section')}]
    assert 'must use an id from available_screens' in seen[1]['repair']
    shot = next(scene for scene in out['scenes'] if scene['visual'] == 'screenshot')
    assert shot['shotCaption'] == captures[0]['caption']


def test_aura_craft_morphs_every_cut_on_one_field_with_its_own_set_pieces():
    from app.services.marketing_film_gates import AURA_KIT, film_kit
    scenes = [{'visual': v} for v in ('call', 'call', 'kinetic', 'network', 'presenting', 'pills', 'endcard')]
    craft = launch_craft(scenes, theme='aura', kit=film_kit([], aura=True))
    assert {c['field'] for c in craft} == {c['bg'] for c in craft} == {'aura'}
    assert [c['transition'] for c in craft] == ['dot', 'dot', 'fill', 'zoom', 'zoom', 'blur', 'dot']
    assert craft[0]['look'] == 'rings' and craft[4]['look'] == 'swarm' and craft[6]['look'] == 'tagline'
    assert craft[0]['ring'] == AURA_KIT['ring'][0]
    classic = launch_craft(scenes, theme='horizon', kit={'call': 'rings'})
    assert 'aura' not in {c['field'] for c in classic} and not {'dot', 'fill', 'zoom', 'blur'} & {c['transition'] for c in classic}
    assert classic[0]['field'] == classic[3]['field'] == LAUNCH_THEMES['horizon']['product']


def test_aura_sound_breathes_through_morphs_and_answers_presses_and_stats():
    scenes = [{'visual': 'pills', 'kind': 'hook', 'from': 0, 'labelFrames': [10, 40]},
              {'visual': 'stat', 'kind': 'proof', 'from': 90, 'wordTimings': [{'word': 'Live', 'start': 3.5, 'end': 3.8}]},
              {'visual': 'network', 'kind': 'proof', 'from': 180, 'labelFrames': [12]},
              {'visual': 'call', 'voice': 'agent', 'from': 270, 'hangupFrame': 360},
              {'visual': 'endcard', 'kind': 'cta', 'from': 380}]
    cues = launch_sfx_cues(scenes, launch_craft(scenes, theme='aura'))
    kinds = [kind for _, kind in cues]
    assert 'swipe' not in kinds and kinds.count('whoosh') == 4
    assert (17 / 30, 'softclick') in cues and (47 / 30, 'softclick') in cues
    assert ((3 + 105) / 30, 'chime') in cues
    assert ((180 + 12 + 4) / 30, 'pop') in cues
    assert 'connect' in kinds and (12.0, 'hangup') in cues


def test_aura_effects_render(tmp_path):
    write_sfx([(0.2, 'whoosh'), (1.0, 'softclick')], tmp_path / 'aura.wav', 2.0)
    samples, channels, seconds = read(tmp_path / 'aura.wav')
    assert channels == 2 and seconds >= 2.0 and max(abs(s) for s in samples) > 300


def test_aura_gates_pass_a_white_field_with_its_glow_but_flag_a_blank_one():
    from PIL import Image, ImageDraw, ImageFilter
    from app.services.marketing_film_gates import AURA_GATES, measure_frame
    field = Image.new('RGB', (1600, 900), (250, 251, 253))
    glow = Image.new('RGB', field.size, (250, 251, 253))
    ImageDraw.Draw(glow).ellipse((-200, 800, 1800, 1400), fill=(167, 195, 255))
    frame = glow.filter(ImageFilter.GaussianBlur(160))
    assert measure_frame(frame, AURA_GATES)['passed']
    assert not measure_frame(frame)['passed']
    assert not measure_frame(field, AURA_GATES)['passed']
