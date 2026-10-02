"""Reusable launch film: measured voice, safe typography, real MP4 checks."""
from __future__ import annotations

import html
import base64
import hashlib
import json
import math
import os
import platform
import re
import shutil
import subprocess
import threading
import time
from pathlib import Path
from functools import lru_cache

from app.config import ROOT, Settings, settings
from app.services.brand import artifact_path
from app.services.marketing_voice import save_sse_take, load_timing, bind_launch_cues, bind_narrated_film, cue_indices, pad_narration, stitch_takes
from app.services.marketing_film_gates import craft_for_scenes, evaluate_encoded_film, launch_craft, launch_theme

def _remotion_dir() -> Path:
    """REMOTION_DIR when set, otherwise the vendored render/remotion."""
    configured = (settings.env_value("remotion_dir") or "").strip()
    if configured:
        return Path(configured).expanduser()
    return ROOT / "render" / "remotion"


REMOTION_DIR = _remotion_dir()
_RENDER_LOCK = threading.Lock()
# Speed stays at the model default: Cartesia paces a well-punctuated transcript itself, and pushing it
# faster flattens the phrasing the script was written for.
VOICE_PROFILE = {"version": "siya-performed-v8", "voice_id": "4459a9a5-69d6-4680-b970-e13dc51845b6",
                 "name": "Siya", "speed": 0.98, "emotion": "confident", "preview_wpm": 170, "preview_voice": "Samantha"}
EXAMPLE_VOICE = {"version": "example-customer-v2", "voice_id": "cbaf8084-f009-4838-a096-07ee2e6612b1",
                 "name": "Maya", "speed": 1.0, "emotion": "calm", "preview_wpm": 165, "preview_voice": "Veena"}
# Call participants are the operator's own Cartesia clones of real Indian callers. They carry no
# emotion tag: a directed emotion is what makes a cloned voice sound read rather than spoken.
# English turns read clearer in "en"; the Hindi model slurs English words. At 1.0 Geeta runs near
# 230 wpm, faster than anyone talks on a call, so she sits at 0.95 (about 185 wpm).
AGENT_VOICE = {"version": "geeta-1-call-v1", "voice_id": "b567e37e-2f09-4ad4-a0a0-aeeb59f0d528",
               "name": "Geeta", "language": "en", "speed": 0.95, "emotion": "confident", "preview_wpm": 150, "preview_voice": "Veena"}
CUSTOMER_VOICE = {"version": "pranika-handset-v1", "voice_id": "dc3e49d2-7b1f-40d6-8350-3fa51e85d4fe",
                  "name": "Pranika", "language": "en", "speed": 1.0, "emotion": "confident", "preview_wpm": 155, "preview_voice": "Samantha",
                  "line": "handset"}
VOICE_PROFILES = {"narrator": VOICE_PROFILE, "example": EXAMPLE_VOICE, "agent": AGENT_VOICE, "customer": CUSTOMER_VOICE}
AUDIO_LEAD_FRAMES = 3
# Cartesia's primary emotions are the ones that sound like people. "confident" is the old
# presenter default; omitting it lets Sonic read the sentence instead of performing a tag.
_NATURAL_DEFAULT = {"confident"}


def tts_generation_config(profile: dict) -> dict:
    """English may carry a directed emotion; Hindi must not. Over-direction is what makes clones sound recited."""
    config = {"speed": float(profile.get("speed") or 1.0)}
    language = profile.get("language") or "en"
    emotion = profile.get("emotion")
    if language == "en" and emotion and emotion not in _NATURAL_DEFAULT:
        config["emotion"] = emotion
    return config


def narrator_id() -> str:
    return getattr(voice_settings(), "marketing_cartesia_voice_id", "") or VOICE_PROFILE["voice_id"]


def pronunciation_lexicon() -> dict:
    from app.services.brand import brand_pack

    pack = brand_pack()
    path = ROOT / f"backend/app/static/artifacts/{pack}-pronunciation.json"
    return json.loads(path.read_text()) if pack and path.is_file() else {}


def brand_pronunciation_id() -> str:
    return pronunciation_lexicon().get("id", "")


def pronunciation_dict_id(text: str) -> str:
    """Attach the private lexicon to any script using a term the model reads wrong.

    A mispronounced word is fixed once in the lexicon, never by respelling visible copy.
    """
    lexicon = pronunciation_lexicon()
    if not lexicon.get("id"):
        return ""
    for item in lexicon.get("items", []):
        flags = 0 if item.get("case_sensitive") else re.IGNORECASE
        if re.search(rf"\b{re.escape(item['text'])}\b", text, flags):
            return lexicon["id"]
    return ""


def voice_take_key(text: str, *, preview=False, profile=None) -> str:
    """A delivery change must not silently reuse yesterday's flat narration."""
    profile = profile or VOICE_PROFILE
    config = voice_settings()
    return hashlib.sha256(json.dumps([text, "preview" if preview else "production",
        profile["voice_id"] if profile.get("explicit_voice") else narrator_id() if profile.get("name") == VOICE_PROFILE["name"] else profile["voice_id"], config.cartesia_model, profile, tts_generation_config(profile), pronunciation_dict_id(text) or None], sort_keys=True).encode()).hexdigest()[:12]


def video_cache_key(video: dict) -> str:
    """Invalidate rendered films when the composition, voice or design contract changes."""
    digest = hashlib.sha256(json.dumps(video, sort_keys=True).encode())
    voice = voice_settings()
    digest.update(brand_pronunciation_id().encode())
    digest.update(json.dumps([voice.cartesia_voice_id, voice.cartesia_model, narrator_id(), VOICE_PROFILE, EXAMPLE_VOICE, AGENT_VOICE, CUSTOMER_VOICE]).encode())
    launch_sources = sorted((REMOTION_DIR / "src/marketing/launch").glob("*.tsx"))
    for path in [REMOTION_DIR / "src/marketing/Film.tsx", REMOTION_DIR / "src/marketing/World.tsx", REMOTION_DIR / "src/marketing/PiiFilm.tsx", REMOTION_DIR / "src/marketing/PiiLaunch.tsx", REMOTION_DIR / "src/marketing/PiiCallFirst.tsx", REMOTION_DIR / "src/marketing/ExamplePanels.tsx", REMOTION_DIR / "src/marketing/Motifs.tsx", REMOTION_DIR / "src/marketing/kit/IPhone.tsx", REMOTION_DIR / "src/marketing/kit/Cards.tsx", REMOTION_DIR / "src/marketing/kit/ProductUI.tsx", *launch_sources, REMOTION_DIR / "src/marketing/index.tsx", REMOTION_DIR / "scripts/render-marketing.mjs",
                 Path(__file__), Path(__file__).with_name("marketing_voice.py"), Path(__file__).with_name("marketing_performance.py"), Path(__file__).with_name("marketing_score.py"), Path(__file__).with_name("marketing_film_gates.py"),
                 artifact_path("marketing-video-design.md")]:
        digest.update(path.read_bytes())
    return digest.hexdigest()[:16]


REFERENCE_VOICE_ENV = (ROOT / "render" / "remotion" / ".env",)


@lru_cache(maxsize=1)
def _reference_voice_settings():
    return Settings(_env_file=[path for path in (*REFERENCE_VOICE_ENV, ROOT / ".env") if path.is_file()])


def voice_settings():
    """The workspace's Cartesia connection. A laptop install may still fall back to a git-ignored
    `render/remotion/.env` (read-only); hosted installs never read files."""
    if settings.cartesia_api_key or settings.is_production:
        return settings
    reference = _reference_voice_settings()
    return reference if reference.cartesia_api_key else settings


def binary(name: str) -> str:
    found = shutil.which(name)
    if found:
        return found
    os_name = {"Darwin": "darwin", "Linux": "linux", "Windows": "win32"}.get(platform.system(), "linux")
    arch = "arm64" if platform.machine() in {"arm64", "aarch64"} else "x64"
    candidate = REMOTION_DIR / "node_modules" / "@remotion" / f"compositor-{os_name}-{arch}" / name
    if candidate.is_file():
        return str(candidate)
    raise RuntimeError(f"The video renderer needs {name}. Run npm install in render/remotion.")


def video_status() -> dict:
    voice_config = voice_settings()
    cloud_voice = bool(voice_config.cartesia_api_key and narrator_id())
    try:
        ready = bool(binary("ffmpeg") and binary("ffprobe") and shutil.which("node") and
                     (REMOTION_DIR / "node_modules" / "@remotion" / "renderer").is_dir())
    except RuntimeError:
        ready = False
    voice = f"Cartesia female narrator ({VOICE_PROFILE['name']})" if cloud_voice else "Mac system voice" if shutil.which("say") else "Not configured"
    return {"ready": ready and cloud_voice, "preview_ready": ready and bool(shutil.which("say")), "voice": voice,
            "label": "Launch film · 1080p · measured narration · captions"}


def run(args: list[str], timeout=120) -> str:
    env = os.environ.copy()
    if Path(args[0]).name in {"ffmpeg", "ffprobe"} and "@remotion" in args[0]:
        env["DYLD_LIBRARY_PATH" if platform.system() == "Darwin" else "LD_LIBRARY_PATH"] = str(Path(args[0]).parent)
    try:
        proc = subprocess.run(args, cwd=REMOTION_DIR, capture_output=True, text=True, timeout=timeout, env=env)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("Video production timed out. Completed content is saved; retry this campaign.") from exc
    if proc.returncode:
        # Subprocesses may include provider details or local paths; do not echo raw stderr into the UI.
        raise RuntimeError(f"Video production failed during {Path(args[0]).name}. Check the renderer installation and retry.")
    return proc.stdout


def probe(path: Path) -> dict:
    return json.loads(run([binary("ffprobe"), "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)]))


def speak(text: str, path: Path, *, preview=False, profile=None, transcript: str | None = None) -> None:
    profile = profile or VOICE_PROFILE
    voice_id = profile["voice_id"] if profile.get("explicit_voice") else narrator_id() if profile.get("name") == VOICE_PROFILE["name"] else profile["voice_id"]
    voice_config = voice_settings()
    transcript = transcript or text
    if profile.get("pauses"):
        from app.services.marketing_performance import directed_transcript
        transcript = directed_transcript(text, profile["pauses"])
    if not preview and voice_config.cartesia_api_key and voice_id:
        from app.clients.http import post
        for attempt in range(2):
            try:
                response = post("https://api.cartesia.ai/tts/sse", headers={
                    "Cartesia-Version": "2026-08-14", "Authorization": f"Bearer {voice_config.cartesia_api_key}"},
                    json={"model_id": voice_config.cartesia_model, "transcript": transcript,
                          "voice": voice_id, "language": profile.get("language", "en"), "add_timestamps": True,
                          **({"pronunciation_dict_id": pronunciation_dict_id(text)} if pronunciation_dict_id(text) else {}), "use_normalized_timestamps": False,
                          "generation_config": tts_generation_config(profile),
                          "output_format": {"container": "raw", "encoding": "pcm_s16le", "sample_rate": 44100}}, timeout=90)
                response.raise_for_status()
                save_sse_take(response.text, text, path)
                return
            except Exception:
                if attempt:
                    raise RuntimeError("Narration provider failed. Check the Cartesia connection and retry.")
                time.sleep(2)
    else:
        if not preview:
            raise RuntimeError("A production narration voice is required. System voice is available for explicit local previews only.")
        say = shutil.which("say")
        if not say:
            raise RuntimeError("Configure a Cartesia voice or use a Mac with a system voice to render narration.")
        script = path.with_suffix(".txt")
        script.write_text(text, encoding="utf-8")
        run([say, "-v", profile["preview_voice"], "-r", str(profile["preview_wpm"]), "-f", str(script), "--file-format=WAVE", "--data-format=LEI16@44100", "-o", str(path)])


def scene_profile(scene: dict) -> dict:
    return VOICE_PROFILES.get(scene.get("voice") or "narrator", VOICE_PROFILE)


def assemble_film_audio(video: dict, public: Path, *, preview=False) -> tuple[Path, list[dict], float]:
    """Use the same scene-level delivery and readable holds for every film topic."""
    from app.services.marketing_performance import assemble_directed_audio
    return assemble_directed_audio(video, public, preview=preview)


def product_label() -> str:
    from app.services.profile import load_profile

    profile = load_profile()
    return profile.get("product_name") or profile.get("workspace") or "Product"


def module_label() -> str:
    """Short module name (the first product module) for tight on-screen labels; the full product name otherwise."""
    from app.services.profile import product_modules

    modules = product_modules()
    return modules[0] if modules else product_label()


def _header_label() -> str:
    from app.services.profile import load_profile

    company = str(load_profile().get("company_name") or "").strip()
    module = module_label()
    return f"{company} / {module}" if company and company.lower() != module.lower() else product_label()


def stage_brand(public: Path) -> None:
    """Films read `brand-logo-dark.svg`, `brand-logo-light.svg` and `brand-mark.svg`; SVG only, so
    raster uploads are wrapped rather than renamed."""
    from app.services.brand import brand_asset, mark_svg, wordmark_svg

    def svg_for(stem: str, fallback: str) -> str:
        path = brand_asset(stem)
        if path is None:
            return fallback
        if path.suffix.lower() == ".svg":
            return path.read_text()
        media = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
        data = base64.b64encode(path.read_bytes()).decode("ascii")
        return f'<svg xmlns="http://www.w3.org/2000/svg" width="320" height="80" viewBox="0 0 320 80"><image href="data:{media};base64,{data}" width="320" height="80" preserveAspectRatio="xMidYMid meet"/></svg>'

    (public / "brand-logo-dark.svg").write_text(svg_for("logo-dark", wordmark_svg(dark=True)))
    (public / "brand-logo-light.svg").write_text(svg_for("logo-light", wordmark_svg(dark=False)))
    (public / "brand-mark.svg").write_text(svg_for("mark", mark_svg()))


def copy_film_plates(public: Path) -> None:
    """Photographic plates live in the world layer; missing files skip rather than inventing pixels."""
    folder = ROOT / "backend/app/static/artifacts/references/video"
    for name in ("conversation.jpg", "signal-flow.jpg", "source-stack.jpg"):
        source = folder / name
        if source.is_file():
            shutil.copyfile(source, public / name)


def bind_scene(scene: dict, seconds: float, start: int) -> dict:
    if not math.isfinite(seconds) or seconds < 0.3 or seconds > 7.5:
        raise ValueError("Narration timing is invalid; regenerate the voice take.")
    # A 0.1s edit grid avoids accumulated dead air. Preserve the entire take and
    # a short reading hold; the CTA gets a slightly longer closing beat.
    tail = 12 if scene.get("kind") == "cta" else 6
    frames = max(66, math.ceil((seconds * 30 + AUDIO_LEAD_FRAMES + tail) / 3) * 3)
    words = scene["narration"].split()
    if not words:
        raise ValueError("Every shot needs narration before timings can be bound.")
    captions = []
    for offset in range(0, len(words), 4):
        stop = min(offset + 4, len(words))
        captions.append({"text": " ".join(words[offset:stop]),
                         "from": AUDIO_LEAD_FRAMES + round(seconds * 30 * offset / len(words)),
                         "to": AUDIO_LEAD_FRAMES + round(seconds * 30 * stop / len(words))})
    count = len(scene.get("labels", []))
    label_frames = [8 + round(min(seconds * 30 * 0.55, frames - 42) * i / max(1, count - 1)) for i in range(count)]
    return {**scene, "from": start, "frames": frames, "captions": captions, "audioFrom": AUDIO_LEAD_FRAMES,
            "audioFrames": round(seconds * 30), "labelFrames": label_frames}


def validate_master(info: dict, aspect: str, seconds: float):
    streams = info.get("streams", [])
    picture = next((s for s in streams if s.get("codec_type") == "video"), {})
    width, height = (1080, 1920) if aspect == "portrait" else (1920, 1080)
    if picture.get("width") != width or picture.get("height") != height or not any(s.get("codec_type") == "audio" for s in streams):
        raise ValueError("The film failed resolution/audio quality checks.")
    if picture.get("codec_name") != "h264" or picture.get("pix_fmt") != "yuv420p":
        raise ValueError("The film must use H.264 with a platform-compatible pixel format.")
    try:
        numerator, denominator = picture.get("r_frame_rate", "0/1").split("/")
        fps = float(numerator) / float(denominator)
    except (ValueError, ZeroDivisionError):
        fps = 0
    if abs(fps - 30) > 0.01:
        raise ValueError("The film failed its 30fps frame-rate check.")
    if abs(float(info["format"]["duration"]) - seconds) > 0.5:
        raise ValueError("The film failed its duration check.")


def measure_audio(path: Path) -> dict:
    """Measure the encoded master, not just its requested normalization target."""
    command = binary("ffmpeg")
    env = os.environ.copy()
    env["DYLD_LIBRARY_PATH" if platform.system() == "Darwin" else "LD_LIBRARY_PATH"] = str(Path(command).parent)
    result = subprocess.run([command, "-i", str(path), "-vn", "-af", "loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json",
                             "-f", "null", "-"], capture_output=True, text=True, env=env, timeout=120)
    matches = re.findall(r'\{\s*"input_i".*?\}', result.stderr, re.S)
    if result.returncode or not matches:
        raise ValueError("Could not measure the film's encoded audio.")
    raw = json.loads(matches[-1])
    loudness, peak = float(raw["input_i"]), float(raw["input_tp"])
    if not math.isfinite(loudness) or not -18 <= loudness <= -14 or not math.isfinite(peak) or peak > -1:
        raise ValueError("The film failed its measured loudness/peak check.")
    return {"integrated_lufs": loudness, "true_peak_dbtp": peak}


def srt_time(frame: int) -> str:
    ms = round(frame * 1000 / 30)
    return f"{ms // 3600000:02}:{ms // 60000 % 60:02}:{ms // 1000 % 60:02},{ms % 1000:03}"


def encode_master(raw: Path, target: Path, seconds: float, narration: Path | None = None, music: Path | None = None, music_gain: float = 0.4, sfx: Path | None = None, duck_floor: float = 0.22):
    command = [binary("ffmpeg"), "-y", "-i", str(raw)]
    padded = mixed = None
    if narration is not None:
        # Do not decode and encode Remotion's AAC again: its priming can shift
        # narration relative to word timestamps. Encode the original PCM once.
        padded = target.with_suffix(".narration.wav")
        pad_narration(narration, padded, AUDIO_LEAD_FRAMES / 30, seconds)
        audio = padded
        if music is not None or sfx is not None:
            from app.services.marketing_score import mix_under_voice
            mixed = target.with_suffix(".mix.wav")
            mix_under_voice(padded, music, mixed, music_gain=music_gain, duck_floor=duck_floor, sfx=sfx)
            audio = mixed
        command += ["-i", str(audio), "-map", "0:v:0", "-map", "1:a:0"]
    try:
        # Single-pass loudnorm overshoots its TP target by ~0.5 dB on percussive scores; aim below the -1 dBTP gate.
        run(command + ["-c:v", "copy", "-af", "loudnorm=I=-16:TP=-2:LRA=11",
                       "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(target)], timeout=180)
    finally:
        for extra in (padded, mixed):
            if extra is not None:
                extra.unlink(missing_ok=True)


def render_campaign_video(video: dict, folder: Path, set_step=lambda *a: None, *, aspects=("landscape", "portrait"), preview=False, max_seconds=90) -> list[dict]:
    with _RENDER_LOCK:
        if not video_status()["preview_ready" if preview else "ready"]:
            raise RuntimeError("Video renderer or narration is unavailable. Run npm install in render/remotion and configure a voice.")
        if not aspects or any(a not in {"landscape", "portrait"} for a in aspects):
            raise ValueError("Unsupported video aspect ratio.")
        if not preview:
            for scene in video["scenes"]:
                cue_indices(scene, [{"word": word} for word in scene["narration"].split()])
        public = folder / "media"
        public.mkdir(parents=True, exist_ok=True)
        stage_brand(public)
        shutil.copyfile(ROOT / "backend" / "app" / "fonts" / "Inter-Regular.ttf", public / "Inter.ttf")
        shutil.copyfile(ROOT / "backend/app/fonts/Inter-Medium.ttf", public / "Inter-Medium.ttf")
        copy_film_plates(public)
        scenes = []
        cursor = 0
        subtitles = []
        narration_audio = None
        launch = video.get("filmKind") == "launch"
        if not preview:
            wav, word_times, seconds = assemble_film_audio(video, public)
            # The launch close holds the lockup after the last word instead of cutting on it.
            scenes, cursor = bind_narrated_film(video["scenes"], word_times, seconds, audio_lead=AUDIO_LEAD_FRAMES, tail_frames=54 if launch else 12)
            if launch:
                bind_launch_cues(scenes, audio_lead=AUDIO_LEAD_FRAMES)
            narration_audio = wav.name
            set_step("narration", {"status": "running", "count": len(scenes), "total": len(scenes)})
        else:
            for index, scene in enumerate(video["scenes"]):
                profile = scene_profile(scene)
                take_key = voice_take_key(scene["narration"], preview=preview, profile=profile)
                wav = public / f"voice-{index}-{take_key}.wav"
                if not wav.is_file():
                    speak(scene["narration"], wav, preview=preview, profile=profile)
                try:
                    seconds = float(probe(wav)["format"]["duration"])
                    timed = bind_scene(scene, seconds, cursor)
                except (ValueError, RuntimeError, KeyError):
                    # Interrupted/corrupt takes must not poison every retry.
                    speak(scene["narration"], wav, preview=preview, profile=profile)
                    seconds = float(probe(wav)["format"]["duration"])
                    timed = bind_scene(scene, seconds, cursor)
                timed["audio"] = wav.name
                scenes.append(timed)
                cursor += timed["frames"]
                set_step("narration", {"status": "running", "count": index + 1, "total": len(video["scenes"])})
        for scene in scenes:
            for caption in scene["captions"]:
                subtitles.append(f"{len(subtitles) + 1}\n{srt_time(scene['from'] + caption['from'])} --> {srt_time(scene['from'] + caption['to'])}\n{caption['text']}\n")
        if not 24 <= cursor / 30 <= max_seconds:
            raise ValueError(f"Film timing is {cursor / 30:.1f}s, outside the 24–{max_seconds}s limit. Tighten narration and remove repeated ideas.")
        craft = launch_craft(scenes, launch_theme(video), video.get("title") or "") if launch else craft_for_scenes(scenes)
        props = {"title": video.get("title") or product_label(), "product": product_label(), "module": module_label(), "filmKind": video.get("filmKind"), "scenes": scenes, "durationInFrames": cursor, "portrait": False, "preview": preview, "audio": narration_audio, "audioFrom": AUDIO_LEAD_FRAMES, "craft": craft}
        (folder / "render-props.json").write_text(json.dumps(props), encoding="utf-8")
        (folder / "captions.srt").write_text("\n".join(subtitles), encoding="utf-8")
        measurements = {}
        for aspect in aspects:
            set_step("video", {"status": "running", "format": aspect})
            final = folder / f"{aspect}.mp4"
            if final.is_file():
                try:
                    validate_master(probe(final), aspect, cursor / 30)
                    measurements[aspect] = measure_audio(final)
                    if (folder / f"{aspect}-thumbnail.png").is_file():
                        continue
                except (ValueError, RuntimeError):
                    # Preserve the old file until a newly validated master replaces it.
                    pass
            # Node renders to a temporary name; only validated outputs get the final name.
            run([shutil.which("node"), str(REMOTION_DIR / "scripts" / "render-marketing.mjs"), str(folder), aspect], timeout=1200)
            raw = folder / f"{aspect}-raw.mp4"
            temporary = folder / f"{aspect}-master.mp4"
            music = sfx = None
            score_kind = video.get("score")
            if not score_kind and video.get("filmKind") == "pii-storyboard":
                from app.services.marketing_score import SCORE as PRIVACY_SCORE
                score_kind = PRIVACY_SCORE["version"]
            if not score_kind and launch:
                from app.services.marketing_score import LAUNCH as LAUNCH_SCORE
                score_kind = LAUNCH_SCORE["version"]
            if score_kind and narration_audio:
                from app.services.marketing_score import write_score
                music = public / f"score-{score_kind}-{cursor}.wav"
                if not music.is_file():
                    write_score(score_kind, music, cursor / 30)
            if launch and narration_audio:
                from app.services.marketing_score import SFX, launch_sfx_cues, write_sfx
                cues = launch_sfx_cues(scenes, craft)
                sfx = public / f"sfx-{hashlib.sha256(json.dumps([SFX, cues, cursor]).encode()).hexdigest()[:12]}.wav"
                if not sfx.is_file():
                    write_sfx(cues, sfx, cursor / 30)
            # Launch beds sit about 11 dB under the voice and swell between lines; deeper ducking buried the score.
            encode_master(raw, temporary, cursor / 30, public / narration_audio if narration_audio else None, music,
                          music_gain=0.7 if launch else 0.5 if score_kind and "launch" in str(score_kind) else 0.4, sfx=sfx,
                          duck_floor=0.5 if launch else 0.22)
            info = probe(temporary)
            validate_master(info, aspect, cursor / 30)
            craft = evaluate_encoded_film(temporary, aspect, binary("ffmpeg"), binary("ffprobe"))
            measurements[aspect] = {**measure_audio(temporary), "craft": {"passed": craft["passed"], "video_bitrate": craft["bitrate"]["video_bitrate"], "freeze_seconds": craft["motion"]["freeze_seconds"]}}
            temporary.replace(final)
        pii_launch = video.get("filmKind") == "pii-launch"
        storyboard = video.get("filmKind") == "pii-storyboard"
        scored = bool(video.get("score") or storyboard or launch)
        qc = {"technical_checks_passed": True, "production_ready": False, "mode": "preview" if preview else "production",
              "width": 1920, "height": 1080, "portrait": "1080x1920", "fps": 30,
              "duration_seconds": cursor / 30, "narration": "Mac system voice (preview)" if preview else video_status()["voice"], "audio": measurements,
              "voice_delivery": VOICE_PROFILE,
              "pacing": {"shot_seconds": [s["frames"] / 30 for s in scenes], "average_shot_seconds": cursor / 30 / len(scenes)},
              "caption_timing": "Estimated (local system preview)" if preview else "Provider word timestamps; one continuous narration track",
              "visual_style": ("Launch grammar: moving gradient fields, narration-timed kinetic type, persistent illustrative call with live transcript, illustrative product-screen recreations with cursor actions, UI sound design" if launch else "PII launch: two-party call desk, live transcript, detect/collect, spread, flow, mask and split" if pii_launch else "User-supplied PII storyboard: brand palette, kinetic type, labelled illustrative masking demos and supplied photo panels" if storyboard else "Launch film: conversations, source stacks, signal flows and kinetic type; no simulated product screenshots"),
              "remaining_review": ("Human playback and creative approval; original ducked score and synthesized UI effects under continuous narration passages" if launch else "Human playback and creative approval; original ducked score under narration" if scored and not storyboard else "Human playback and creative approval; illustrative 1 kHz masking beep under an original ducked score" if storyboard else "Automated visual review and human playback; no music or sound-design pass is claimed."),
              "scene_count": len(scenes), "aspects": list(aspects),
              "checks": (["complete word alignment", "continuous audio timeline", "narration cue order"] if not preview else []) + ["measured voice duration", "settled-shot text bounds and overlap", "audio track", "resolution", "output duration", "30fps H.264/yuv420p", "encoded loudness and true peak", "saturation/gradient/freeze/bitrate craft gates"] + (["original ducked score under narration"] if scored else [])}
        (folder / "quality.json").write_text(json.dumps(qc, indent=2), encoding="utf-8")
        outputs = [(f"{aspect}.mp4", "video/mp4") for aspect in aspects]
        outputs += [(f"{aspect}-thumbnail.png", "image/png") for aspect in aspects]
        outputs += [("captions.srt", "application/x-subrip"), ("quality.json", "application/json")]
        return [{"filename": name, "channel": "video", "mime": mime} for name, mime in outputs]



def document_html(title: str, markdown: str) -> str:
    """Print-ready, escaped HTML. Model HTML/scripts and external resources never execute."""
    blocks = []
    for paragraph in re.split(r"\n\s*\n", markdown):
        escaped = html.escape(paragraph)
        escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
        if escaped.startswith("#"):
            blocks.append(f"<h2>{escaped.lstrip('# ').strip()}</h2>")
        else:
            blocks.append("<p>" + escaped.replace("\n", "<br>") + "</p>")
    return '<!doctype html><html lang="en"><meta charset="utf-8"><title>' + html.escape(title) + '''</title>
<style>body{font:17px/1.65 Inter,Arial,sans-serif;color:#151515;max-width:820px;margin:64px auto;padding:32px}
header{color:#1a62f2;font-weight:700;letter-spacing:2px}h1{font:700 46px/1.1 Helvetica,Arial,sans-serif;letter-spacing:-1px}h2{font-size:25px;break-after:avoid}p{orphans:3;widows:3}@media print{body{margin:0;max-width:none;padding:0;font-size:11pt}@page{size:A4;margin:20mm}}</style>
<header>''' + html.escape(_header_label().upper()) + '</header><h1>' + html.escape(title) + "</h1>" + "".join(blocks) + "</html>"
