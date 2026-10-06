"""HeyGen avatar presenter videos.

A separate pipeline: it never reads or writes MarketingCampaign rows, the Remotion film
renderer, film narration takes or the marketing queue. HeyGen renders remotely, so a server
restart loses nothing; rows are polled on demand and the finished MP4 is copied locally
because HeyGen file URLs are presigned and expire.

A HeyGen voice speaks the script inside HeyGen. A cloned Cartesia or ElevenLabs voice (voice id
prefixed "cartesia:" or "elevenlabs:") is narrated here first, previewed as an MP3, then uploaded
for HeyGen to lip-sync.
"""
from __future__ import annotations

import array
import hashlib
import html
import io
import json
import logging
import math
import re
import shutil
import tempfile
import threading
import time
import wave
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.context import spawn
from app.clients.cartesia import CartesiaClient, CartesiaError
from app.clients.elevenlabs import ElevenLabsClient, ElevenLabsError
from app.clients.heygen import HeyGenClient, HeyGenError
from app.config import ROOT, settings
from app.database import SessionLocal
from app.models import AvatarVideo, MarketingFeature
from app.services.brand import brand_name
from app.storage import WorkspaceDir

log = logging.getLogger(__name__)

AVATAR_DIR = WorkspaceDir("marketing", "avatar")
SOURCES_DIR = WorkspaceDir("marketing", "avatar", "sources")
MAX_PHOTOS = 8
MAX_PHOTO_BYTES = 20 * 1024 * 1024
# HeyGen animates the mouth from these pixels; below 1080p the teeth are a blur it has to invent.
MIN_PHOTO_EDGE = 1080
PHOTO_RETRY_SECONDS = 4
SAFE_ID = re.compile(r"[A-Za-z0-9_-]{1,120}")
SCRIPT_SURFACE = "marketing_avatar_script"
ASPECT_RATIOS = ("16:9", "9:16", "1:1", "4:5", "auto")
RESOLUTIONS = ("1080p", "720p")
ENGINES = ("avatar_iv", "avatar_v", "avatar_iii")
EXPRESSIVENESS = ("low", "medium", "high")
MAX_MOTION_PROMPT = 300
# The prompt guides body motion so the presenter isn't frozen. Face cues and higher expressiveness make
# HeyGen exaggerate the mouth beyond what a single photo shows, so teeth merge, flicker and vanish.
PRESENTER_MOTION = ("Speaks to camera in a calm, conversational way. Gentle head nods, relaxed shoulders, "
                    "steady eye contact.")
DEFAULT_OPTIONS = {"aspect_ratio": "16:9", "resolution": "1080p", "engine": "avatar_iv", "speed": 1.0, "background": "",
                   "pauses": True, "expressiveness": "low", "motion_prompt": PRESENTER_MOTION}
SENTENCE_BREAK = '<break time="0.5s"/>'
PARAGRAPH_BREAK = '<break time="1s"/>'
BREAK_TAG = re.compile(r"<break\b[^>]*/>", re.IGNORECASE)
SENTENCE_END = re.compile(r"(?<=[.!?])([\"')\]]?)\s+(?=[\"'(\[]?[A-Z0-9])")
# Multilingual v2 honours punctuation and break tags; Eleven v3 ignores break tags and Flash rushes.
ELEVENLABS_MODEL = "eleven_multilingual_v2"
ELEVEN_VOICE_SETTINGS = {"stability": 0.5, "similarity_boost": 0.75, "style": 0.0, "use_speaker_boost": True}
ELEVEN_SPEED = (0.7, 1.2)
NARRATORS = ("cartesia", "elevenlabs")
# Sonic 3.6 learns from up to 60 s of a clone clip; older Sonic models hear only the first 10 s.
CARTESIA_MODEL = "sonic-3.6"
CARTESIA_LOCALE = "en-IN"
CARTESIA_SPEED = (0.6, 1.5)
# Sonic already pauses at punctuation, so its added breaks are shorter than the HeyGen/ElevenLabs ones.
CARTESIA_SENTENCE_BREAK = '<break time="400ms"/>'
CARTESIA_PARAGRAPH_BREAK = '<break time="800ms"/>'
CLIP_RATE = 44100
CLIP_SECONDS = 60
MIN_CLIP_SECONDS = 8
CLIP_HIGHPASS_HZ = 80
NARRATION_FILE = "narration.mp3"
NARRATION_BITRATE = 128_000  # Both providers return 44.1 kHz / 128 kbps CBR MP3, so size gives the length.
MAX_SAMPLE_BYTES = 25 * 1024 * 1024
SAMPLE_MIME = {".m4a": "audio/mp4", ".mp3": "audio/mpeg", ".wav": "audio/wav", ".aac": "audio/aac", ".ogg": "audio/ogg",
               ".flac": "audio/flac", ".webm": "audio/webm"}
ACTIVE = {"submitting", "submitted", "rendering", "downloading"}
EDITABLE = {"draft", "failed"}
MAX_SCRIPT_CHARS = 5000
WORDS_PER_MINUTE = 150
POLL_SECONDS = 8
CATALOG_TTL = 600
ACCOUNT_TTL = 300
RENDER_TIMEOUT = timedelta(hours=6)
SUBMIT_STALE = timedelta(minutes=3)
MAX_DOWNLOAD_ATTEMPTS = 3
BACKGROUND_DOWNLOADS = True
MIME = {".mp4": "video/mp4", ".srt": "application/x-subrip", ".jpg": "image/jpeg", ".png": "image/png", ".webp": "image/webp",
        ".mp3": "audio/mpeg"}

_submit_lock = threading.Lock()
_downloads: set[int] = set()
_downloads_lock = threading.Lock()
_account_cache: dict = {}
_catalog_cache: dict[tuple, tuple[float, dict]] = {}


def _now() -> datetime:
    return datetime.utcnow()


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _key_tag(client: HeyGenClient) -> str:
    return hashlib.sha256(client.api_key.encode()).hexdigest()[:10]


def word_count(script: str) -> int:
    return len((script or "").split())


def estimated_seconds(script: str, speed: float = 1.0) -> int:
    return round(word_count(script) / WORDS_PER_MINUTE * 60 / max(float(speed or 1.0), 0.5))


def clean_options(raw: dict | None) -> dict:
    data = {**DEFAULT_OPTIONS, **{k: v for k, v in (raw or {}).items() if k in DEFAULT_OPTIONS}}
    if data["aspect_ratio"] not in ASPECT_RATIOS:
        data["aspect_ratio"] = DEFAULT_OPTIONS["aspect_ratio"]
    if data["resolution"] not in RESOLUTIONS:
        data["resolution"] = DEFAULT_OPTIONS["resolution"]
    if data["engine"] not in ENGINES:
        data["engine"] = DEFAULT_OPTIONS["engine"]
    try:
        data["speed"] = round(min(max(float(data["speed"]), 0.5), 1.5), 2)
    except (TypeError, ValueError):
        data["speed"] = 1.0
    background = str(data.get("background") or "").strip()
    data["background"] = background if re.fullmatch(r"#[0-9a-fA-F]{6}", background) else ""
    data["pauses"] = bool(data["pauses"])
    if data["expressiveness"] not in EXPRESSIVENESS:
        data["expressiveness"] = DEFAULT_OPTIONS["expressiveness"]
    data["motion_prompt"] = " ".join(str(data["motion_prompt"] or "").split())[:MAX_MOTION_PROMPT]
    return data


def pace_script(script: str, sentence: str = SENTENCE_BREAK, paragraph: str = PARAGRAPH_BREAK) -> str:
    """Cloned voices read straight through punctuation; sparse break tags restore sentence rhythm.

    ElevenLabs destabilises with many breaks, so only sentence and paragraph ends get one, and a
    script that already carries the author's own break tags is left alone.
    """
    text = (script or "").strip()
    if BREAK_TAG.search(text):
        return text
    paragraphs = [" ".join(part.split()) for part in re.split(r"\n\s*\n", text) if part.strip()]
    paced = [SENTENCE_END.sub(lambda m: f"{m.group(1)} {sentence} ", part) for part in paragraphs]
    return f" {paragraph} ".join(paced)


def escape_outside_breaks(text: str) -> str:
    """Sonic parses markup, so stray <, > and & in copy are escaped while break tags pass through."""
    parts = BREAK_TAG.split(text)
    tags = BREAK_TAG.findall(text)
    return html.escape(parts[0], quote=False) + "".join(tag + html.escape(part, quote=False) for tag, part in zip(tags, parts[1:]))


def option_catalog() -> dict:
    return {"aspect_ratios": list(ASPECT_RATIOS), "resolutions": list(RESOLUTIONS), "engines": list(ENGINES),
            "expressiveness": list(EXPRESSIVENESS), "max_motion_prompt": MAX_MOTION_PROMPT,
            "max_script_chars": MAX_SCRIPT_CHARS, "words_per_minute": WORDS_PER_MINUTE, "defaults": dict(DEFAULT_OPTIONS)}


def account_status(*, force: bool = False) -> dict:
    client = HeyGenClient()
    if not client.configured:
        return {"configured": False, "reachable": False, "billing_type": "", "balance": None, "currency": "", "error": ""}
    tag = _key_tag(client)
    cached = _account_cache.get(tag)
    if cached and not force and time.monotonic() - cached[0] < ACCOUNT_TTL:
        return cached[1]
    try:
        me = client.me()
        wallet = me.get("wallet") or {}
        value = {"configured": True, "reachable": True, "billing_type": me.get("billing_type") or "",
                 "balance": wallet.get("remaining_balance"), "currency": (wallet.get("currency") or "").upper(), "error": ""}
    except HeyGenError as exc:
        value = {"configured": True, "reachable": False, "billing_type": "", "balance": None, "currency": "", "error": str(exc)}
    _account_cache[tag] = (time.monotonic(), value)
    return value


def _cached(key: tuple, loader) -> dict:
    hit = _catalog_cache.get(key)
    if hit and time.monotonic() - hit[0] < CATALOG_TTL:
        return hit[1]
    value = loader()
    _catalog_cache[key] = (time.monotonic(), value)
    return value


def look_out(item: dict) -> dict:
    status = str(item.get("status") or "completed")
    error = item.get("error") or {}
    return {
        "id": item["id"], "name": item.get("name") or "Untitled look", "avatar_type": item.get("avatar_type") or "",
        "group_id": item.get("group_id") or "", "gender": item.get("gender") or "",
        "preview_image_url": item.get("preview_image_url") or "", "preview_video_url": item.get("preview_video_url") or "",
        "default_voice_id": item.get("default_voice_id") or "", "engines": item.get("supported_api_engines") or [],
        "orientation": item.get("preferred_orientation") or "", "status": status,
        # Private looks still training, awaiting consent or rejected by moderation cannot render.
        "ready": status == "completed",
        "error": str(error.get("message") or "") if isinstance(error, dict) else str(error),
    }


def list_avatars(*, ownership: str = "private", avatar_type: str | None = None, token: str | None = None) -> dict:
    client = HeyGenClient()

    def load() -> dict:
        body = client.looks(ownership=ownership, avatar_type=avatar_type, token=token, limit=50)
        items = [look_out(item) for item in body.get("data") or [] if item.get("id")]
        return {"items": items, "has_more": bool(body.get("has_more")), "next_token": body.get("next_token") or ""}

    return _cached(("looks", _key_tag(client), ownership, avatar_type or "", token or ""), load)


def look_status(look_id: str, client: HeyGenClient | None = None) -> dict:
    if not SAFE_ID.fullmatch(look_id or ""):
        raise ValueError("That is not a HeyGen look id.")
    item = (client or HeyGenClient()).look(look_id)
    if not item.get("id"):
        raise HeyGenError("HeyGen returned no look for that id.", 404, "not_found")
    out = look_out(item)
    if out["ready"]:
        _catalog_cache.clear()
    return out


def _trim_bars(image):
    """Crop near-black letterbox bands, which phone screenshots of portraits often carry."""
    gray = image.convert("L")
    width, height = gray.size

    def dark(box) -> bool:
        counts = gray.crop(box).histogram()
        return sum(counts[:28]) >= 0.95 * max(sum(counts), 1)

    top, bottom, left, right = 0, height, 0, width
    while top < height // 4 and dark((0, top, width, top + 1)):
        top += 1
    while bottom > height * 3 // 4 and dark((0, bottom - 1, width, bottom)):
        bottom -= 1
    while left < width // 4 and dark((left, 0, left + 1, height)):
        left += 1
    while right > width * 3 // 4 and dark((right - 1, 0, right, height)):
        right -= 1
    if (top, bottom, left, right) == (0, height, 0, width):
        return image
    return image.crop((left, top, right, bottom))


def prepare_photo(raw: bytes) -> bytes:
    from PIL import Image, ImageOps, UnidentifiedImageError

    if len(raw) > MAX_PHOTO_BYTES:
        raise ValueError("Each photo must be under 20 MB.")
    try:
        image = Image.open(io.BytesIO(raw))
        image.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("One of the files is not a readable photo. Use JPEG or PNG.") from exc
    image = _trim_bars(ImageOps.exif_transpose(image).convert("RGB"))
    if min(image.size) < MIN_PHOTO_EDGE:
        raise ValueError(f"Each photo needs at least {MIN_PHOTO_EDGE}px on its shorter side so the face stays sharp.")
    out = io.BytesIO()
    image.save(out, "JPEG", quality=95)
    return out.getvalue()


def _save_source(group_id: str, look_id: str, data: bytes) -> None:
    if not (SAFE_ID.fullmatch(group_id) and SAFE_ID.fullmatch(look_id)):
        return
    folder = SOURCES_DIR / group_id
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{look_id}.jpg").write_bytes(data)


def _private_looks(client: HeyGenClient, group: str) -> dict[str, dict]:
    body = client.looks(ownership="private", group_id=group or None, limit=50)
    return {item["id"]: item for item in body.get("data") or [] if item.get("id")}


def _create_look(client: HeyGenClient, name: str, asset_id: str, group: str, key: str, attempts: int = 3) -> dict:
    before = _private_looks(client, group)
    for attempt in range(attempts):
        try:
            return client.create_photo_avatar(name, asset_id, group_id=group or None, idempotency_key=f"{key}-{attempt}")["avatar_item"]
        except HeyGenError as exc:
            time.sleep(PHOTO_RETRY_SECONDS * (attempt + 1))
            # A failed response can still leave a billed look behind; adopt it rather than paying for a duplicate.
            fresh = [item for look_id, item in _private_looks(client, group).items() if look_id not in before and item.get("name") == name]
            if len(fresh) == 1:
                return fresh[0]
            # A just-uploaded asset is briefly "not found"; retry only once HeyGen has confirmed no look exists.
            transient = exc.status in (404, 409) or "not found" in str(exc).lower()
            if fresh or not transient or attempt == attempts - 1:
                raise
    raise HeyGenError("HeyGen did not create the look.", 0, "not_created")


def create_photo_avatar(name: str, photos: list[tuple[str, bytes]], *, group_id: str = "",
                        look_names: list[str] | None = None, client: HeyGenClient | None = None) -> dict:
    """Upload photos as looks on one HeyGen character. Without group_id the first photo creates the character
    and its look carries the character name; later photos use look_names."""
    client = client or HeyGenClient()
    if not client.configured:
        raise HeyGenError("HeyGen is not connected. Add the API key in Connections.", 401, "not_configured")
    name = re.sub(r"\s+", " ", name or "").strip()[:80]
    group = (group_id or "").strip()
    if not name:
        raise ValueError("Name the avatar.")
    if group and not SAFE_ID.fullmatch(group):
        raise ValueError("That is not a HeyGen avatar group id.")
    if not photos:
        raise ValueError("Add at least one photo.")
    if len(photos) > MAX_PHOTOS:
        raise ValueError(f"Add up to {MAX_PHOTOS} photos at a time.")
    prepared = [prepare_photo(raw) for _, raw in photos]
    labels = [re.sub(r"\s+", " ", str(label or "")).strip()[:80] for label in (look_names or [])]
    looks: list[dict] = []
    for index, data in enumerate(prepared):
        digest = hashlib.sha256(data).hexdigest()
        label = (labels[index] if index < len(labels) else "") or f"{name} {index + 1}"
        asset = client.upload_asset(f"{digest[:16]}.jpg", data, "image/jpeg", idempotency_key=f"pmos-asset-{digest[:48]}")
        item = _create_look(client, label if group else name, asset["asset_id"], group,
                            f"pmos-photo-{digest[:40]}-{group or 'new'}")
        group = group or item.get("group_id") or ""
        _save_source(group, item["id"], data)
        looks.append(look_out(item))
    _catalog_cache.clear()
    return {"group_id": group, "name": name, "looks": looks}


def list_voices(*, voice_type: str = "public", language: str | None = None, gender: str | None = None,
                token: str | None = None) -> dict:
    client = HeyGenClient()

    def load() -> dict:
        body = client.voices(voice_type=voice_type, language=language, gender=gender, token=token, limit=100)
        items = [{
            "id": item["voice_id"], "name": item.get("name") or "Untitled voice", "language": item.get("language") or "",
            "gender": item.get("gender") or "", "type": item.get("type") or voice_type,
            "preview_audio_url": item.get("preview_audio_url") or "",
        } for item in body.get("data") or [] if item.get("voice_id")]
        return {"items": items, "has_more": bool(body.get("has_more")), "next_token": body.get("next_token") or ""}

    return _cached(("voices", _key_tag(client), voice_type, language or "", gender or "", token or ""), load)


def voice_engine(voice_id: str, client: HeyGenClient) -> str:
    if not voice_id:
        return ""

    def load() -> dict:
        body = client.voices(voice_type="private", engine="elevenlabs", limit=100)
        return {"ids": [item.get("voice_id") for item in body.get("data") or []]}

    try:
        ids = _cached(("voice-engine", _key_tag(client), "elevenlabs"), load)["ids"]
    except HeyGenError:
        log.warning("could not read the ElevenLabs voice list; rendering with HeyGen's default voice engine")
        return ""
    return "elevenlabs" if voice_id in ids else ""


def default_voice() -> dict:
    cartesia = (settings.avatar_cartesia_voice_id or "").strip()
    if cartesia:
        return {"id": f"cartesia:{cartesia}", "name": (settings.avatar_cartesia_voice_name or "").strip() or "Cartesia voice"}
    eleven = (settings.elevenlabs_voice_id or "").strip()
    if eleven:
        return {"id": f"elevenlabs:{eleven}", "name": (settings.elevenlabs_voice_name or "").strip() or "ElevenLabs voice"}
    voice_id = (settings.heygen_voice_id or "").strip()
    name = (settings.heygen_voice_name or "").strip() or "Default voice"
    return {"id": voice_id, "name": name if voice_id else ""}


def narrator(voice_id: str) -> tuple[str, str]:
    """("cartesia" | "elevenlabs", provider voice id) for voices narrated here; ("", "") for HeyGen voices."""
    provider, _, voice = (voice_id or "").partition(":")
    return (provider, voice) if provider in NARRATORS and voice else ("", "")


def _clamp(value: float, bounds: tuple[float, float]) -> float:
    return round(min(max(float(value or 1.0), bounds[0]), bounds[1]), 2)


def _decode_clip(filename: str, data: bytes) -> tuple[array.array, int]:
    if Path(filename).suffix.lower() == ".wav":
        try:
            with wave.open(io.BytesIO(data)) as clip:
                if clip.getnchannels() == 1 and clip.getsampwidth() == 2:
                    return array.array("h", clip.readframes(clip.getnframes())), clip.getframerate()
        except (wave.Error, EOFError):
            pass
    from app.services.marketing_video import binary, run

    with tempfile.TemporaryDirectory() as folder:
        source, target = Path(folder) / f"source{Path(filename).suffix.lower()}", Path(folder) / "clip.wav"
        source.write_bytes(data)
        try:
            run([binary("ffmpeg"), "-y", "-loglevel", "error", "-i", str(source), "-t", str(CLIP_SECONDS), "-ac", "1",
                 "-ar", str(CLIP_RATE), "-c:a", "pcm_s16le", str(target)], timeout=120)
        except RuntimeError as exc:
            raise ValueError(f"{filename} could not be read as audio.") from exc
        with wave.open(str(target)) as clip:
            return array.array("h", clip.readframes(clip.getnframes())), clip.getframerate()


def _highpass(samples: list[float], rate: int, cutoff: float) -> list[float]:
    # Fourth-order Butterworth as two biquads: -10 dB at 60 Hz, flat by 110 Hz where a low male voice starts.
    for q in (0.5412, 1.3066):
        w0 = 2 * math.pi * cutoff / rate
        alpha, cos_w0 = math.sin(w0) / (2 * q), math.cos(w0)
        a0 = 1 + alpha
        b0, b1, b2 = (1 + cos_w0) / 2 / a0, -(1 + cos_w0) / a0, (1 + cos_w0) / 2 / a0
        a1, a2 = -2 * cos_w0 / a0, (1 - alpha) / a0
        x1 = x2 = y1 = y2 = 0.0
        out = []
        for x0 in samples:
            y0 = b0 * x0 + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2
            out.append(y0)
            x2, x1, y2, y1 = x1, x0, y1, y0
        samples = out
    return samples


def prepare_clip(filename: str, data: bytes) -> tuple[bytes, float]:
    """Mono 16-bit WAV of at most 60 s with room rumble removed: an instant clone copies whatever it hears."""
    pcm, rate = _decode_clip(filename, data)
    pcm = pcm[: rate * CLIP_SECONDS]
    seconds = len(pcm) / rate if rate else 0
    if seconds < MIN_CLIP_SECONDS:
        raise ValueError(f"The recording needs at least {MIN_CLIP_SECONDS} seconds of speech; 30–60 seconds clones best.")
    filtered = _highpass([s / 32768 for s in pcm], rate, CLIP_HIGHPASS_HZ)
    gain = 0.89 / max(max(abs(s) for s in filtered), 1e-6)
    out = array.array("h", (max(-32767, min(32767, int(s * gain * 32767))) for s in filtered))
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as clip:
        clip.setnchannels(1)
        clip.setsampwidth(2)
        clip.setframerate(rate)
        clip.writeframes(out.tobytes())
    return buffer.getvalue(), round(seconds, 1)


def clone_cartesia_voice(name: str, filename: str, data: bytes, *, language: str = "hi", accent: str = "standard-hindi",
                         speaks: tuple[str, ...] = ("indian-english",), make_default: bool = False,
                         client: CartesiaClient | None = None) -> dict:
    """Clone in the language the speaker recorded in, then add the accents the scripts are written in."""
    name = re.sub(r"\s+", " ", name or "").strip()[:80]
    if not name:
        raise ValueError("Name the voice before cloning it.")
    if Path(filename).suffix.lower() not in SAMPLE_MIME:
        raise ValueError(f"{filename} is not a supported audio file. Use M4A, MP3, WAV, AAC, OGG, FLAC or WebM.")
    if len(data) > MAX_SAMPLE_BYTES:
        raise ValueError(f"{filename} is larger than 25 MB.")
    clip, seconds = prepare_clip(filename, data)
    client = client or CartesiaClient()
    voice_id = str(client.clone_voice(name, ("voice.wav", clip, "audio/wav"), language=language, accent=accent,
                                      description=f"Presenter voice for {brand_name()} avatar videos.")["id"])
    extra = [item for item in speaks if item and item != accent]
    accent_error = ""
    if extra:
        try:
            client.add_accents(voice_id, extra)
        except CartesiaError as exc:
            # The clone already exists (and is billed); keep it and report the missing accent.
            accent_error = str(exc)
    if SAFE_ID.fullmatch(voice_id):
        (AVATAR_DIR / "voices").mkdir(parents=True, exist_ok=True)
        (AVATAR_DIR / "voices" / f"{voice_id}.wav").write_bytes(clip)
    if make_default:
        from app.services.workspace import save_connection_settings

        save_connection_settings("cartesia", {"avatar_voice_id": voice_id, "avatar_voice_name": name})
    return {"voice_id": voice_id, "id": f"cartesia:{voice_id}", "name": name, "language": language,
            "accents": [accent, *(item for item in extra if not accent_error)], "accent_error": accent_error,
            "clip_seconds": seconds, "default": make_default}


def clone_elevenlabs_voice(name: str, samples: list[tuple[str, bytes]], *, remove_background_noise: bool = False,
                           make_default: bool = False, client: ElevenLabsClient | None = None) -> dict:
    name = re.sub(r"\s+", " ", name or "").strip()[:80]
    if not name:
        raise ValueError("Name the voice before cloning it.")
    if not samples:
        raise ValueError("Add at least one recording of the speaker.")
    prepared = []
    for filename, data in samples:
        mime = SAMPLE_MIME.get(Path(filename).suffix.lower())
        if not mime:
            raise ValueError(f"{filename} is not a supported audio file. Use M4A, MP3, WAV, AAC, OGG, FLAC or WebM.")
        if len(data) > MAX_SAMPLE_BYTES:
            raise ValueError(f"{filename} is larger than 25 MB.")
        prepared.append((Path(filename).name, data, mime))
    client = client or ElevenLabsClient()
    body = client.clone_voice(name, prepared, remove_background_noise=remove_background_noise,
                              description=f"Presenter voice for {brand_name()} avatar videos.")
    if make_default:
        from app.services.workspace import save_connection_settings

        save_connection_settings("elevenlabs", {"voice_id": body["voice_id"], "voice_name": name})
    return {"voice_id": body["voice_id"], "id": f"elevenlabs:{body['voice_id']}", "name": name,
            "requires_verification": bool(body.get("requires_verification")), "default": make_default}


def _pronunciation_dictionary(script: str) -> str:
    from app.services.marketing_video import pronunciation_dict_id

    try:
        return pronunciation_dict_id(script)
    except (OSError, ValueError):
        return ""


def narration_config(row: AvatarVideo) -> dict:
    provider, voice = narrator(row.voice_id)
    speed = clean_options(row.options)["speed"]
    if provider == "cartesia":
        # locale picks the language; accent (one the voice lists, e.g. its native standard-hindi) makes it
        # speak that language the way the speaker does instead of Cartesia's localized accent.
        return {"provider": provider, "voice": voice, "model": CARTESIA_MODEL,
                "locale": (settings.avatar_cartesia_locale or "").strip() or CARTESIA_LOCALE,
                "accent": (settings.avatar_cartesia_accent or "").strip(),
                "speed": _clamp(speed, CARTESIA_SPEED), "dictionary": _pronunciation_dictionary(row.script or "")}
    return {"provider": provider, "voice": voice, "model": ELEVENLABS_MODEL,
            "voice_settings": {**ELEVEN_VOICE_SETTINGS, "speed": _clamp(speed, ELEVEN_SPEED)}}


def narration_text(row: AvatarVideo) -> str:
    script, pauses = (row.script or "").strip(), clean_options(row.options)["pauses"]
    if narrator(row.voice_id)[0] == "cartesia":
        return escape_outside_breaks(pace_script(script, CARTESIA_SENTENCE_BREAK, CARTESIA_PARAGRAPH_BREAK) if pauses else script)
    return pace_script(script) if pauses else script


def narration_key(row: AvatarVideo) -> str:
    payload = json.dumps([row.voice_id, narration_text(row), narration_config(row)], sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def narration_info(row: AvatarVideo) -> dict | None:
    info = (row.result or {}).get("narration") or {}
    if not info or not (video_folder(row.id) / NARRATION_FILE).is_file():
        return None
    return {**info, "stale": info.get("key") != narration_key(row),
            "url": f"/api/avatar-videos/{row.id}/files/{NARRATION_FILE}"}


def narrate(db: Session, row: AvatarVideo, client: CartesiaClient | ElevenLabsClient | None = None) -> dict:
    """Render the narration once per script/voice/speed so previews and renders reuse it."""
    config = narration_config(row)
    if not config["provider"]:
        raise ValueError("This video uses a HeyGen voice, which speaks inside HeyGen. "
                         "Pick a Cartesia or ElevenLabs voice to preview narration.")
    script = (row.script or "").strip()
    if word_count(script) < 3:
        raise ValueError("Write a script of at least a few words before generating narration.")
    current = narration_info(row)
    if current and not current["stale"]:
        return current
    text = narration_text(row)
    if config["provider"] == "cartesia":
        client = client or CartesiaClient()
        audio = client.speech(config["voice"], text, model_id=config["model"], locale=config["locale"],
                              accent=config["accent"], speed=config["speed"], pronunciation_dict_id=config["dictionary"])
    else:
        client = client or ElevenLabsClient()
        audio = client.speech(config["voice"], text, model_id=config["model"], voice_settings=config["voice_settings"])
    folder = video_folder(row.id)
    folder.mkdir(parents=True, exist_ok=True)
    partial = folder / "narration.download.mp3"
    partial.write_bytes(audio)
    partial.replace(folder / NARRATION_FILE)
    _merge_result(row, {"narration": {
        "key": narration_key(row), "file": NARRATION_FILE, "seconds": round(len(audio) * 8 / NARRATION_BITRATE, 1),
        "characters": len(text), "provider": config["provider"], "voice_id": config["voice"], "model": config["model"],
        "created_at": _iso(_now()),
    }})
    db.commit()
    return narration_info(row)


def video_out(row: AvatarVideo) -> dict:
    options = clean_options(row.options)
    result = row.result or {}
    return {
        "id": row.id, "title": row.title, "feature_id": row.feature_id, "script": row.script,
        "words": word_count(row.script), "estimated_seconds": estimated_seconds(row.script, options["speed"]),
        "avatar": {"id": row.avatar_id, "name": row.avatar_name, "type": row.avatar_type, "preview_url": row.avatar_preview_url},
        "voice": {"id": row.voice_id, "name": row.voice_name},
        "options": options, "status": row.status, "error": row.error or "",
        "heygen_video_id": row.heygen_video_id, "attempt": row.attempt, "revision": row.revision,
        "duration": result.get("duration"), "video_page_url": result.get("video_page_url") or "",
        "retry_downloads_only": _can_redownload(row),
        "narration": narration_info(row),
        "assets": [{**asset, "url": f"/api/avatar-videos/{row.id}/files/{asset['filename']}"} for asset in row.assets or []],
        "created_at": _iso(row.created_at), "updated_at": _iso(row.updated_at),
        "submitted_at": _iso(row.submitted_at), "completed_at": _iso(row.completed_at),
    }


def apply_fields(row: AvatarVideo, data: dict) -> None:
    for key in ("title", "script", "avatar_id", "avatar_name", "avatar_type", "avatar_preview_url", "voice_id", "voice_name"):
        if key in data:
            setattr(row, key, str(data[key] or "").strip())
    if not row.voice_id:
        voice = default_voice()
        row.voice_id, row.voice_name = voice["id"], voice["name"]
    if "feature_id" in data:
        row.feature_id = data["feature_id"] or None
    if "options" in data:
        row.options = clean_options(data["options"])
    row.updated_at = _now()


def duplicate(db: Session, row: AvatarVideo) -> AvatarVideo:
    copy = AvatarVideo(
        title=(f"{row.title} (copy)" if row.title else "")[:180], feature_id=row.feature_id, script=row.script,
        avatar_id=row.avatar_id, avatar_name=row.avatar_name, avatar_type=row.avatar_type,
        avatar_preview_url=row.avatar_preview_url, voice_id=row.voice_id, voice_name=row.voice_name,
        options=clean_options(row.options), status="draft", result={}, assets=[],
    )
    db.add(copy)
    db.commit()
    db.refresh(copy)
    return copy


def video_folder(video_id: int) -> Path:
    return AVATAR_DIR / str(int(video_id))


def delete(db: Session, row: AvatarVideo) -> None:
    if row.status in ACTIVE:
        raise ValueError("This video is still rendering. Wait for HeyGen to finish before deleting it.")
    folder = video_folder(row.id).resolve()
    if folder.parent == AVATAR_DIR.resolve() and folder.is_dir():
        shutil.rmtree(folder, ignore_errors=True)
    db.delete(row)
    db.commit()


def validate_for_render(row: AvatarVideo) -> None:
    if not row.avatar_id:
        raise ValueError("Choose an avatar before rendering.")
    script = (row.script or "").strip()
    if word_count(script) < 3:
        raise ValueError("Write a script of at least a few words before rendering.")
    if len(script) > MAX_SCRIPT_CHARS:
        raise ValueError(f"One HeyGen render accepts up to {MAX_SCRIPT_CHARS} characters. Shorten the script.")
    if clean_options(row.options)["pauses"] and len(pace_script(script)) > MAX_SCRIPT_CHARS:
        raise ValueError(f"With sentence pauses added the script passes HeyGen's {MAX_SCRIPT_CHARS}-character limit. "
                         "Shorten it or turn pauses off.")


def build_request(row: AvatarVideo, *, voice_engine: str = "", audio_asset_id: str = "") -> dict:
    options = clean_options(row.options)
    body: dict = {
        "type": "avatar", "avatar_id": row.avatar_id,
        "title": (row.title or f"Avatar video {row.id}")[:180],
        "aspect_ratio": options["aspect_ratio"], "resolution": options["resolution"],
        "caption": {"file_format": "srt"}, "output_format": "mp4",
    }
    if audio_asset_id:
        # Uploaded narration bypasses HeyGen TTS; speed and pauses are already in the audio.
        body["audio_asset_id"] = audio_asset_id
    else:
        body["script"] = pace_script(row.script) if options["pauses"] else row.script.strip()
    if row.voice_id and not audio_asset_id:
        body["voice_id"] = row.voice_id
        # HeyGen applies voice_settings only when an explicit voice_id accompanies the script.
        voice: dict = {}
        if abs(options["speed"] - 1.0) > 0.001:
            voice["speed"] = options["speed"]
        if voice_engine == "elevenlabs":
            voice["engine_settings"] = {"engine_type": "elevenlabs", "model": ELEVENLABS_MODEL}
        if voice:
            body["voice_settings"] = voice
    if options["engine"] != "avatar_iv":
        body["engine"] = {"type": options["engine"]}
    elif row.avatar_type == "photo_avatar":
        # Photo-avatar controls; Avatar V rejects expressiveness, and motion prompts without a digital-twin reference.
        body["expressiveness"] = options["expressiveness"]
        if options["motion_prompt"]:
            body["motion_prompt"] = options["motion_prompt"]
    if options["background"]:
        body["background"] = {"type": "color", "value": options["background"]}
    return body


def _merge_result(row: AvatarVideo, patch: dict) -> None:
    row.result = {**(row.result or {}), **patch}
    flag_modified(row, "result")


def _fail(db: Session, row: AvatarVideo, message: str) -> None:
    row.status = "failed"
    row.error = (message or "HeyGen could not render this video.")[:800]
    row.updated_at = _now()
    db.commit()


def _can_redownload(row: AvatarVideo) -> bool:
    result = row.result or {}
    return bool(row.status == "failed" and row.heygen_video_id and result.get("remote_status") == "completed"
                and result.get("rendered_revision") == row.revision)


def submit(db: Session, row: AvatarVideo, client: HeyGenClient | None = None) -> AvatarVideo:
    client = client or HeyGenClient()
    if not client.configured:
        raise HeyGenError("HeyGen is not connected. Add the API key in Connections.", 401, "not_configured")
    with _submit_lock:
        db.refresh(row)
        if row.status not in EDITABLE:
            raise ValueError("This video is already rendering or finished. Duplicate it to make another version.")
        redownload = _can_redownload(row)
        if redownload:
            # HeyGen already rendered (and billed) this exact revision; only the local copy failed.
            _merge_result(row, {"download_attempts": 0})
            row.status, row.error, row.updated_at = "downloading", "", _now()
            db.commit()
    if redownload:
        return refresh(db, row, force=True, client=client)
    with _submit_lock:
        db.refresh(row)
        if row.status not in EDITABLE:
            raise ValueError("This video is already rendering or finished. Duplicate it to make another version.")
        validate_for_render(row)
        row.attempt = (row.attempt or 0) + 1
        row.status, row.error, row.heygen_video_id = "submitting", "", ""
        narration = (row.result or {}).get("narration")
        row.assets, row.result = [], ({"narration": narration} if narration else {})
        row.submitted_at = row.completed_at = None
        row.updated_at = _now()
        db.commit()
    audio_asset_id, engine = "", ""
    if narrator(row.voice_id)[0]:
        try:
            narrate(db, row)
            audio = (video_folder(row.id) / NARRATION_FILE).read_bytes()
            upload = client.upload_asset(NARRATION_FILE, audio, "audio/mpeg",
                                         idempotency_key=f"pmos-audio-{hashlib.sha256(audio).hexdigest()[:48]}")
        except (CartesiaError, ElevenLabsError, HeyGenError, ValueError) as exc:
            _fail(db, row, str(exc))
            raise
        audio_asset_id = str(upload["asset_id"])
    else:
        engine = voice_engine(row.voice_id, client)
    body = build_request(row, voice_engine=engine, audio_asset_id=audio_asset_id)
    key = f"pmos-avatar-{row.id}-r{row.revision}-a{row.attempt}"
    for retry in range(2):
        try:
            data = client.create_video(body, idempotency_key=key + (f"-{retry}" if retry else ""))
            break
        except HeyGenError as exc:
            # A just-uploaded narration asset is briefly "not found"; no video exists yet, so one retry is safe.
            if not (audio_asset_id and retry == 0 and (exc.status == 404 or "not found" in str(exc).lower())):
                _fail(db, row, str(exc))
                raise
            time.sleep(PHOTO_RETRY_SECONDS)
    now = _now()
    row.heygen_video_id = str(data["video_id"])
    row.status = "rendering" if str(data.get("status") or "").lower() == "processing" else "submitted"
    row.submitted_at = row.checked_at = row.updated_at = now
    _merge_result(row, {"rendered_revision": row.revision, "remote_status": str(data.get("status") or ""),
                        "request": {k: v for k, v in body.items() if k != "script"}})
    db.commit()
    return row


def _downloading(video_id: int) -> bool:
    with _downloads_lock:
        return video_id in _downloads


def refresh(db: Session, row: AvatarVideo, *, force: bool = False, client: HeyGenClient | None = None,
            quick: bool = False) -> AvatarVideo:
    now = _now()
    if row.status == "submitting":
        if row.updated_at and now - row.updated_at > SUBMIT_STALE:
            _fail(db, row, "Submission to HeyGen was interrupted. Check the HeyGen dashboard before rendering again.")
        return row
    if row.status not in {"submitted", "rendering", "downloading"} or not row.heygen_video_id:
        return row
    if _downloading(row.id):
        return row
    if not force and row.checked_at and (now - row.checked_at).total_seconds() < POLL_SECONDS:
        return row
    client = client or HeyGenClient()
    row.checked_at = now
    try:
        detail = client.video(row.heygen_video_id, attempts=1 if quick else 3, timeout=10 if quick else 30)
    except HeyGenError as exc:
        if exc.status == 404:
            _fail(db, row, "HeyGen no longer has this video. Render it again.")
        else:
            _merge_result(row, {"poll_error": str(exc)})
            db.commit()
        return row
    remote = str(detail.get("status") or "").lower()
    _merge_result(row, {"remote_status": remote, "duration": detail.get("duration"),
                        "video_page_url": detail.get("video_page_url") or "", "failure_code": detail.get("failure_code") or "",
                        "poll_error": ""})
    if remote == "failed":
        _fail(db, row, detail.get("failure_message") or "HeyGen could not render this video.")
    elif remote == "completed":
        row.status, row.updated_at = "downloading", now
        db.commit()
        start_download(db, row, detail, client)
    else:
        row.status = "rendering" if remote == "processing" else "submitted"
        if row.submitted_at and now - row.submitted_at > RENDER_TIMEOUT:
            _fail(db, row, "HeyGen did not finish within 6 hours. Check the HeyGen dashboard, then render again.")
        else:
            db.commit()
    return row


def refresh_active(db: Session) -> None:
    rows = db.query(AvatarVideo).filter(AvatarVideo.status.in_(ACTIVE)).all()
    if not rows:
        return
    client = HeyGenClient()
    for row in rows:
        try:
            refresh(db, row, client=client, quick=True)
        except Exception:
            db.rollback()
            log.exception("could not refresh avatar video %s", row.id)


def start_download(db: Session, row: AvatarVideo, detail: dict, client: HeyGenClient) -> None:
    with _downloads_lock:
        if row.id in _downloads:
            return
        _downloads.add(row.id)
    if not BACKGROUND_DOWNLOADS:
        try:
            download_assets(db, row, detail, client)
        finally:
            with _downloads_lock:
                _downloads.discard(row.id)
        return
    spawn(_download_job, row.id, detail, client, name=f"avatar-download-{row.id}")


def _download_job(video_id: int, detail: dict, client: HeyGenClient) -> None:
    session = SessionLocal()
    try:
        row = session.get(AvatarVideo, video_id)
        if row and row.status == "downloading":
            download_assets(session, row, detail, client)
    except Exception:
        session.rollback()
        log.exception("avatar video %s download failed", video_id)
    finally:
        session.close()
        with _downloads_lock:
            _downloads.discard(video_id)


def check_mp4(path: Path) -> None:
    with path.open("rb") as handle:
        head = handle.read(12)
    if path.stat().st_size < 2048 or head[4:8] != b"ftyp":
        raise ValueError("HeyGen returned a file that is not a playable MP4.")


def _thumbnail_name(url: str) -> str:
    suffix = Path(urlparse(url).path).suffix.lower()
    return f"thumbnail{suffix if suffix in {'.png', '.webp'} else '.jpg'}"


def _asset(path: Path, kind: str) -> dict:
    return {"filename": path.name, "kind": kind, "mime": MIME.get(path.suffix.lower(), "application/octet-stream"),
            "size": path.stat().st_size}


def _download_failed(db: Session, row: AvatarVideo, message: str) -> None:
    attempts = int((row.result or {}).get("download_attempts") or 0) + 1
    _merge_result(row, {"download_attempts": attempts})
    if attempts >= MAX_DOWNLOAD_ATTEMPTS:
        _fail(db, row, f"HeyGen finished the video but the download kept failing: {message} Retry to download again without re-rendering.")
        return
    row.error, row.updated_at = message[:800], _now()
    db.commit()


def download_assets(db: Session, row: AvatarVideo, detail: dict, client: HeyGenClient) -> None:
    url = detail.get("video_url")
    if not url:
        _download_failed(db, row, "HeyGen marked the video complete but returned no file link.")
        return
    folder = video_folder(row.id)
    folder.mkdir(parents=True, exist_ok=True)
    partial = folder / "avatar.download.mp4"
    try:
        client.download(url, partial)
        check_mp4(partial)
    except (HeyGenError, ValueError, OSError) as exc:
        partial.unlink(missing_ok=True)
        _download_failed(db, row, str(exc))
        return
    video = folder / "avatar.mp4"
    partial.replace(video)
    assets = [_asset(video, "video")]
    for key, name, kind in (("subtitle_url", "captions.srt", "captions"), ("thumbnail_url", None, "thumbnail")):
        link = detail.get(key)
        if not link:
            continue
        target = folder / (name or _thumbnail_name(link))
        try:
            client.download(link, target, timeout=60)
            assets.append(_asset(target, kind))
        except (HeyGenError, OSError):
            log.warning("avatar video %s: optional %s download failed", row.id, kind)
    row.assets = assets
    row.status, row.error = "completed", ""
    row.completed_at = row.updated_at = _now()
    db.commit()


SCRIPT_SYSTEM = """You write scripts for one presenter speaking straight to camera in a short product video for [[product]] buyers: [[personas]].

Rules:
- Spoken English only. Short sentences, one idea each. Contractions are fine.
- No stage directions, scene notes, speaker labels, emojis, hashtags, markdown, bullet points or bracketed cues.
- Open with the buyer's problem in one or two sentences, then what the feature does, then the outcome for their team.
- Use only facts in the brief. Never invent metrics, customer names, integrations, prices or claims.
- End with one plain call to action, such as asking their [[company]] account team for a walkthrough.
- Land within 10 percent of target_words.

Return JSON only: {"title": "a plain title of at most 70 characters", "script": "the spoken script"}"""


def _clean_script(text: str) -> str:
    lines = []
    for line in str(text or "").splitlines():
        stripped = line.strip()
        if not stripped or re.fullmatch(r"[\[(].*[\])]", stripped):
            continue
        lines.append(re.sub(r"^[-*•#>]+\s*", "", stripped).replace("**", ""))
    return re.sub(r"[ \t]+", " ", "\n\n".join(lines)).strip()[:MAX_SCRIPT_CHARS]


def script_ready() -> bool:
    from app.clients.llm import LLMClient, model_for

    return LLMClient(model=model_for(SCRIPT_SURFACE), surface=SCRIPT_SURFACE).configured


def draft_script(db: Session, *, feature_id: int | None = None, brief: str = "", seconds: int = 60, angle: str = "") -> dict:
    from app.clients.llm import chat_json, model_for

    feature = db.get(MarketingFeature, feature_id) if feature_id else None
    if feature_id and not feature:
        raise LookupError("That feature no longer exists.")
    if not feature and not brief.strip():
        raise ValueError("Choose a feature or describe what the video should cover.")
    if not script_ready():
        raise RuntimeError("The marketing writing model is not configured. Write the script by hand or connect AI models in Connections.")
    payload = {
        "target_seconds": seconds, "target_words": round(seconds * WORDS_PER_MINUTE / 60),
        "angle": angle.strip(), "extra_brief": brief.strip(),
        "feature": {
            "name": feature.name, "module": feature.module, "summary": feature.summary, "use_case": feature.description,
            "audience": feature.audience, "benefit": feature.benefit, "hook": feature.hook,
        } if feature else None,
    }
    out = chat_json(SCRIPT_SURFACE, SCRIPT_SYSTEM, payload, temperature=0.4, max_retries=1, timeout=120)
    script = _clean_script(out.get("script") or "")
    if word_count(script) < 10:
        raise RuntimeError("The writing model returned an unusable script. Try again or write it by hand.")
    title = re.sub(r"\s+", " ", str(out.get("title") or (feature.name if feature else "")).strip())[:70]
    return {"title": title, "script": script, "words": word_count(script), "estimated_seconds": estimated_seconds(script),
            "model": model_for(SCRIPT_SURFACE)}
