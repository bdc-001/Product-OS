"""Original in-process scores for launch films. No third-party samples or licensed tracks."""
from __future__ import annotations

import array
import math
import random
import wave
from pathlib import Path

SCORE = {"version": "privacy-pad-v1", "bpm": 80, "key": "A minor"}
LAUNCH = {"version": "launch-pulse-v1", "bpm": 120, "key": "D minor"}
DRIVE = {"version": "launch-drive-v1", "bpm": 132, "key": "A minor"}
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
DRIVE_CHORDS = {
    "Am": (55.00, 110.00, 220.00, 261.63, 329.63),
    "F": (43.65, 87.31, 174.61, 220.00, 261.63),
    "C": (65.41, 130.81, 196.00, 261.63, 329.63),
    "G": (49.00, 98.00, 196.00, 246.94, 293.66),
}
DRIVE_LOOP = ("Am", "F", "C", "G")


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


def _noise(buf: array.array, rng: random.Random, start: float, dur: float, amp: float, *, decay: float, bright=0.85) -> None:
    i0 = max(0, int(start * RATE))
    n = min(int(dur * RATE), len(buf) - i0)
    prev = 0.0
    for i in range(max(0, n)):
        white = rng.uniform(-1, 1)
        hp = white - prev * bright
        prev = white
        buf[i0 + i] += amp * hp * math.exp(-i / RATE * decay)


def write_drive_bed(path: Path, seconds: float) -> dict:
    """Fast A-minor drive: four-on-the-floor kick, claps on 2 and 4, 16th hats, rolling offbeat bass,
    a running arpeggio, and a riser into every fourth bar so section changes land on a downbeat."""
    if seconds < 8:
        raise ValueError("A score needs a full film duration.")
    n = int((seconds + 0.4) * RATE)
    left, right = _zeros(n), _zeros(n)
    rng = random.Random(132)
    beat = 60 / DRIVE["bpm"]
    bar = beat * 4
    t, bar_i = 0.0, 0
    while t < seconds:
        name = DRIVE_LOOP[bar_i % len(DRIVE_LOOP)]
        tones = DRIVE_CHORDS[name]
        sub, root = tones[0], tones[1]
        intro = bar_i < 1
        close = 0.5 if t > seconds - 5 else 1.0
        full = 0.0 if intro else close
        for b in range(4):
            hit = t + b * beat
            _sweep(left, hit, 0.16, 128, 42, 0.78 * close, 12)
            _sweep(right, hit, 0.16, 124, 40, 0.74 * close, 12)
            if b in (1, 3) and not intro:
                _noise(left, rng, hit, 0.14, 0.11 * full, decay=26, bright=0.6)
                _noise(right, rng, hit + 0.006, 0.14, 0.11 * full, decay=26, bright=0.6)
            for s in range(4):
                hat = hit + s * beat / 4
                accent = 1.0 if s == 2 else 0.55
                _noise(left if s % 2 else right, rng, hat, 0.035, 0.035 * accent * full, decay=120, bright=0.98)
            off = hit + beat / 2
            _add(left, sub * 2, off, beat * 0.42, 0.2 * full, attack=0.003, release=0.08, detune=0.998)
            _add(right, sub * 2, off, beat * 0.42, 0.18 * full, attack=0.003, release=0.08, detune=1.002)
            _add(left, sub * 4, off, beat * 0.3, 0.05 * full, attack=0.003, release=0.06)
        if not intro:
            for i, freq in enumerate(tones[2:]):
                voice = 0.032 * close * (0.75 if i else 1.0)
                for at in (0.0, 1.5, 3.0):
                    _add(left, freq, t + at * beat, beat * 0.9, voice, attack=0.004, release=0.18, detune=0.996)
                    _add(right, freq, t + at * beat, beat * 0.9, voice, attack=0.004, release=0.18, detune=1.004)
            steps = (tones[2], tones[3], tones[4], tones[3] * 2, tones[4], tones[3], tones[2] * 2, tones[4])
            for s, freq in enumerate(steps * 2):
                note = t + s * beat / 4
                pan = 0.5 + 0.35 * math.sin(s * 0.8)
                _add(left, freq * 2, note, 0.09, 0.04 * close * (1.2 - pan), attack=0.002, release=0.06)
                _add(right, freq * 2, note, 0.09, 0.04 * close * (0.2 + pan), attack=0.002, release=0.06)
        if bar_i % 4 == 3 and t + bar < seconds - 2:
            rise_at = t + bar - beat * 2
            steps = 24
            for k in range(steps):
                at = rise_at + k * (beat * 2) / steps
                _noise(left if k % 2 else right, rng, at, beat * 2 / steps, 0.012 + 0.05 * k / steps, decay=8, bright=0.95)
        t += bar
        bar_i += 1
    return _finish(left, right, path, DRIVE, fade_in=0.05, fade_out=1.6, peak=0.44)


def write_score(kind: str, path: Path, seconds: float) -> dict:
    if kind in {SCORE["version"], "privacy-pad"}:
        return write_privacy_bed(path, seconds)
    if kind in {LAUNCH["version"], "launch-pulse"}:
        return write_launch_bed(path, seconds)
    if kind in {DRIVE["version"], "launch-drive"}:
        return write_drive_bed(path, seconds)
    raise ValueError("Unknown original score.")


SFX = {"version": "launch-sfx-v2"}


def _place(left: array.array, right: array.array, at: float, samples, *, pan=0.5) -> None:
    i0 = int(at * RATE)
    for i, value in enumerate(samples):
        j = i0 + i
        if 0 <= j < len(left):
            left[j] += value * (1.2 - pan * 0.4)
            right[j] += value * (0.8 + pan * 0.4)


SWIPE_RISE = 0.15


def _swipe(rng: random.Random, amp=0.2):
    """A tight filtered-noise rise that lands on the cut with a low thump and a short tap in the score's key (A)."""
    rise, low, band = [], 0.0, 0.0
    n = int(SWIPE_RISE * RATE)
    for i in range(n):
        p = i / n
        f = 2 * math.sin(math.pi * (700 + 7200 * p ** 2) / RATE)
        high = rng.uniform(-1, 1) - low - 0.6 * band
        band += f * high
        low += f * band
        rise.append(band * p ** 2.4)
    peak = max(abs(v) for v in rise) or 1.0
    out = [v / peak * amp * 0.75 for v in rise]
    phase = 0.0
    for i in range(int(0.22 * RATE)):
        t = i / RATE
        phase += 2 * math.pi * (150 - 95 * min(1.0, t / 0.12)) / RATE
        thump = 0.7 * math.sin(phase) * math.exp(-t * 26)
        tap = 0.22 * math.sin(2 * math.pi * 880 * t) * math.exp(-t * 55) + 0.1 * math.sin(2 * math.pi * 1320 * t) * math.exp(-t * 70)
        out.append(amp * (thump + tap) * min(1.0, i / 40))
    return out


def _click(rng: random.Random, amp=0.32):
    for i in range(int(0.03 * RATE)):
        t = i / RATE
        yield amp * (0.65 * math.sin(2 * math.pi * 2350 * t) * math.exp(-t * 240) + 0.35 * rng.uniform(-1, 1) * math.exp(-t * 1100))


def _tone(freq: float, dur: float, amp: float, *, decay=0.0, harmonics=(1.0,), attack=0.004):
    n = int(dur * RATE)
    for i in range(n):
        t = i / RATE
        env = min(1.0, t / attack) * (math.exp(-t * decay) if decay else min(1.0, (n - i) / (0.01 * RATE)))
        yield amp * env * sum(h * math.sin(2 * math.pi * freq * (k + 1) * t) for k, h in enumerate(harmonics))


def _pop(amp=0.2):
    phase = 0.0
    for i in range(int(0.09 * RATE)):
        p = i / (0.09 * RATE)
        phase += 2 * math.pi * (720 - 470 * p) / RATE
        yield amp * math.exp(-p * 7) * math.sin(phase)


def _impact(rng: random.Random, amp=0.55):
    phase, low = 0.0, 0.0
    for i in range(int(0.9 * RATE)):
        p = i / (0.9 * RATE)
        phase += 2 * math.pi * (105 - 68 * p) / RATE
        low += 0.08 * (rng.uniform(-1, 1) - low)
        yield amp * (math.exp(-p * 4.5) * math.sin(phase) + 0.6 * low * math.exp(-p * 30))


def _sound(kind: str, rng: random.Random):
    if kind == "swipe":
        return _swipe(rng), SWIPE_RISE
    if kind == "click":
        return list(_click(rng)) + [0.0] * int(0.05 * RATE) + [v * 0.45 for v in _click(rng)], 0.0
    if kind == "tick":
        return [v * 0.35 for v in _click(rng)], 0.0
    if kind == "pop":
        return list(_pop()), 0.0
    if kind == "hangup":
        return list(_tone(620, 0.12, 0.13, harmonics=(1.0, 0.25))) + [0.0] * int(0.05 * RATE) + list(_tone(470, 0.17, 0.13, harmonics=(1.0, 0.25))), 0.0
    if kind == "connect":
        return list(_tone(880, 0.07, 0.07)) + list(_tone(1320, 0.09, 0.07)), 0.0
    if kind == "chime":
        first, second = list(_tone(1046.5, 1.0, 0.11, decay=4.5)), list(_tone(1568.0, 1.0, 0.09, decay=4.0))
        offset = int(0.08 * RATE)
        return [a + (second[i - offset] if i >= offset else 0.0) for i, a in enumerate(first + [0.0] * offset)], 0.0
    if kind == "impact":
        return list(_impact(rng)), 0.0
    raise ValueError("Unknown sound effect.")


def message_arrivals(scene: dict, layout: str | None) -> list[int]:
    """Scene frames where a message lands. The cadence mirrors CADENCE in remotion launch/ScaleShots.tsx."""
    rows = (scene.get("screen") or {}).get("rows") or []
    frames = scene.get("frames") or 10**6
    if layout == "thread":
        landing = [6 + 20 * k + 2 for k in range(len(rows))]
    elif layout == "phone":
        landed = [row for row in rows if row.get("hint") in {"delivered", "read"}] or rows
        landing = [10 + 18 * k + 2 for k in range(len(landed))]
    elif layout == "lanes":
        lanes = min(4, len({row.get("tag") or "" for row in rows}))
        landing = sorted(8 + 8 * lane + 84 * n + 4 for lane in range(lanes) for n in range(frames // 84 + 1))
    else:
        landing = [14 + 9 * i for i in range(6)]
    return [frame for frame in landing if frame < frames]


def launch_sfx_cues(scenes: list[dict], craft: list[dict]) -> list[tuple[float, str]]:
    """Every sound answers something visible: a wipe, a click, a reveal, a hang-up. Times are film seconds."""
    cues: list[tuple[float, str]] = []
    revealed = False
    for index, scene in enumerate(scenes):
        start, visual = scene["from"] / 30, scene.get("visual")
        field = craft[index].get("field")
        labels = [scene["from"] + frame for frame in scene.get("labelFrames") or []]
        # Consecutive calls share one handset and consecutive screens push inside one block; every other cut wipes.
        continues = index and visual in {"call", "ui"} and scenes[index - 1].get("visual") == visual and field == craft[index - 1].get("field")
        if index and not continues:
            cues.append((start + 0.2, "swipe"))
        if visual == "call" and (index == 0 or scenes[index - 1].get("visual") != "call"):
            cues.append((start + 0.25, "connect"))
        if visual == "kinetic" and index and scene.get("kind") not in {"hook", "problem"} and not revealed:
            cues.append((start + 0.05, "impact"))
            revealed = True
        if visual == "endcard":
            cues.append((start + 0.05, "impact"))
        if visual in {"orbit", "ui"} or (visual == "call" and (scene.get("voice") or "narrator") == "narrator"):
            cues += [((frame + 8) / 30, "pop") for frame in labels]
        if visual == "messages":
            cues += [(start + frame / 30, "tick") for frame in message_arrivals(scene, craft[index].get("layout"))]
        if visual == "ui" and (scene.get("screen") or {}).get("view") == "checklist":
            standard = [row for row in (scene.get("screen") or {}).get("rows", []) if not row.get("tag")]
            cues += [((scene["from"] + 8 + 3 * i + 4) / 30, "tick") for i in range(len(standard))]
        if scene.get("clickAt") is not None:
            cues.append((scene["clickAt"] / 30, "click"))
            if (scene.get("screen") or {}).get("toast"):
                cues.append((scene["clickAt"] / 30 + 0.18, "chime"))
        if scene.get("hangupFrame") is not None:
            cues.append((scene["hangupFrame"] / 30, "hangup"))
    return sorted(cues)


def write_sfx(cues: list[tuple[float, str]], path: Path, seconds: float) -> dict:
    """Absolute-level stereo effects on the film clock; never normalized, so they sit under the voice."""
    n = int((seconds + 0.4) * RATE)
    left, right = _zeros(n), _zeros(n)
    rng = random.Random(7)
    for index, (at, kind) in enumerate(cues):
        samples, lead = _sound(kind, rng)
        _place(left, right, max(0.0, at - lead), samples, pan=0.5 if kind != "swipe" else 0.25 + 0.5 * (index % 2))
    pcm = array.array("h")
    for a, b in zip(left, right):
        pcm.append(max(-32767, min(32767, int(a * 32767))))
        pcm.append(max(-32767, min(32767, int(b * 32767))))
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(2); wav.setsampwidth(2); wav.setframerate(RATE)
        wav.writeframes(pcm.tobytes())
    return {**SFX, "cues": len(cues), "seconds": n / RATE, "source": "original"}


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


def mix_under_voice(voice: Path, bed: Path | None, target: Path, *, music_gain: float = 0.4, duck_floor: float = 0.22, sfx: Path | None = None, sfx_gain: float = 1.0) -> None:
    """Keep Siya in front: duck the bed when she speaks. Effects ride on top, undocked but quiet."""
    rate, _, spoken = _read(voice)
    n = len(spoken)
    music = [0.0] * n
    if bed is not None:
        bed_rate, _, music = _read(bed)
        if bed_rate != RATE:
            raise ValueError("Voice and score must both be 44.1 kHz.")
    if rate != RATE:
        raise ValueError("Voice and score must both be 44.1 kHz.")
    if len(music) < n:
        music = music + [0.0] * (n - len(music))
    effects = [0.0] * n
    if sfx is not None:
        sfx_rate, _, effects = _read(sfx)
        if sfx_rate != RATE:
            raise ValueError("Sound effects must be 44.1 kHz.")
        effects = effects + [0.0] * max(0, n - len(effects))
    follow = 0.0
    attack = 1 - math.exp(-1 / (0.04 * RATE))
    release = 1 - math.exp(-1 / (0.45 * RATE))
    mixed = array.array("h")
    for i in range(0, n, 2):
        level = math.sqrt((spoken[i] ** 2 + spoken[i + 1] ** 2) / 2)
        follow += (attack if level > follow else release) * (level - follow)
        duck = duck_floor + (1 - duck_floor) / (1 + (follow / 0.018) ** 2)
        for side in (0, 1):
            sample = spoken[i + side] + music[i + side] * music_gain * duck + effects[i + side] * sfx_gain
            mixed.append(max(-32767, min(32767, int(sample * 32767))))
    with wave.open(str(target), "wb") as wav:
        wav.setnchannels(2); wav.setsampwidth(2); wav.setframerate(RATE)
        wav.writeframes(mixed.tobytes())
