import base64
import json
import math

import pytest

from app.services.marketing_voice import align_words, save_sse_take, load_timing, bind_narrated_film, cue_indices, caption_ranges


def timing(text, starts, ends):
    return {'words':text.split(),'start':starts,'end':ends}


def test_alignment_follows_irregular_speech_and_preserves_approved_punctuation():
    result=align_words('Read the prompt. Then test.',timing('Read the prompt Then test',[.1,.3,.55,1.5,1.9],[.25,.4,.8,1.8,2.2]),2.5)
    assert result[3] == {'word':'Then','start':1.5,'end':1.8}
    assert result[2]['word']=='prompt.'
    for change in [dict(words=['Missing']),dict(start=[.1,.3,-1,1.5,1.9]),dict(end=[.25,.4,math.inf,1.8,2.2])]:
        with pytest.raises(ValueError): align_words('Read the prompt. Then test.',{**timing('Read the prompt Then test',[.1,.3,.55,1.5,1.9],[.25,.4,.8,1.8,2.2]),**change},2.5)


def sse(*events):
    return '\n\n'.join('data: '+json.dumps(event) for event in events)+'\n\n'


def test_audio_and_timing_are_saved_together_and_stale_timing_is_rejected(tmp_path):
    path=tmp_path/'take.wav'
    chunk={'type':'chunk','data':base64.b64encode(b'\x01\x00'*44100).decode()}
    stamps={'type':'timestamps','word_timestamps':timing('Hello world',[.1,.4],[.3,.8])}
    for events in [(chunk,stamps),(chunk,{'type':'done'}),(chunk,stamps,{'type':'error'})]:
        with pytest.raises(ValueError): save_sse_take(sse(*events),'Hello world.',path)
        assert not path.exists()
    save_sse_take(sse(chunk,stamps,{'type':'done'}),'Hello world.',path)
    words,seconds=load_timing(path,'Hello world.')
    assert seconds==1 and words[-1]['end']==.8
    path.write_bytes(path.read_bytes()+b'changed')
    with pytest.raises(ValueError,match='different audio'): load_timing(path,'Hello world.')


def test_continuous_audio_drives_captions_reveals_and_cuts_without_equal_word_estimates():
    scenes=[{'narration':'Read the prompt. Then test.', 'labels':['Prompt','Test'], 'label_cues':['Read','Then']},
            {'narration':'Review the session with your team.', 'labels':[], 'label_cues':[]}]
    text=' '.join(s['narration'] for s in scenes)
    starts=[.1,.3,.55,1.5,1.9,3.1,3.4,3.7,4.,4.3,4.5]
    ends=[.25,.4,.8,1.8,2.2,3.3,3.6,3.9,4.2,4.4,4.8]
    words=align_words(text,timing(text,starts,ends),5.)
    bound,frames=bind_narrated_film(scenes,words,5.)
    assert bound[0]['captions'][1]['from']==48  # The actual pause before "Then" matters.
    assert bound[0]['labelFrames'][1]==40
    assert bound[1]['from']==83  # Cut is in the real inter-sentence pause.
    assert bound[0]['frames']==bound[1]['from']
    assert bound[1]['from']+bound[1]['frames']==frames==165
    for scene in bound:
        assert all(0 <= c['from'] < c['to'] <= scene['frames'] for c in scene['captions'])
    with pytest.raises(ValueError,match='cue'): bind_narrated_film([{**scenes[0],'label_cues':[]},scenes[1]],words,5.)


def test_cues_must_appear_in_order_and_captions_respect_sentence_boundaries():
    words=[{'word':w} for w in 'Pick a scenario. Run your call. Review the session.'.split()]
    assert cue_indices({'labels':['Pick','Run','Review'],'label_cues':['Pick','Run','Review']},words)==[0,3,6]
    assert caption_ranges(words)==[(0,3),(3,6),(6,9)]
    with pytest.raises(ValueError): cue_indices({'labels':['Review','Pick'],'label_cues':['Review','Pick']},words)


def test_captions_break_where_the_voice_breaks_a_long_clause():
    spoken=[{'word':w} for w in 'Read the prompt to see the plan, then inspect the session that happened.'.split()]
    assert [' '.join(w['word'] for w in spoken[a:b]) for a,b in caption_ranges(spoken)] == [
        'Read the prompt to', 'see the plan,', 'then inspect the', 'session that happened.']


def test_final_audio_has_exact_silence_lead_without_reencoding_an_intermediate_track(tmp_path):
    import wave
    from app.services.marketing_voice import pad_narration
    source=tmp_path/'voice.wav';target=tmp_path/'on-film-clock.wav'
    with wave.open(str(source),'wb') as wav:
        wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(1000)
        wav.writeframes(b'\x10\x00'*1000)
    pad_narration(source,target,.1,1.5)
    with wave.open(str(target),'rb') as wav:
        assert wav.getnframes()==1500
        assert wav.readframes(100)==b'\0'*200
        assert wav.readframes(1000)==b'\x10\x00'*1000
        assert wav.readframes(400)==b'\0'*800
    with pytest.raises(ValueError): pad_narration(source,target,.1,1.)


def write_take(path, text, starts, ends, frames=44100):
    import wave
    with wave.open(str(path), 'wb') as wav:
        wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(44100)
        wav.writeframes(b'\x10\x00' * frames)
    path.with_suffix('.timing.json').write_text(json.dumps({
        'source': 'cartesia_word_timestamps', 'transcript': text,
        'words': [{'word': w, 'start': s, 'end': e} for w, s, e in zip(text.split(), starts, ends)],
        'audio_sha256': __import__('hashlib').sha256(path.read_bytes()).hexdigest(),
    }))


def test_example_and_narrator_takes_share_one_clock(tmp_path):
    from app.services.marketing_voice import stitch_takes, load_timing
    first, second, target = tmp_path/'ex.wav', tmp_path/'vo.wav', tmp_path/'film.wav'
    write_take(first, 'Hi Priya.', [0.0, 0.3], [0.2, 0.5], frames=22050)
    write_take(second, 'Meet Sense.', [0.0, 0.25], [0.2, 0.4], frames=22050)
    words, seconds = stitch_takes([(first, 'Hi Priya.'), (second, 'Meet Sense.')], target, gap_seconds=0.2)
    assert [w['word'] for w in words] == ['Hi', 'Priya.', 'Meet', 'Sense.']
    assert words[2]['start'] == pytest.approx(0.7)
    combined, duration = load_timing(target, 'Hi Priya. Meet Sense.')
    assert duration == pytest.approx(seconds) and combined[0]['word'] == 'Hi'


def test_hindi_vowel_marks_are_not_discarded_and_danda_breaks_captions():
    from app.services.marketing_voice import normalized
    assert normalized('की') != normalized('क')
    words=[{'word':w} for w in 'जी, चार तीन दो एक। जानकारी भेज दीजिए।'.split()]
    parts=[' '.join(w['word'] for w in words[a:b]) for a,b in caption_ranges(words)]
    assert parts==['जी,','चार तीन दो एक।','जानकारी भेज दीजिए।']
    text='जी, चार तीन दो एक।'
    assert [w['word'] for w in align_words(text,timing(text,[.1,.3,.5,.7,.9],[.2,.4,.6,.8,1.0]),1.1)]==text.split()


def test_example_panels_and_language_transition_use_actual_speech_clock():
    scenes=[{'voice':'agent','language':'en','narration':'Hello about your application.'},
            {'voice':'customer','language':'hi','narration':'हिंदी में बात करेंगे?'},
            {'voice':'narrator','language':'en','narration':'The value disappears. Meaning stays.',
             'examples':[{'label':'PAN','cue':'disappears'},{'label':'Card','cue':'disappears'}]}]
    words=[]
    for i,scene in enumerate(scenes):
        for j,w in enumerate(scene['narration'].split()):words.append({'word':w,'start':i*3+j*.4,'end':i*3+j*.4+.3})
    bound,_=bind_narrated_film(scenes,words,9.0)
    assert bound[1]['languageFrom']=='en'
    assert bound[2]['languageFrom'] is None
    expected=round(words[10]['start']*30)+3-bound[2]['from']
    assert bound[2]['exampleFrames']==[expected,expected]


def test_stitch_accepts_a_gap_per_join(tmp_path):
    from app.services.marketing_voice import stitch_takes
    first, second, target = tmp_path/'a.wav', tmp_path/'b.wav', tmp_path/'out.wav'
    write_take(first, 'Hi Priya.', [0.0, 0.3], [0.2, 0.5], frames=22050)
    write_take(second, 'Meet Sense.', [0.0, 0.25], [0.2, 0.4], frames=22050)
    words, _ = stitch_takes([(first, 'Hi Priya.'), (second, 'Meet Sense.')], target, gap_seconds=[1.75])
    assert words[2]['start'] == pytest.approx(2.25)


def test_call_scenes_hand_off_with_a_hangup_flag():
    scenes=[
        {'voice':'agent','visual':'call','treatment':'call-agent','narration':'Hello I am calling about your card now.'},
        {'voice':'customer','visual':'call','treatment':'call-customer','narration':'Please take this number after we speak.'},
        {'voice':'narrator','visual':'statement','treatment':'shared','narration':'Those details now travel after the call ends.'},
    ]
    words=[]; t=0.0
    for scene in scenes:
        for w in scene['narration'].split():
            words.append({'word':w,'start':t,'end':t+.28}); t+=.35
        t+=.2
    bound,_=bind_narrated_film(scenes,words,t+.5)
    assert not bound[0].get('endsCall')
    assert bound[1]['endsCall'] is True
    assert bound[2]['transitionFrom']=='call'
