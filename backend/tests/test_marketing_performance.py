import pytest
from types import SimpleNamespace
from app.services.marketing_performance import directed_transcript, performance_profile, assemble_directed_audio, stitch_gaps, HANGUP_HOLD, color_handset_take
from app.services import marketing_video as video
from tests.test_marketing_voice import write_take


def test_pause_tags_preserve_spoken_copy_and_reject_ambiguous_anchors():
    assert directed_transcript('Keep the insight. Protect people.', [{'after':'insight.','milliseconds':240}]) == 'Keep the insight.<break time="240ms"/> Protect people.'
    for text, pause in [('Go. Go.', {'after':'Go.','milliseconds':200}), ('Go.',{'after':'missing','milliseconds':200}), ('Go.',{'after':'Go.','milliseconds':900})]:
        with pytest.raises(ValueError): directed_transcript(text,[pause])


def test_direction_and_voice_override_invalidate_cached_takes(monkeypatch):
    monkeypatch.setattr(video,'voice_settings',lambda:SimpleNamespace(cartesia_model='sonic-3'))
    monkeypatch.setattr(video,'narrator_id',lambda:'voice-one')
    line={'narration':'Where did it go?','performance':{'emotion':'curious','pauses':[{'after':'go?','milliseconds':300}]}}
    profile=performance_profile(line)
    key=video.voice_take_key(line['narration'],profile=profile)
    assert key != video.voice_take_key(line['narration'],profile={**profile,'emotion':'calm'})
    assert key != video.voice_take_key(line['narration'],profile={**profile,'pauses':[]})
    monkeypatch.setattr(video,'narrator_id',lambda:'voice-two')
    assert key != video.voice_take_key(line['narration'],profile=profile)


def test_separate_acting_beats_preserve_word_clock_and_cache(monkeypatch,tmp_path):
    monkeypatch.setattr(video,'voice_settings',lambda:SimpleNamespace(cartesia_model='sonic-3'))
    monkeypatch.setattr(video,'narrator_id',lambda:'voice-one')
    calls=[]
    def speak(text,path,**kw):
        calls.append(kw['profile']['emotion'])
        write_take(path,text,[.1,.4],[.3,.8])
    monkeypatch.setattr(video,'speak',speak)
    film={'scenes':[{'narration':'What happened?','performance':{'emotion':'curious'}},{'narration':'Meet masking.','performance':{'emotion':'enthusiastic'}}]}
    path,words,seconds=assemble_directed_audio(film,tmp_path)
    assert calls==['curious','enthusiastic']
    assert words[2]['start']==pytest.approx(1.24)
    assert seconds==pytest.approx(2.14)
    assert assemble_directed_audio(film,tmp_path)[0]==path
    assert len(calls)==2


def test_provider_pause_markup_never_leaks_into_caption_transcript(monkeypatch,tmp_path):
    config=SimpleNamespace(cartesia_api_key='test',cartesia_model='sonic-3',marketing_cartesia_voice_id='test')
    monkeypatch.setattr(video,'voice_settings',lambda:config)
    requests=[];saved=[]
    def post(url,**kw):
        requests.append(kw['json'])
        return SimpleNamespace(raise_for_status=lambda:None,text='complete fixture')
    monkeypatch.setattr('app.clients.http.post',post)
    monkeypatch.setattr(video,'save_sse_take',lambda response,text,path:saved.append(text))
    text='Where do details go? Meet masking.'
    profile=performance_profile({'narration':text,'performance':{'emotion':'curious','pauses':[{'after':'go?','milliseconds':320}]}})
    video.speak(text,tmp_path/'take.wav',profile=profile)
    assert '<break time="320ms"/>' in requests[0]['transcript']
    assert requests[0]['generation_config']['emotion']=='curious'
    assert saved==[text]


def test_hindi_language_and_explicit_voice_are_sent_and_cached(monkeypatch,tmp_path):
    monkeypatch.setattr(video,'voice_settings',lambda:SimpleNamespace(cartesia_api_key='test',cartesia_model='sonic-3',marketing_cartesia_voice_id='older-config'))
    requests=[]
    monkeypatch.setattr('app.clients.http.post',lambda url,**kw:(requests.append(kw['json']) or SimpleNamespace(raise_for_status=lambda:None,text='fixture')))
    monkeypatch.setattr(video,'save_sse_take',lambda *a:None)
    line={'narration':'जी, चार तीन दो एक।','voice':'customer','language':'hi','voice_id':'4459a9a5-69d6-4680-b970-e13dc51845b6'}
    profile=performance_profile(line)
    video.speak(line['narration'],tmp_path/'hindi.wav',profile=profile)
    assert requests[0]['language']=='hi'
    assert requests[0]['transcript']==line['narration']
    assert requests[0]['voice']==line['voice_id']
    assert 'emotion' not in requests[0]['generation_config']
    assert video.voice_take_key(line['narration'],profile=profile)!=video.voice_take_key(line['narration'],profile={**profile,'language':'en'})
    # Explicit Meera selection overrides stale env config without mutating credentials.
    narrator=performance_profile({'voice':'narrator','voice_id':'a81fccdc-5595-4dfc-ae76-4de6a515b8a2','narration':'Meet the feature.'})
    video.speak('Meet the feature.',tmp_path/'narrator.wav',profile=narrator)
    assert requests[1]['voice']=='a81fccdc-5595-4dfc-ae76-4de6a515b8a2'


def test_lexicon_fixes_pronunciation_without_respelling_copy(monkeypatch,tmp_path):
    monkeypatch.setattr(video,'voice_settings',lambda:SimpleNamespace(cartesia_api_key='test',cartesia_model='sonic-3',marketing_cartesia_voice_id='test'))
    monkeypatch.setattr(video,'pronunciation_lexicon',lambda:{'id':'pdict_terms','items':[
        {'text':'Convin','case_sensitive':True},{'text':'PAN','case_sensitive':True},{'text':'recordings','case_sensitive':False}]})
    requests=[];written=[]
    monkeypatch.setattr('app.clients.http.post',lambda url,**kw:(requests.append(kw['json']) or SimpleNamespace(raise_for_status=lambda:None,text='fixture')))
    monkeypatch.setattr(video,'save_sse_take',lambda response,text,path:written.append(text))
    for line in ['PII Masking by Convin.','A PAN number stays out of the transcript.','In Recordings, details are replaced.']:
        video.speak(line,tmp_path/'take.wav')
    assert [r['pronunciation_dict_id'] for r in requests]==['pdict_terms']*3
    # The spoken transcript is the approved copy; nothing is respelled to coax the model.
    assert [r['transcript'] for r in requests]==written
    # A term only present in lowercase prose must not hijack a case-sensitive entry.
    video.speak('The pan is on the stove.',tmp_path/'take.wav')
    assert 'pronunciation_dict_id' not in requests[3]
    assert video.voice_take_key('A PAN number.')!=video.voice_take_key('A number.')


def test_a_hard_to_say_line_is_rejected_before_it_is_ever_synthesised(monkeypatch):
    import pytest
    monkeypatch.setattr(video,'pronunciation_lexicon',lambda:{'id':'pdict_terms','items':[
        {'text':'PAN','case_sensitive':True},{'text':'recordings','case_sensitive':False}]})
    with pytest.raises(ValueError,match='bare abbreviation'):
        performance_profile({'narration':'A PAN. A credit card number.','voice':'narrator'})
    with pytest.raises(ValueError,match='rushed'):
        performance_profile({'narration':'Into recordings and reports.','voice':'narrator','performance':{'speed':1.1}})
    assert performance_profile({'narration':'A PAN number. Into recordings and reports.','voice':'narrator',
                                'performance':{'speed':1.0}})['speed']==1.0


def test_distinct_cast_is_required_and_identity_survives_language_switch(monkeypatch):
    from app.services.marketing_performance import validate_voice_cast
    monkeypatch.setattr(video,'narrator_id',lambda:video.VOICE_PROFILE['voice_id'])
    agent={'voice':'agent','narration':'Hello, about your application.','language':'en'}
    customer={'voice':'customer','narration':'हिंदी में बात करेंगे?','language':'hi'}
    validate_voice_cast([agent,customer,{**agent,'language':'hi'}])
    with pytest.raises(ValueError,match='distinct voices'):
        validate_voice_cast([agent,{**customer,'voice_id':video.AGENT_VOICE['voice_id']}])
    with pytest.raises(ValueError,match='consistent'):
        validate_voice_cast([agent,{**agent,'voice_id':video.CUSTOMER_VOICE['voice_id'],'language':'hi'}])


def test_dialogue_hands_the_film_to_narration_after_a_hangup_hold(monkeypatch,tmp_path):
    monkeypatch.setattr(video,'voice_settings',lambda:SimpleNamespace(cartesia_model='sonic-3'))
    monkeypatch.setattr(video,'narrator_id',lambda:'voice-one')
    monkeypatch.setattr(video,'speak',lambda text,path,**kw: write_take(path,text,[.1,.4],[.3,.8]))
    assert stitch_gaps([{'voice':'agent'},{'voice':'customer'},{'voice':'narrator'}])==[0.32, HANGUP_HOLD]
    film={'scenes':[{'voice':'agent','narration':'Hello there.','language':'en'},{'voice':'narrator','narration':'Meet masking.'}]}
    _,words,seconds=assemble_directed_audio(film,tmp_path)
    assert words[2]['start']==pytest.approx(1+HANGUP_HOLD+.1)
    assert seconds==pytest.approx(2+HANGUP_HOLD)


def test_customer_handset_line_keeps_duration_and_retimes_the_hash(tmp_path):
    path = tmp_path/'customer.wav'
    write_take(path, 'जी हाँ।', [0.1], [0.4], frames=44100)
    before = path.read_bytes()
    color_handset_take(path)
    import wave, json, hashlib
    with wave.open(str(path), 'rb') as wav:
        assert wav.getnframes() == 44100
        assert wav.getframerate() == 44100
    assert path.read_bytes() != before
    meta = json.loads(path.with_suffix('.timing.json').read_text())
    assert meta['line'] == 'handset'
    assert meta['audio_sha256'] == hashlib.sha256(path.read_bytes()).hexdigest()


def test_explanation_holds_do_not_slow_dialogue_or_misalign_words(monkeypatch,tmp_path):
    monkeypatch.setattr(video,'voice_settings',lambda:SimpleNamespace(cartesia_model='sonic-3'))
    monkeypatch.setattr(video,'narrator_id',lambda:'voice-one')
    monkeypatch.setattr(video,'speak',lambda text,path,**kw: write_take(path,text,[.1,.4],[.3,.8]))
    film={'scenes':[{'narration':'Choose identifiers.','treatment':'select','hold_after':1.6},
                    {'narration':'Protect recordings.','treatment':'audio'}]}
    _,words,seconds=assemble_directed_audio(film,tmp_path)
    assert words[2]['start']==pytest.approx(2.7)
    assert seconds==pytest.approx(3.6)
    with pytest.raises(ValueError,match='hold'):
        stitch_gaps([{'treatment':'select','hold_after':-1},{'treatment':'audio'}])


def test_handset_filter_preserves_quiet_delivery_without_full_scale_normalization(tmp_path):
    import array, math, wave
    path=tmp_path/'quiet.wav'
    write_take(path,'A quiet line.',[.1],[.4],frames=44100)
    pcm=array.array('h',(round(1400*math.sin(i*2*math.pi*600/44100)) for i in range(44100)))
    with wave.open(str(path),'wb') as wav:
        wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(44100);wav.writeframes(pcm.tobytes())
    color_handset_take(path)
    with wave.open(str(path),'rb') as wav:
        after=array.array('h');after.frombytes(wav.readframes(wav.getnframes()))
    assert max(abs(x) for x in after)<2200
    assert len(after)==len(pcm)
