"""Directed narration: isolated acting beats, exact pauses, and untouched word alignment."""
import hashlib
import html
import json
import re
from pathlib import Path

from app.services.marketing_voice import load_timing, stitch_takes


def directed_transcript(text: str, pauses: list[dict]) -> str:
    """Only insert validated provider break tags; spoken words never change."""
    marks = []
    for pause in pauses:
        anchor, milliseconds = pause['after'], pause['milliseconds']
        if not isinstance(milliseconds, int) or not 80 <= milliseconds <= 800:
            raise ValueError('Narration pauses must be 80–800 milliseconds.')
        if not anchor or text.count(anchor) != 1:
            raise ValueError('A pause anchor must appear exactly once in its spoken line.')
        marks.append((text.index(anchor) + len(anchor), milliseconds))
    if len({at for at, _ in marks}) != len(marks):
        raise ValueError('Duplicate narration pause.')
    result, at = '', 0
    for stop, milliseconds in sorted(marks):
        result += html.escape(text[at:stop], quote=False) + f'<break time="{milliseconds}ms"/>'
        at = stop
    return result + html.escape(text[at:], quote=False)


def review_diction(text: str, speed: float) -> None:
    """Guard the two ways a correct script still comes out unintelligible."""
    from app.services.marketing_video import pronunciation_lexicon, pronunciation_dict_id
    for item in pronunciation_lexicon().get('items', []):
        term = item['text']
        if term.isupper() and re.search(rf'\b{re.escape(term)}\s*[.?!]', text):
            raise ValueError(f'Give "{term}" its noun in the spoken line; a bare abbreviation is hard to hear.')
    if pronunciation_dict_id(text) and speed > 1.05:
        raise ValueError('A line carrying a hard-to-say term must not be rushed past 1.05 speed.')


def performance_profile(scene: dict) -> dict:
    from app.services.marketing_video import scene_profile
    base = scene_profile(scene)
    direction = scene.get('performance') or {}
    allowed = {'emotion', 'speed', 'pauses'}
    if set(direction) - allowed:
        raise ValueError('Unsupported narration direction.')
    profile = {**base, **direction}
    language = scene.get("language") or profile.get("language", "en")
    if language not in {"en", "hi"}:
        raise ValueError("Unsupported narration language.")
    profile["language"] = language
    if scene.get("voice_id"):
        from uuid import UUID
        profile["voice_id"] = str(UUID(scene["voice_id"]))
        profile["explicit_voice"] = True
    if profile['emotion'] not in {'confident','curious','excited','calm','sympathetic','content','enthusiastic'}:
        raise ValueError('Unsupported narration emotion.')
    if not .85 <= profile['speed'] <= 1.15:
        raise ValueError('Narration speed must preserve natural delivery.')
    directed_transcript(scene['narration'], profile.get('pauses', []))
    review_diction(scene['narration'], profile['speed'])
    return profile



def validate_voice_cast(scenes: list[dict]) -> None:
    """Role identity survives language switches; participants cannot share a voice."""
    from app.services.marketing_video import narrator_id, VOICE_PROFILE
    identities = {}
    for scene in scenes:
        role = scene.get('voice') or 'narrator'
        profile = performance_profile(scene)
        voice = profile['voice_id'] if profile.get('explicit_voice') else narrator_id() if profile['name'] == VOICE_PROFILE['name'] else profile['voice_id']
        if role in identities and identities[role] != voice:
            raise ValueError('Keep each speaker identity consistent across language changes.')
        identities[role] = voice
    if 'agent' in identities and 'customer' in identities and identities['agent'] == identities['customer']:
        raise ValueError('The agent and customer must have distinct voices.')
    if 'narrator' in identities and any(identities.get(role) == identities['narrator'] for role in ('agent','customer')):
        raise ValueError('Narrator and dialogue participants must have distinct voices.')


HANGUP_HOLD = 2.0
_DIALOGUE = {"agent", "customer", "example"}


def _one_pole_lowpass(samples: list[float], cutoff: float, rate: int) -> list[float]:
    a = 1.0 / (1.0 + (rate / (2 * 3.141592653589793 * cutoff)))
    y = 0.0
    out = []
    for x in samples:
        y += a * (x - y)
        out.append(y)
    return out


def _one_pole_highpass(samples: list[float], cutoff: float, rate: int) -> list[float]:
    a = (rate / (2 * 3.141592653589793 * cutoff)) / (1.0 + (rate / (2 * 3.141592653589793 * cutoff)))
    prev_x = prev_y = 0.0
    out = []
    for x in samples:
        y = a * (prev_y + x - prev_x)
        prev_x, prev_y = x, y
        out.append(y)
    return out


def color_handset_take(path: Path) -> None:
    """Keep timestamps; paint the customer onto a mobile uplink so they sit across the line."""
    import array
    import hashlib
    import math
    import wave
    with wave.open(str(path), "rb") as wav:
        params = wav.getparams()
        raw = wav.readframes(wav.getnframes())
        rate = wav.getframerate()
    pcm = array.array("h")
    pcm.frombytes(raw)
    channels = params.nchannels
    frames = [pcm[i] / 32768.0 for i in range(0, len(pcm), channels)]
    original_rms = math.sqrt(sum(x*x for x in frames) / max(1, len(frames)))
    frames = _one_pole_highpass(frames, 120, rate)
    frames = _one_pole_lowpass(frames, 7200, rate)
    # A modern wideband call preserves breath and consonants. Never normalize each
    # take to full scale: that crushed the customer into an unnaturally loud buzz.
    filtered_rms = math.sqrt(sum(x*x for x in frames) / max(1, len(frames)))
    gain = min(1.6, original_rms / max(filtered_rms, 1e-8))
    shaped = array.array("h")
    for i, x in enumerate(frames):
        x = math.tanh(x * gain * 1.05) / 1.05
        sample = int(max(-32767, min(32767, x * 32767)))
        for _ in range(channels):
            shaped.append(sample)
    with wave.open(str(path), "wb") as wav:
        wav.setparams(params)
        wav.writeframes(shaped.tobytes())
    sidecar = path.with_suffix(".timing.json")
    meta = json.loads(sidecar.read_text())
    meta["audio_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    meta["line"] = "handset"
    sidecar.write_text(json.dumps(meta, indent=2))


def stitch_gaps(scenes: list[dict]) -> list[float]:
    """Leave a beat between speakers; hold after the last spoken turn so the call can hang up."""
    gaps = []
    for previous, current in zip(scenes, scenes[1:]):
        leave_call = previous.get("voice") in _DIALOGUE and (current.get("voice") or "narrator") == "narrator"
        both_talking = previous.get("voice") in _DIALOGUE and current.get("voice") in _DIALOGUE
        # Explanatory diagrams need a readable hold before the next sentence.
        diagram = bool(previous.get('treatment')) and not both_talking
        hold = float(previous.get('hold_after', 1.25 if diagram else 0.14))
        if not 0 <= hold <= 3:
            raise ValueError('Scene hold must be between zero and three seconds.')
        gaps.append(HANGUP_HOLD if leave_call else 0.32 if both_talking else hold)
    return gaps


def assemble_directed_audio(video: dict, public: Path, *, preview=False):
    from app.services.marketing_video import speak, voice_take_key
    validate_voice_cast(video["scenes"])
    takes, identities = [], []
    for scene in video['scenes']:
        text = scene['narration']
        profile = performance_profile(scene)
        key = voice_take_key(text, preview=preview, profile=profile)
        path = public / f'directed-{key}.wav'
        try:
            load_timing(path, text)
        except (OSError, ValueError, KeyError):
            speak(text, path, preview=preview, profile=profile)
            if profile.get("line") == "handset":
                color_handset_take(path)
        takes.append((path,text)); identities.append(key)
    gaps = stitch_gaps(video["scenes"])
    digest = hashlib.sha256(json.dumps(['directed-v2', identities, gaps]).encode()).hexdigest()[:12]
    path = public / f'narration-{digest}.wav'
    text = ' '.join(t for _,t in takes)
    try:
        words, seconds = load_timing(path,text)
    except (OSError, ValueError, KeyError):
        words, seconds = stitch_takes(takes, path, gap_seconds=gaps or 0.14)
    return path,words,seconds
