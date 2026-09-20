"""Word-aligned marketing narration. No timing estimates are accepted for production."""
from __future__ import annotations

import base64
import hashlib
import json
import math
import re
import wave
import unicodedata
from pathlib import Path


def normalized(word: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFC', word.casefold()) if c.isalnum() or unicodedata.category(c).startswith('M'))


def align_words(text: str, timestamps: dict, seconds: float) -> list[dict]:
    """Map provider token boundaries back to the approved spelling/punctuation."""
    supplied = timestamps.get('words', [])
    starts, ends = timestamps.get('start', []), timestamps.get('end', [])
    expected = text.split()
    if not supplied or len(supplied) != len(starts) or len(starts) != len(ends):
        raise ValueError('Narration is missing complete word timestamps.')
    if ''.join(map(normalized, supplied)) != ''.join(map(normalized, expected)):
        raise ValueError('Narration timestamps do not cover the approved script exactly.')
    spans, offset, previous = [], 0, -1.0
    for word, begin, end in zip(supplied, starts, ends):
        begin, end = float(begin), float(end)
        if not all(map(math.isfinite, [begin, end])) or not 0 <= begin <= end <= seconds + 0.1 or begin < previous:
            raise ValueError('Narration word timestamps are invalid or out of order.')
        width = len(normalized(word))
        if width:
            spans.append((offset, offset + width, begin, end))
            offset += width
        previous = begin
    aligned, offset = [], 0
    for word in expected:
        width = len(normalized(word))
        hits = [s for s in spans if s[0] < offset + width and s[1] > offset]
        if not hits:
            raise ValueError('Narration contains an unaligned token.')
        aligned.append({'word': word, 'start': hits[0][2], 'end': hits[-1][3]})
        offset += width
    return aligned


def save_sse_take(response_text: str, text: str, path: Path) -> None:
    """Buffer one complete SSE response; save only complete PCM + matching timestamps."""
    pcm = bytearray()
    timestamps = {'words': [], 'start': [], 'end': []}
    done = False
    for event in re.split(r'\r?\n\r?\n', response_text.strip()):
        data = '\n'.join(line[5:].lstrip() for line in event.splitlines() if line.startswith('data:'))
        if not data:
            continue
        message = json.loads(data)
        kind = message.get('type')
        if kind == 'error' or message.get('status_code', 200) >= 400:
            raise ValueError('Narration provider returned an incomplete take.')
        if kind == 'chunk':
            pcm.extend(base64.b64decode(message['data'], validate=True))
        elif kind == 'timestamps':
            timing = message.get('word_timestamps', {})
            for key in timestamps:
                timestamps[key].extend(timing.get(key, []))
        elif kind == 'done':
            done = True
    if not done or len(pcm) < 44100 * 2 * 0.3 or len(pcm) % 2:
        raise ValueError('Narration audio stream is incomplete.')
    words = align_words(text, timestamps, len(pcm) / (44100 * 2))
    temporary = path.with_suffix('.pending.wav')
    with wave.open(str(temporary), 'wb') as wav:
        wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(44100)
        wav.writeframes(pcm)
    metadata = {'source': 'cartesia_word_timestamps', 'transcript': text, 'words': words,
                'audio_sha256': hashlib.sha256(temporary.read_bytes()).hexdigest()}
    temporary.replace(path)
    sidecar = path.with_suffix('.timing.json')
    pending = sidecar.with_suffix('.pending.json')
    pending.write_text(json.dumps(metadata, indent=2))
    pending.replace(sidecar)


def load_timing(path: Path, text: str) -> tuple[list[dict], float]:
    metadata = json.loads(path.with_suffix('.timing.json').read_text())
    if metadata.get('source') != 'cartesia_word_timestamps' or metadata.get('transcript') != text or metadata.get('audio_sha256') != hashlib.sha256(path.read_bytes()).hexdigest():
        raise ValueError('Cached narration timing belongs to a different audio take.')
    with wave.open(str(path), 'rb') as wav:
        seconds = wav.getnframes() / wav.getframerate()
    timing = metadata['words']
    validated = align_words(text, {'words': [w['word'] for w in timing], 'start': [w['start'] for w in timing], 'end': [w['end'] for w in timing]}, seconds)
    return validated, seconds


def shift_words(words: list[dict], offset: float) -> list[dict]:
    return [{**word, "start": word["start"] + offset, "end": word["end"] + offset} for word in words]


def stitch_takes(takes: list[tuple[Path, str]], target: Path, *, gap_seconds: float | list[float] = 0.28) -> tuple[list[dict], float]:
    """Join example and narrator PCM on one clock. Transcript is the scene order, with no extra words."""
    if not takes:
        raise ValueError("A film needs at least one voice take.")
    gaps = list(gap_seconds) if isinstance(gap_seconds, (list, tuple)) else [float(gap_seconds)] * max(0, len(takes) - 1)
    if len(gaps) != max(0, len(takes) - 1):
        raise ValueError("Voice stitch needs one gap between each consecutive take.")
    transcript = " ".join(text for _, text in takes)
    combined, words, offset = bytearray(), [], 0.0
    params = None
    for index, (path, text) in enumerate(takes):
        timed, seconds = load_timing(path, text)
        with wave.open(str(path), "rb") as wav:
            params = params or wav.getparams()
            if wav.getparams().nchannels != params.nchannels or wav.getframerate() != params.framerate:
                raise ValueError("Voice takes must share the same PCM format.")
            pcm = wav.readframes(wav.getnframes())
        if index:
            gap = float(gaps[index - 1])
            combined.extend(b"\0" * int(round(gap * params.framerate) * params.nchannels * params.sampwidth))
            offset += gap
        combined.extend(pcm)
        words.extend(shift_words(timed, offset))
        offset += seconds
    with wave.open(str(target), "wb") as wav:
        wav.setparams(params)
        wav.writeframes(combined)
    sidecar = target.with_suffix(".timing.json")
    sidecar.write_text(json.dumps({
        "source": "cartesia_word_timestamps", "transcript": transcript, "words": words,
        "audio_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
    }, indent=2))
    return words, offset


def pad_narration(source: Path, target: Path, lead_seconds: float, total_seconds: float) -> None:
    """Place the original PCM take on the film clock before the single AAC encode."""
    with wave.open(str(source), 'rb') as wav:
        params = wav.getparams()
        audio = wav.readframes(wav.getnframes())
    lead = round(lead_seconds * params.framerate)
    total = round(total_seconds * params.framerate)
    tail = total - lead - params.nframes
    if lead < 0 or tail < 0:
        raise ValueError('The narration does not fit the film clock.')
    stride = params.nchannels * params.sampwidth
    with wave.open(str(target), 'wb') as wav:
        wav.setparams(params)
        wav.writeframes(b'\0' * (lead * stride) + audio + b'\0' * (tail * stride))


def caption_ranges(words: list[dict]) -> list[tuple[int, int]]:
    """Break captions where the voice breaks: sentences, then clauses, then even chunks."""
    phrases, start = [], 0
    for i, w in enumerate(words):
        if re.search(r'[.!?;:,।॥]$', w['word']) or i == len(words) - 1:
            phrases.append((start, i + 1)); start = i + 1
    chunks = []
    for start, stop in phrases:
        size = math.ceil((stop - start) / math.ceil((stop - start) / 5))
        while stop - start > size:
            chunks.append((start, start + size)); start += size
        chunks.append((start, stop))
    return chunks


def cue_indices(scene: dict, words: list[dict]) -> list[int]:
    labels = scene.get('labels', [])
    cues = scene.get('label_cues', [])
    if labels and len(cues) != len(labels):
        raise ValueError('Every animated label needs an exact narration cue before production.')
    normalized_words = [normalized(w['word']) for w in words]
    indices, after = [], 0
    for cue in cues:
        tokens = list(map(normalized, cue.split()))
        hits = [i for i in range(after, len(words) - len(tokens) + 1) if normalized_words[i:i+len(tokens)] == tokens]
        if not tokens or not hits:
            raise ValueError('Animation cues must quote the narration in spoken order.')
        indices.append(hits[0]); after = hits[0] + len(tokens)
    return indices


def bind_narrated_film(scenes: list[dict], words: list[dict], seconds: float, *, audio_lead=3) -> tuple[list[dict], int]:
    """One continuous voice track is the clock for every cut, caption and reveal."""
    groups, offset = [], 0
    for scene in scenes:
        count = len(scene['narration'].split())
        group = words[offset:offset + count]
        if len(group) != count or [w['word'] for w in group] != scene['narration'].split():
            raise ValueError('Scene narration does not match the aligned voice track.')
        groups.append(group); offset += count
    if offset != len(words):
        raise ValueError('Narration has unassigned words.')
    # Put cuts in the pause between sentences. Audio stays continuous; no inserted
    # gaps, per-shot resampling, or accumulated rounding drift.
    boundaries = [0] + [audio_lead + round((groups[i-1][-1]['end'] + groups[i][0]['start']) * 15) for i in range(1, len(groups))]
    duration = audio_lead + math.ceil(seconds * 30) + 12
    boundaries.append(duration)
    result = []
    previous_language = None
    for i, (scene, group) in enumerate(zip(scenes, groups)):
        begin, end = boundaries[i:i+2]
        frames = end - begin
        longest = 300 if scene.get("voice") in {"example", "agent", "customer"} or scene.get("visual") in {"call", "conversation", "detect", "collect"} else 240
        if not 45 <= frames <= longest:
            raise ValueError('A narrated shot is outside the 1.5–8 second pacing limits; revise its spoken line.')
        cues = cue_indices(scene, group)
        labels = [max(0, audio_lead + round(group[j]['start']*30) - begin - 8) for j in cues]
        if labels and labels[-1] + 20 > frames:
            raise ValueError('The final visual cue arrives too late to read before the next cut.')
        captions = []
        for first, stop in caption_ranges(group):
            caption_from = max(0, audio_lead + round(group[first]['start'] * 30) - begin)
            caption_to = min(frames, audio_lead + math.ceil(group[stop-1]['end'] * 30) - begin + 2)
            captions.append({'text': ' '.join(w['word'] for w in group[first:stop]), 'from': caption_from, 'to': max(caption_from + 1, caption_to)})
        for c, following in zip(captions, captions[1:]):
            c['to'] = min(c['to'], following['from'])
        example_frames = [max(0, audio_lead + round(group[cue_indices({'labels':[ex['label']], 'label_cues':[ex['cue']]}, group)[0]]['start']*30) - begin) for ex in scene.get('examples', [])]
        if example_frames and max(example_frames) + 20 > frames:
            raise ValueError('An example transformation arrives too late to read.')
        language_from = None
        if scene.get('voice') in {'agent', 'customer', 'example'}:
            language = scene.get('language')
            if language and previous_language and language != previous_language:
                language_from = previous_language
            if language:
                previous_language = language
        result.append({**scene, 'from': begin, 'frames': frames, 'captions': captions, 'labelFrames': labels,
                       'exampleFrames': example_frames, 'languageFrom': language_from,
                       'wordTimings': group, 'timingSource': 'cartesia_word_timestamps'})
    for index, scene in enumerate(result):
        call = scene.get('visual') == 'call' or str(scene.get('treatment') or '').startswith('call-')
        nxt = result[index + 1] if index + 1 < len(result) else None
        next_call = bool(nxt) and (nxt.get('visual') == 'call' or str(nxt.get('treatment') or '').startswith('call-'))
        if call and not next_call:
            scene['endsCall'] = True
            if nxt is not None:
                nxt['transitionFrom'] = 'call'
    return result, duration
