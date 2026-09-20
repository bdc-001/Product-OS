import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services import marketing_video as video
from app.services.marketing_content import Scene, validate_format


SPOKEN = ['Your agent opens well, but what happens when the conversation turns?',
          'Run a realistic test, then inspect the session it produced.',
          'Read the transcript, hear the recording, and check the events.',
          'Test the call first.']


def scene(**changes):
    return dict(kind='proof', visual='steps', headline='Inspect the test conversation', body='Review the session before your next decision.',
                narration='Run a realistic test and inspect the resulting conversation before making your next decision.',
                evidence='Agent Testing supports a web or phone test and inspecting the test session.',
                labels=['Run the test', 'Inspect the session'], visual_reason='Ordered actions explain the supported test and review workflow.', **changes)


def film(lines):
    visuals = ['conversation', 'statement', 'contrast', 'spotlight']
    scenes = []
    for i in range(10):
        visual = visuals[i % 4]
        labels = [] if visual == 'statement' else ['One supported takeaway'] if visual == 'spotlight' else ['Run the test', 'Inspect the session']
        scenes.append({**scene(), 'kind': 'hook' if i == 0 else 'cta' if i == 9 else 'proof',
                       'narration': lines[i % len(lines)], 'headline': f'Inspect the supported session {i}',
                       'visual': visual, 'labels': labels})
    return {'title':'Agent Testing', 'body':'A useful channel description about running a test and reviewing its actual session before making a publishing decision.', 'scenes': scenes}


def test_new_visuals_have_bounded_visible_labels_and_real_emphasis():
    raw = scene()
    raw.update(visual='conversation', emphasis='test conversation')
    assert Scene.model_validate(raw).emphasis == 'test conversation'
    for change in ({'emphasis': 'guaranteed results'}, {'visual': 'statement'}, {'visual': 'contrast', 'labels': ['One', 'Two', 'Three']}):
        with pytest.raises(ValueError): Scene.model_validate({**raw, **change})


def test_launch_film_opens_on_a_lived_example_and_varies_shots():
    raw = film(SPOKEN)
    raw['scenes'][0].update(visual='statement', labels=[])
    with pytest.raises(ValueError, match='lived example'):
        validate_format('youtube_landscape_video', raw)
    raw['scenes'][0].update(visual='conversation', labels=['Run the test', 'Inspect the session'])
    assert len(validate_format('youtube_landscape_video', raw)['scenes']) == 10
    call = Scene.model_validate({**scene(), 'visual': 'call', 'voice': 'example',
                                 'labels': ['This is Priya Sharma.', 'Account ending 4412.']})
    assert call.visual == 'call'
    with pytest.raises(ValueError, match='example voice'):
        Scene.model_validate({**scene(), 'voice': 'example'})
    detect = Scene.model_validate({**scene(), 'visual': 'detect', 'voice': 'agent',
                                   'narration': 'Before I proceed, confirm the mobile number now.',
                                   'labels': ['Before I proceed', 'Mobile number'],
                                   'label_cues': ['Before I proceed', 'mobile number']})
    assert detect.voice == 'agent'
    with pytest.raises(ValueError, match='example voice'):
        Scene.model_validate({**scene(), 'voice': 'customer'})


def test_pii_launch_storyboard_is_a_valid_film():
    from pathlib import Path
    from app.config import ROOT
    raw = json.loads((ROOT / 'output/marketing/pii-masking/launch-storyboard.json').read_text())
    video = validate_format('youtube_landscape_video', raw)
    assert video['scenes'][0]['voice'] == 'agent' and video['scenes'][1]['voice'] == 'customer'
    assert {'call', 'detect', 'collect', 'spread', 'flow', 'mask', 'split'} <= {s['visual'] for s in video['scenes']}


def test_agent_and_customer_voices_select_their_profiles():
    assert video.scene_profile({'voice': 'agent'})['name'] == 'Arushi'
    assert video.scene_profile({'voice': 'customer'})['name'] == 'Kabir'
    assert video.scene_profile({'voice': 'example'})['name'] == 'Maya'
    assert video.scene_profile({'voice': 'narrator'})['name'] == 'Siya'


def test_tts_omits_presenter_emotion_and_hindi_tags():
    assert video.tts_generation_config({'speed': 1, 'emotion': 'confident', 'language': 'en'}) == {'speed': 1}
    assert video.tts_generation_config({'speed': 0.96, 'emotion': 'calm', 'language': 'en'}) == {'speed': 0.96, 'emotion': 'calm'}
    assert video.tts_generation_config({'speed': 1, 'emotion': 'content', 'language': 'hi'}) == {'speed': 1}


def test_a_film_of_same_length_statements_never_reaches_the_narrator():
    with pytest.raises(ValueError, match='average at least 7 words'):
        validate_format('youtube_landscape_video', film(['Pick a scenario. Run the call. Review it.']))
    with pytest.raises(ValueError, match='11 or more words'):
        validate_format('youtube_landscape_video', film(['Run a realistic test, then inspect it.']))
    with pytest.raises(ValueError, match='comma or colon'):
        validate_format('youtube_landscape_video', film(['Run a realistic test and inspect the session it produced before you publish.',
                                                         'Test the call first.']))
    assert validate_format('youtube_landscape_video', film(SPOKEN))['scenes'][0]['narration'] == SPOKEN[0]


def test_timing_leaves_readable_holds_and_reveals_within_voice_take():
    bound = video.bind_scene(scene(), 5.1, 150)
    assert bound['from'] == 150
    assert bound['frames'] % 3 == 0
    assert 6 <= bound['frames'] - bound['captions'][-1]['to'] <= 9
    assert bound['audioFrom'] == bound['captions'][0]['from']
    assert bound['labelFrames'][0] < bound['labelFrames'][1] < bound['audioFrames']
    with pytest.raises(ValueError): video.bind_scene({**scene(), 'narration':''}, 4, 0)


def test_fast_edits_keep_complete_voice_and_reject_a_lingering_take():
    for seconds in [1.9, 3.41, 4.89, 7.5]:
        timed = video.bind_scene(scene(), seconds, 0)
        assert timed['frames'] >= timed['audioFrom'] + timed['audioFrames'] + 6
        assert timed['labelFrames'][-1] + 25 < timed['frames']
        assert max(len(c['text'].split()) for c in timed['captions']) <= 4
    with pytest.raises(ValueError): video.bind_scene(scene(), 8, 0)


def test_production_voice_requests_directed_delivery_and_invalidates_old_takes(monkeypatch, tmp_path):
    config = SimpleNamespace(cartesia_api_key='test-key', cartesia_voice_id='test-voice', marketing_cartesia_voice_id='test-voice', cartesia_model='sonic-3')
    monkeypatch.setattr(video, 'voice_settings', lambda: config)
    requests = []
    def post(url, **kwargs):
        requests.append(kwargs)
        return SimpleNamespace(raise_for_status=lambda: None, text='SSE fixture')
    monkeypatch.setattr('app.clients.http.post', post)
    monkeypatch.setattr(video, 'save_sse_take', lambda response, text, path: path.write_bytes(b'voice-take'))
    video.speak('Test the conversation before you publish.', tmp_path/'voice.wav')
    assert requests[0]['json']['generation_config'] == {'speed': 0.98}
    assert 'emotion' not in requests[0]['json']['generation_config']
    assert requests[0]['json']['voice'] == 'test-voice'
    assert requests[0]['json']['add_timestamps'] is True
    video.speak('Hi, this is Priya Sharma.', tmp_path/'example.wav', profile=video.EXAMPLE_VOICE)
    assert requests[1]['json']['voice'] == video.EXAMPLE_VOICE['voice_id']
    assert (tmp_path/'voice.wav').read_bytes() == b'voice-take'
    key = video.voice_take_key('Test the conversation before you publish.')
    monkeypatch.setitem(video.VOICE_PROFILE, 'speed', 1.2)
    assert video.voice_take_key('Test the conversation before you publish.') != key


def test_narration_allows_punchy_reveals_but_rejects_long_monologues():
    assert Scene.model_validate({**scene(), 'narration': 'Meet your next test conversation.'})
    with pytest.raises(ValueError, match='4-16'):
        Scene.model_validate({**scene(), 'narration': ' '.join(['word'] * 17)})


def test_production_never_silently_uses_system_voice(monkeypatch, tmp_path):
    monkeypatch.setattr(video, 'voice_settings', lambda: SimpleNamespace(cartesia_api_key='',cartesia_voice_id=''))
    monkeypatch.setattr(video, 'run', lambda *a, **kw: pytest.fail('No system voice for production'))
    with pytest.raises(RuntimeError,match='production narration'): video.speak('Approved narration',tmp_path/'voice.wav')


def test_explicit_preview_never_calls_configured_cloud_voice(monkeypatch,tmp_path):
    monkeypatch.setattr(video, 'voice_settings', lambda: SimpleNamespace(cartesia_api_key='configured',cartesia_voice_id='configured'))
    monkeypatch.setattr(video.shutil,'which',lambda _: '/usr/bin/say')
    monkeypatch.setattr('app.clients.http.post',lambda *a, **kw: pytest.fail('No external narration for local preview'))
    calls=[]
    monkeypatch.setattr(video,'run',lambda args, **kw: calls.append(args))
    video.speak('Approved narration',tmp_path/'voice.wav',preview=True)
    assert calls[0][0] == '/usr/bin/say'


def master():
    return {'streams':[{'codec_type':'video','codec_name':'h264','pix_fmt':'yuv420p','r_frame_rate':'30/1','width':1920,'height':1080}, {'codec_type':'audio'}], 'format':{'duration':'60'}}


def test_cached_master_is_validated_for_actual_aspect_audio_and_duration():
    video.validate_master(master(),'landscape',60)
    with pytest.raises(ValueError,match='resolution'): video.validate_master(master(),'portrait',60)
    with pytest.raises(ValueError,match='duration'): video.validate_master(master(),'landscape',45)
    info=master();info['streams'].pop()
    with pytest.raises(ValueError,match='audio'): video.validate_master(info,'landscape',60)


def test_encoded_silent_or_clipping_audio_fails(monkeypatch,tmp_path):
    monkeypatch.setattr(video,'binary',lambda _: '/tmp/ffmpeg')
    def measured(loudness,peak):
        monkeypatch.setattr(video.subprocess,'run',lambda *a,**kw: SimpleNamespace(returncode=0,stderr=json.dumps({'input_i':loudness,'input_tp':peak})))
    measured('-16.2','-1.6')
    assert video.measure_audio(tmp_path/'video.mp4')['integrated_lufs']==-16.2
    for loudness,peak in [('-inf','-inf'),('-16','0.2'),('-30','-3')]:
        measured(loudness,peak)
        with pytest.raises(ValueError,match='loudness'): video.measure_audio(tmp_path/'video.mp4')


def test_sense_storyboard_leads_film_design_references():
    from app.services.marketing_quality import video_references
    names=[item['name'] for item in video_references()]
    assert names[0]=='convin-sense-board'
    assert 'conversation' in names and 'signal-flow' in names


def test_video_review_samples_entry_middle_and_late_frames(monkeypatch,tmp_path):
    from PIL import Image
    from app.services import marketing_quality as quality
    monkeypatch.setattr(video,'video_cache_key',lambda _: 'current-render')
    monkeypatch.setattr(video,'binary',lambda _: '/tmp/ffmpeg')
    captures=[]
    def capture(args):
        captures.append(float(args[args.index('-ss')+1]))
        from PIL import Image
        img = Image.new('RGB', (320, 180))
        pix = img.load()
        for y in range(180):
            for x in range(320):
                tone = x / 320
                pix[x, y] = (int(26 + 180 * tone), int(40 + y / 6), int(242 - 120 * tone))
                if (x - 80) ** 2 + (y - 90) ** 2 < 40 ** 2:
                    pix[x, y] = (26, 98, 242)
        img.save(args[-1])
    monkeypatch.setattr(video,'run',capture)
    monkeypatch.setattr(quality,'video_references',lambda: [])
    monkeypatch.setattr(quality,'chat_json',lambda *a,**kw: dict(passed=True,issues=[],legibility=5,hierarchy=5,visual_usefulness=5,rationale='All three sampled phases show readable typography and a clear feature-specific visual relationship.'))
    folder=tmp_path/'youtube_short/current-render';folder.mkdir(parents=True)
    (folder/'render-props.json').write_text(json.dumps({'scenes':[{'from':0,'frames':150},{'from':150,'frames':180}]}))
    (tmp_path/'short.mp4').write_bytes(b'fixture')
    quality.review_rendered('youtube_short',{'title':'Agent Testing'},tmp_path,[('short.mp4','video/mp4')])
    assert captures == [0.8,2.5,4.7,5.8,8.0,10.7]
    report=json.loads((tmp_path/'youtube_short-visual-review.json').read_text())
    assert report['reviewed_images']==6


def test_wrong_frame_rate_cannot_pass_delivery_checks():
    info = master(); info['streams'][0]['r_frame_rate']='24/1'
    with pytest.raises(ValueError,match='frame-rate'): video.validate_master(info,'landscape',60)


def test_render_cache_changes_when_the_voice_changes(monkeypatch):
    config = SimpleNamespace(cartesia_voice_id='first-voice',cartesia_model='model')
    monkeypatch.setattr(video,'voice_settings',lambda:config)
    first=video.video_cache_key({'title':'Agent Testing','scenes':[scene()]})
    config.cartesia_voice_id='second-voice'
    assert video.video_cache_key({'title':'Agent Testing','scenes':[scene()]}) != first


def test_feature_examples_require_real_changes_and_exact_narration_cues():
    from app.services.marketing_content import content_units
    ex={'label':'PAN','before':'ABCDE1234F','after':'[PAN Number]','context':'Complete the application.','cue':'disappears','evidence':'Selected transcript values become semantic labels.'}
    raw={**scene(),'visual':'mask','labels':[],'narration':'The value disappears, while the conversation keeps its meaning.','examples':[ex]}
    model=Scene.model_validate(raw)
    assert model.examples[0].after=='[PAN Number]'
    units=content_units({'title':'PII Masking','body':'Approved body','scenes':[model.model_dump()]})
    assert '[PAN Number]' in units['scenes[0]'] and 'Complete the application.' in units['scenes[0]']
    with pytest.raises(ValueError,match='meaningful change'):
        Scene.model_validate({**raw,'examples':[{**ex,'after':ex['before']}]})
    with pytest.raises(ValueError,match='cue'):
        Scene.model_validate({**raw,'examples':[{**ex,'cue':'never spoken'}]})


def test_film_uses_production_motion_packages():
    pkg = json.loads((video.REMOTION_DIR / 'package.json').read_text())
    for name in ['@remotion/lottie', '@remotion/shapes', '@remotion/paths', '@remotion/motion-blur']:
        assert pkg['dependencies'][name] == '4.0.504'
    motifs = (video.REMOTION_DIR / 'src/marketing/Motifs.tsx').read_text()
    film = (video.REMOTION_DIR / 'src/marketing/Film.tsx').read_text()
    launch = (video.REMOTION_DIR / 'src/marketing/PiiLaunch.tsx').read_text()
    world = (video.REMOTION_DIR / 'src/marketing/World.tsx').read_text()
    assert '@remotion/lottie' in motifs and 'Trail' in motifs and 'evolvePath' in motifs and 'makeArrow' in motifs
    assert 'from "./Motifs"' in film and 'from "./Motifs"' in launch
    assert 'FilmRoot' in film and 'PersistentWorld' in world and 'SceneLayer' in film
    assert 'background: "transparent"' in film
    assert 'World.tsx' in Path(video.__file__).read_text()
    assert 'Motifs.tsx' in Path(video.__file__).read_text()


def test_example_layout_also_accepts_non_privacy_feature_comparisons():
    examples=[{'label':'Opening','before_label':'Expected','after_label':'Observed','before':'Ask preferred language','after':'Customer requests Hindi','context':'Inspect the actual test session.','cue':'observed response','evidence':'Agent Testing supports inspecting the test conversation and transcript.'},
              {'label':'Follow-up','before_label':'Expected','after_label':'Observed','before':'Offer a follow-up call','after':'Customer requests email','context':'Review the customer reply.','cue':'observed response','evidence':'Agent Testing supports inspecting the session and its responses.'}]
    raw={**scene(),'visual':'contrast','labels':[],'narration':'Compare the expected step with the observed response, then review the full session.','examples':examples}
    actual=Scene.model_validate(raw)
    assert actual.examples[0].after_label=='Observed'
    assert len(actual.examples)==2
