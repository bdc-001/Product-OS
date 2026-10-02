import math
import wave
from array import array
from pathlib import Path
from typing import get_args

import pytest

from app.services.marketing_content import UiScreen, Video, VoicePerformance
from app.services.marketing_film_gates import LAUNCH_BACKGROUNDS, LAUNCH_LAYOUTS, LAUNCH_THEMES, launch_craft, launch_layouts, launch_theme
from app.services.marketing_performance import LAUNCH_GAPS, gap_between, narration_passages, performance_profile
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


def test_calls_and_screens_hold_one_field_and_the_film_closes_on_brand():
    scenes = [{'visual': 'volume'}, {'visual': 'kinetic', 'kind': 'problem'}, {'visual': 'call'}, {'visual': 'call'},
              {'visual': 'kinetic', 'kind': 'benefit'}, {'visual': 'ui'}, {'visual': 'ui'}, {'visual': 'endcard'}]
    fields = [c['field'] for c in launch_craft(scenes)]
    assert fields == ['dark', 'light', 'stage', 'stage', 'brand', 'brand', 'brand', 'brand']
    assert {c['transition'] for c in launch_craft(scenes)} >= {'slide', 'wipe', 'fade', 'push'}


def test_back_to_back_type_cards_alternate_off_brand_blue():
    scenes = [{'visual': 'kinetic', 'kind': 'benefit'}, {'visual': 'ui'}, {'visual': 'kinetic', 'kind': 'benefit'},
              {'visual': 'orbit'}, {'visual': 'kinetic', 'kind': 'benefit'}, {'visual': 'kinetic', 'kind': 'benefit'},
              {'visual': 'endcard'}]
    assert [c['field'] for c in launch_craft(scenes)] == ['light', 'brand', 'light', 'dark', 'brand', 'light', 'brand']


def test_every_theme_draws_one_on_brand_background_per_field_and_uses_all_twelve():
    source = (Path(__file__).resolve().parents[2] / 'Sense_Communication/remotion/src/marketing/launch/core.tsx').read_text()
    used = set()
    for name, plan in LAUNCH_THEMES.items():
        assert set(plan['bg']) == set(LAUNCH_BACKGROUNDS), name
        for field, bg in plan['bg'].items():
            assert bg in LAUNCH_BACKGROUNDS[field], (name, field, bg)
            used.add(bg)
    every = {bg for options in LAUNCH_BACKGROUNDS.values() for bg in options}
    assert len(every) == 12 and used == every
    assert all(f'"{bg}"' in source for bg in every)
    assert set(get_args(get_args(Video.model_fields['look'].annotation)[0])) == set(LAUNCH_THEMES)


def test_a_film_keeps_one_seeded_theme_unless_the_look_is_pinned():
    film = {'title': 'Campaign Health: See How Much Effort Each Lead Really Takes'}
    assert launch_theme(film) == launch_theme(dict(film)) in LAUNCH_THEMES
    assert launch_theme({**film, 'look': 'night'}) == 'night'
    assert launch_theme({'title': ''}) == 'daylight'
    titles = [f'Feature {i}: launch film' for i in range(40)]
    assert len({launch_theme({'title': t}) for t in titles}) == len(LAUNCH_THEMES)


def test_themes_move_type_and_product_but_keep_calls_scale_and_close_in_role():
    scenes = [{'visual': 'volume'}, {'visual': 'kinetic', 'kind': 'problem'}, {'visual': 'call'}, {'visual': 'ui'},
              {'visual': 'kinetic', 'kind': 'benefit'}, {'visual': 'endcard'}]
    night = launch_craft(scenes, 'night')
    assert [c['field'] for c in night] == ['dark', 'dark', 'stage', 'dark', 'brand', 'brand']
    assert [c['bg'] for c in night] == ['ink', 'ink', 'stage', 'ink', 'deep', 'deep']
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
        beat('hook', 'kinetic', 'Hundreds of calls, all fine', 'Hundreds of calls go out today, and every one sounds fine.'),
        beat('problem', 'volume', 'A callback that never comes', 'Until a customer asks for a callback that never comes.'),
        beat('problem', 'kinetic', 'Nobody on the team heard it', 'Nobody on the team heard it.'),
        beat('problem', 'volume', 'Gone by Monday', 'By Monday, that customer has already moved on to someone else.'),
        beat('proof', 'kinetic', 'Introducing Agent Monitoring', 'Introducing Agent Monitoring by Acme.'),
        beat('proof', 'orbit', 'The missed promise, flagged', 'It flags the call where a callback was promised, and missed.',
             labels=['Callback promised', 'Missed'], label_cues=['callback was promised', 'missed']),
        beat('benefit', 'kinetic', 'Called back the same day', 'Your team lead hears it that afternoon, and calls back the same day.'),
        beat('cta', 'endcard', 'Every call, finally heard', 'Every call, finally heard.'),
    ]
    return {'title': 'Agent Monitoring by Acme', 'filmKind': 'launch', 'scenes': scenes,
            'body': 'A callback promised on a call and never made. See how Agent Monitoring flags the missed promise so your team can act the same day.', **changes}


def test_launch_films_tell_a_story_and_keep_the_feature_brief():
    from app.services.marketing_content import Video
    film = story_film()
    Video.model_validate(film)
    orbit = film['scenes'][5]
    with pytest.raises(ValueError, match='three feature shots'):
        Video.model_validate({**film, 'scenes': [*film['scenes'][:5], orbit, film['scenes'][6], {**orbit, 'headline': 'Second orbit'},
                                                  {**orbit, 'headline': 'Third orbit'}, {**orbit, 'headline': 'Fourth orbit'}, film['scenes'][7]]})
    with pytest.raises(ValueError, match='three shots on the situation'):
        Video.model_validate({**film, 'scenes': [film['scenes'][0], orbit, *film['scenes'][1:5], film['scenes'][6], film['scenes'][7]]})
    with pytest.raises(ValueError, match='a third of the spoken words'):
        long = {**orbit, 'narration': 'It flags every call where a callback was promised, missed, and routes it to your lead.'}
        Video.model_validate({**film, 'scenes': [*film['scenes'][:5], long, {**long, 'headline': 'Routed to the lead'}, *film['scenes'][6:]]})


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
    source = (Path(__file__).resolve().parents[2] / 'Sense_Communication/remotion/src/marketing/launch/ScaleShots.tsx').read_text()
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
