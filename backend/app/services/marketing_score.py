"""Original in-process scores for launch films. No third-party samples or licensed tracks."""
from __future__ import annotations

import array
import math
import wave
from pathlib import Path

SCORE = {"version": "privacy-pad-v1", "bpm": 80, "key": "A minor"}
LAUNCH = {"version": "launch-pulse-v1", "bpm": 120, "key": "D minor"}
RATE = 44100
TABLE = 4096
SINE = [math.sin(2 * math.pi * i / TABLE) for i in range(TABLE)]
CHORDS = {
    "Am": (110.00, 220.00, 261.63, 329.63),
    "F": (174.61, 220.00, 261.63, 349.23),
    "C": (130.81, 164.81, 196.00, 261.63),
    "G": (196.00, 246.94, 293.66, 392.00),
    "Em": (164.81, 196.00, 246.94, 329.63),
}
# Dark setup, lift into the product, steady demo, warmer close.
BARS = (
    "Am", "F", "Am", "Em",
    "Am", "F", "Am", "G",
    "F", "C",
    "Am", "F", "C", "G",
    "Am", "F", "C", "G",
    "F", "C", "G", "Am",
    "F", "C", "C",
)
MELODY = (
    (9.0, 4.5, 329.63, 0.045),
    (24.2, 2.2, 392.00, 0.055),
    (26.6, 3.4, 440.00, 0.06),
    (54.5, 3.0, 349.23, 0.04),
    (66.2, 3.8, 523.25, 0.05),
    (70.0, 4.0, 440.00, 0.055),
)
LAUNCH_CHORDS = {
    "Dm": (73.42, 146.83, 220.00, 293.66, 349.23),
    "Bb": (58.27, 116.54, 174.61, 233.08, 349.23),
    "F": (87.31, 174.61, 220.00, 261.63, 349.23),
    "C": (65.41, 130.81, 196.00, 261.63, 329.63),
    "Gm": (98.00, 196.00, 233.08, 293.66, 392.00),
}
LAUNCH_LOOP = ("Dm", "Bb", "F", "C", "Dm", "Gm", "Bb", "C")


def _zeros(n: int) -> array.array:
    return array.array("f", bytes(n * 4))


def _add(buf: array.array, freq: float, start: float, dur: float, amp: float, *,
         attack=0.45, release=0.7, detune=1.0) -> None:
    i0 = max(0, int(start * RATE))
    n = min(int(dur * RATE), len(buf) - i0)
    if n <= 0 or amp <= 0:
        return
    step = freq * detune * TABLE / RATE
    att = max(1, int(attack * RATE))
    rel = max(1, int(release * RATE))
    phase = 0.0
    for i in range(n):
        env = (i / att if i < att else 1.0) * (1.0 if n - i >= rel else (n - i) / rel)
        buf[i0 + i] += amp * env * SINE[int(phase) % TABLE]
        phase += step


def _sweep(buf: array.array, start: float, dur: float, f0: float, f1: float, amp: float, decay=10.0) -> None:
    i0 = max(0, int(start * RATE))
    n = min(int(dur * RATE), len(buf) - i0)
    if n <= 0 or amp <= 0:
        return
    phase = 0.0
    click = max(1, int(0.002 * RATE))
    for i in range(n):
        p = i / n
        env = amp * math.exp(-p * decay) * (i / click if i < click else 1.0)
        buf[i0 + i] += env * math.sin(phase)
        phase += 2 * math.pi * (f0 + (f1 - f0) * p) / RATE


def _finish(left: array.array, right: array.array, path: Path, meta: dict, *,
            fade_in: float, fade_out: float, peak: float) -> dict:
    n = len(left)
    inn, out = int(fade_in * RATE), int(fade_out * RATE)
    for i in range(min(inn, n)):
        w = i / inn
        left[i] *= w; right[i] *= w
    for i in range(min(out, n)):
        w = i / out
        left[n - 1 - i] *= w; right[n - 1 - i] *= w
    loud = max(max(abs(s) for s in left), max(abs(s) for s in right), 1e-6)
    scale = peak / loud
    pcm = array.array("h")
    for a, b in zip(left, right):
        pcm.append(max(-32767, min(32767, int(a * scale * 32767))))
        pcm.append(max(-32767, min(32767, int(b * scale * 32767))))
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(2); wav.setsampwidth(2); wav.setframerate(RATE)
        wav.writeframes(pcm.tobytes())
    return {**meta, "seconds": n / RATE, "source": "original"}


def write_privacy_bed(path: Path, seconds: float) -> dict:
    """Stereo pad + sparse melody, written as 44.1 kHz PCM."""
    if seconds < 8:
        raise ValueError("A score needs a full film duration.")
    n = int((seconds + 0.4) * RATE)
    left, right = _zeros(n), _zeros(n)
    bar = 60 / SCORE["bpm"] * 4
    t = 0.0
    for name in BARS:
        if t >= seconds:
            break
        amp = 0.11 if t < 24 else 0.14 if t < 54 else 0.12
        for i, freq in enumerate(CHORDS[name]):
            voice = amp * (0.85 if i == 0 else 0.55)
            _add(left, freq, t, bar + 0.12, voice, detune=0.998)
            _add(right, freq, t, bar + 0.12, voice, detune=1.002)
        t += bar
    for start, dur, freq, amp in MELODY:
        _add(left, freq, start, dur, amp, attack=0.25, release=0.9, detune=0.999)
        _add(right, freq, start, dur, amp, attack=0.25, release=0.9, detune=1.001)
    return _finish(left, right, path, SCORE, fade_in=0.6, fade_out=2.6, peak=0.38)


def write_launch_bed(path: Path, seconds: float) -> dict:
    """Driving D-minor pulse for launch films: kick, offbeat stabs, moving bass."""
    if seconds < 8:
        raise ValueError("A score needs a full film duration.")
    n = int((seconds + 0.4) * RATE)
    left, right = _zeros(n), _zeros(n)
    bpm = LAUNCH["bpm"]
    beat, bar = 60 / bpm, 60 / bpm * 4
    t = 0.0
    bar_i = 0
    while t < seconds:
        name = LAUNCH_LOOP[bar_i % len(LAUNCH_LOOP)]
        tones = LAUNCH_CHORDS[name]
        root, fifth, third = tones[0], tones[2], tones[3]
        lift = 0.0 if t < 4 else 1.0
        close = 0.55 if t > seconds - 6 else 1.0
        for b in range(4):
            hit = t + b * beat
            _sweep(left, hit, 0.15, 102, 40, 0.7 * close, 11)
            _sweep(right, hit, 0.15, 98, 38, 0.64 * close, 11)
            _add(left, root, hit, 0.36, 0.2 * close, attack=0.004, release=0.22, detune=0.998)
            _add(right, root * 2, hit, 0.3, 0.09 * close, attack=0.004, release=0.2, detune=1.002)
            if b in (1, 3) and lift:
                _add(left, 196.00, hit, 0.08, 0.16 * close, attack=0.001, release=0.05)
                _add(right, 233.08, hit, 0.08, 0.14 * close, attack=0.001, release=0.05)
                _add(left, 392.00, hit, 0.05, 0.07 * close, attack=0.001, release=0.04)
            for eighth in (0.0, 0.5):
                hat = hit + eighth * beat
                _add(left, 6200, hat, 0.03, (0.028 if eighth else 0.04) * lift * close,
                     attack=0.0006, release=0.02, detune=0.996)
                _add(right, 7400, hat, 0.03, (0.024 if eighth else 0.036) * lift * close,
                     attack=0.0006, release=0.02, detune=1.004)
            if lift:
                off = hit + beat * 0.5
                _add(left, third, off, 0.16, 0.09 * close, attack=0.006, release=0.1, detune=0.999)
                _add(right, fifth, off, 0.16, 0.08 * close, attack=0.006, release=0.1, detune=1.001)
                _add(left, tones[-1], off, 0.14, 0.05 * close, attack=0.006, release=0.09)
        if lift:
            for i, freq in enumerate(tones[1:]):
                voice = 0.045 * close * (0.7 if i else 1.0)
                _add(left, freq, t, bar * 0.92, voice, attack=0.02, release=0.35, detune=0.997)
                _add(right, freq, t, bar * 0.92, voice, attack=0.02, release=0.35, detune=1.003)
        if t >= 16 and t < seconds - 8:
            steps = (tones[1], tones[2], tones[3], tones[2])
            for s, freq in enumerate(steps * 2):
                note = t + s * (beat / 2)
                _add(left, freq * 2, note, 0.12, 0.045 * close, attack=0.008, release=0.08, detune=0.999)
                _add(right, freq * 2, note, 0.12, 0.04 * close, attack=0.008, release=0.08, detune=1.001)
        t += bar
        bar_i += 1
    return _finish(left, right, path, LAUNCH, fade_in=0.12, fade_out=1.8, peak=0.42)


def write_score(kind: str, path: Path, seconds: float) -> dict:
    if kind in {SCORE["version"], "privacy-pad"}:
        return write_privacy_bed(path, seconds)
    if kind in {LAUNCH["version"], "launch-pulse"}:
        return write_launch_bed(path, seconds)
    raise ValueError("Unknown original score.")


def _read(path: Path) -> tuple[int, int, list[float]]:
    with wave.open(str(path), "rb") as wav:
        channels, width, rate, frames = wav.getnchannels(), wav.getsampwidth(), wav.getframerate(), wav.getnframes()
        raw = array.array("h"); raw.frombytes(wav.readframes(frames))
    if width != 2:
        raise ValueError("Score mixing expects 16-bit PCM.")
    samples = [s / 32768 for s in raw]
    if channels == 1:
        samples = [v for s in samples for v in (s, s)]
    return rate, 2, samples


def mix_under_voice(voice: Path, bed: Path, target: Path, *, music_gain: float = 0.4) -> None:
    """Keep Siya in front: duck the bed when she speaks."""
    rate, _, spoken = _read(voice)
    bed_rate, _, music = _read(bed)
    if rate != RATE or bed_rate != RATE:
        raise ValueError("Voice and score must both be 44.1 kHz.")
    n = len(spoken)
    if len(music) < n:
        music = music + [0.0] * (n - len(music))
    follow = 0.0
    attack = 1 - math.exp(-1 / (0.04 * RATE))
    release = 1 - math.exp(-1 / (0.45 * RATE))
    mixed = array.array("h")
    for i in range(0, n, 2):
        level = math.sqrt((spoken[i] ** 2 + spoken[i + 1] ** 2) / 2)
        follow += (attack if level > follow else release) * (level - follow)
        duck = 0.22 + 0.78 / (1 + (follow / 0.018) ** 2)
        for side in (0, 1):
            sample = spoken[i + side] + music[i + side] * music_gain * duck
            mixed.append(max(-32767, min(32767, int(sample * 32767))))
    with wave.open(str(target), "wb") as wav:
        wav.setnchannels(2); wav.setsampwidth(2); wav.setframerate(RATE)
        wav.writeframes(mixed.tobytes())
