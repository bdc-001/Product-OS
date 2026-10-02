import math
import wave
from array import array

import pytest

from app.services.marketing_score import write_privacy_bed, write_launch_bed, write_score, mix_under_voice, SCORE, LAUNCH, RATE


def pcm(path, seconds, *, stereo=False, amp=8000, freq=220):
    n = int(seconds * RATE)
    samples = array('h')
    for i in range(n):
        value = int(amp * math.sin(2 * math.pi * freq * i / RATE))
        samples.append(value)
        if stereo:
            samples.append(value)
    with wave.open(str(path), 'wb') as handle:
        handle.setnchannels(2 if stereo else 1); handle.setsampwidth(2); handle.setframerate(RATE)
        handle.writeframes(samples.tobytes())


def test_privacy_bed_is_original_stereo_and_covers_the_film(tmp_path):
    path = tmp_path / 'bed.wav'
    info = write_privacy_bed(path, 8)
    assert info['source'] == 'original' and info['version'] == SCORE['version']
    with wave.open(str(path), 'rb') as wav:
        assert wav.getnchannels() == 2 and wav.getframerate() == RATE
        frames = wav.readframes(wav.getnframes())
    peak = max(abs(int.from_bytes(frames[i:i+2], 'little', signed=True)) for i in range(0, len(frames), 2))
    assert wav_duration(path) >= 8 and peak > 1000


def wav_duration(path):
    with wave.open(str(path), 'rb') as wav:
        return wav.getnframes() / wav.getframerate()


def test_score_ducks_when_the_voice_is_present(tmp_path):
    voice, bed, mixed = tmp_path/'voice.wav', tmp_path/'bed.wav', tmp_path/'mix.wav'
    pcm(voice, 1.0, amp=12000, freq=180)
    pcm(bed, 1.0, stereo=True, amp=8000, freq=110)
    mix_under_voice(voice, bed, mixed)
    with wave.open(str(bed), 'rb') as wav:
        music = array('h'); music.frombytes(wav.readframes(wav.getnframes()))
    with wave.open(str(mixed), 'rb') as wav:
        out = array('h'); out.frombytes(wav.readframes(wav.getnframes()))
    # Under a loud voice the bed must contribute less than it does on its own.
    assert max(abs(s) for s in out) < max(abs(s) for s in music) + 12000
    assert wav_duration(mixed) == wav_duration(voice)


def test_launch_bed_is_original_stereo_and_covers_the_film(tmp_path):
    path = tmp_path / 'bed.wav'
    info = write_launch_bed(path, 8)
    assert info['source'] == 'original' and info['version'] == LAUNCH['version']
    with wave.open(str(path), 'rb') as wav:
        assert wav.getnchannels() == 2 and wav.getframerate() == RATE
    assert wav_duration(path) >= 8
    assert write_score('launch-pulse', tmp_path/'named.wav', 8)['version'] == LAUNCH['version']
    with pytest.raises(ValueError, match='Unknown original score'):
        write_score('licensed-library-track', tmp_path/'no.wav', 8)
