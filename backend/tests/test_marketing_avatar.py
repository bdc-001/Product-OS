import array
import io
import math
import wave

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.routers.avatar_videos import router
from app.clients import elevenlabs
from app.clients.heygen import HeyGenError
from app.database import Base
from app.models import AvatarVideo
from app.services import marketing_avatar as av


def photo(width=600, height=800, bars=0, mark=False, color=(180, 140, 120)) -> bytes:
    image = Image.new("RGB", (width, height), color)
    if bars:
        black = Image.new("RGB", (width, bars), (0, 0, 0))
        image.paste(black, (0, 0))
        image.paste(black, (0, height - bars))
        if mark:
            image.paste(Image.new("RGB", (12, 12), (255, 255, 255)), (width - 30, height - 40))
    out = io.BytesIO()
    image.save(out, "JPEG")
    return out.getvalue()


class FakeHeyGen:
    configured = True
    api_key = "test-key"

    def __init__(self, failures=None):
        self.failures = list(failures or [])
        self.store: dict[str, dict] = {}
        self.creates: list[dict] = []

    def upload_asset(self, filename, content, mime, *, idempotency_key):
        return {"asset_id": f"ast_{len(self.store)}_{len(content)}"}

    def looks(self, *, ownership=None, group_id=None, limit=50, **_):
        return {"data": [item for item in self.store.values() if not group_id or item["group_id"] == group_id]}

    def create_photo_avatar(self, name, asset_id, *, group_id=None, idempotency_key):
        self.creates.append({"name": name, "group_id": group_id, "key": idempotency_key})
        look_id = f"look{len(self.creates)}"
        item = {"id": look_id, "name": name, "group_id": group_id or look_id, "status": "processing", "avatar_type": "photo_avatar"}
        failure = self.failures.pop(0) if self.failures else None
        if failure == "billed":
            self.store[look_id] = item
            raise HeyGenError("Photo avatar creation conflicted with an existing operation.", 409, "conflict")
        if failure == "asset":
            raise HeyGenError(f"Asset {asset_id} not found", 404, "not_found")
        if failure == "moderation":
            raise HeyGenError("The photo did not pass moderation.", 400, "moderation_failed")
        self.store[look_id] = item
        return {"avatar_item": item, "avatar_group": {"id": item["group_id"]}}


class FakeEleven:
    configured = True

    def __init__(self):
        self.speeches: list[dict] = []
        self.clones: list[dict] = []

    def speech(self, voice_id, text, *, model_id, voice_settings, output_format="mp3_44100_128"):
        self.speeches.append({"voice_id": voice_id, "text": text, "model_id": model_id, "settings": voice_settings})
        return b"\xff\xfb" * 16000

    def clone_voice(self, name, samples, *, remove_background_noise=False, description="", labels=None):
        self.clones.append({"name": name, "samples": samples, "denoise": remove_background_noise})
        return {"voice_id": "el123", "requires_verification": False}


class FakeCartesia:
    configured = True

    def __init__(self, accent_failure=False):
        self.accent_failure = accent_failure
        self.speeches: list[dict] = []
        self.clones: list[dict] = []
        self.accents: list[tuple] = []

    def speech(self, voice_id, transcript, *, model_id, locale, accent="", speed=1.0, pronunciation_dict_id=""):
        self.speeches.append({"voice_id": voice_id, "text": transcript, "model_id": model_id, "locale": locale,
                              "accent": accent, "speed": speed, "dictionary": pronunciation_dict_id})
        return b"\xff\xfb" * 16000

    def clone_voice(self, name, clip, *, language, accent="", description=""):
        self.clones.append({"name": name, "clip": clip, "language": language, "accent": accent})
        return {"id": "ca-77"}

    def add_accents(self, voice_id, accents):
        if self.accent_failure:
            raise av.CartesiaError("Accent localisation is not enabled for this plan.", 403)
        self.accents.append((voice_id, accents))
        return {"id": voice_id}


def tone_wav(seconds=9.0, rate=16000, parts=((40, 0.4), (300, 0.4))) -> bytes:
    samples = array.array("h", (int(32767 * sum(level * math.sin(2 * math.pi * freq * i / rate) for freq, level in parts))
                                for i in range(int(seconds * rate))))
    out = io.BytesIO()
    with wave.open(out, "wb") as clip:
        clip.setnchannels(1)
        clip.setsampwidth(2)
        clip.setframerate(rate)
        clip.writeframes(samples.tobytes())
    return out.getvalue()


def level(samples, rate, freq) -> float:
    tail = samples[-rate:]
    re_part = sum(s * math.cos(2 * math.pi * freq * i / rate) for i, s in enumerate(tail))
    im_part = sum(s * math.sin(2 * math.pi * freq * i / rate) for i, s in enumerate(tail))
    return math.hypot(re_part, im_part) / len(tail)


class Recorder(FakeHeyGen):
    def __init__(self, failures=None):
        super().__init__(failures)
        self.uploads: list[dict] = []
        self.videos: list[dict] = []

    def upload_asset(self, filename, content, mime, *, idempotency_key):
        self.uploads.append({"filename": filename, "mime": mime, "size": len(content), "key": idempotency_key})
        return {"asset_id": f"aud{len(self.uploads)}"}

    def create_video(self, body, *, idempotency_key):
        self.videos.append({"body": body, "key": idempotency_key})
        failure = self.failures.pop(0) if self.failures else None
        if failure == "asset":
            raise HeyGenError(f"Asset {body.get('audio_asset_id')} not found", 404, "not_found")
        return {"video_id": f"vid{len(self.videos)}", "status": "waiting"}


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(av, "SOURCES_DIR", tmp_path / "sources")
    monkeypatch.setattr(av, "AVATAR_DIR", tmp_path / "avatar")
    monkeypatch.setattr(av, "PHOTO_RETRY_SECONDS", 0)
    monkeypatch.setattr(av.settings, "elevenlabs_voice_id", "")
    monkeypatch.setattr(av.settings, "avatar_cartesia_voice_id", "")
    monkeypatch.setattr(av.settings, "avatar_cartesia_locale", "en-IN")
    monkeypatch.setattr(av.settings, "avatar_cartesia_accent", "")
    monkeypatch.setattr(av, "_pronunciation_dictionary", lambda script: "")
    av._catalog_cache.clear()


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as session:
        yield session


def test_prepare_photo_trims_letterbox_bars_even_with_a_corner_mark():
    trimmed = Image.open(io.BytesIO(av.prepare_photo(photo(400, 900, bars=150, mark=True))))
    assert trimmed.size == (400, 600)
    assert Image.open(io.BytesIO(av.prepare_photo(photo(600, 800)))).size == (600, 800)


def test_prepare_photo_rejects_unreadable_and_tiny_files():
    with pytest.raises(ValueError, match="readable photo"):
        av.prepare_photo(b"not an image")
    with pytest.raises(ValueError, match="shorter side"):
        av.prepare_photo(photo(200, 300))


def test_photos_become_looks_on_one_character():
    client = FakeHeyGen()
    out = av.create_photo_avatar("Presenter", [("a.jpg", photo()), ("b.jpg", photo(color=(90, 90, 200))), ("c.jpg", photo(color=(20, 160, 60)))],
                                 look_names=["Office", "Studio", "Seated"], client=client)
    assert [c["name"] for c in client.creates] == ["Presenter", "Studio", "Seated"]
    assert [c["group_id"] for c in client.creates] == [None, "look1", "look1"]
    assert len({c["key"] for c in client.creates}) == 3
    assert out["group_id"] == "look1"
    assert [look["ready"] for look in out["looks"]] == [False, False, False]
    assert sorted(p.name for p in (av.SOURCES_DIR / "look1").iterdir()) == ["look1.jpg", "look2.jpg", "look3.jpg"]


def test_failed_response_adopts_the_billed_look_instead_of_creating_a_duplicate():
    client = FakeHeyGen(failures=[None, "billed"])
    out = av.create_photo_avatar("Presenter", [("a.jpg", photo()), ("b.jpg", photo(color=(90, 90, 200)))],
                                 look_names=["", "Studio"], client=client)
    assert len(client.creates) == 2
    assert len(client.store) == 2
    assert out["looks"][1]["id"] == "look2"


def test_fresh_asset_not_found_is_retried_with_a_new_key():
    client = FakeHeyGen(failures=["asset"])
    out = av.create_photo_avatar("Presenter", [("a.jpg", photo())], client=client)
    assert len(client.creates) == 2
    assert client.creates[0]["key"] != client.creates[1]["key"]
    assert len(client.store) == 1
    assert out["looks"][0]["name"] == "Presenter"


def test_moderation_failure_is_not_retried():
    client = FakeHeyGen(failures=["moderation"])
    with pytest.raises(HeyGenError, match="moderation"):
        av.create_photo_avatar("Presenter", [("a.jpg", photo())], client=client)
    assert len(client.creates) == 1


def test_create_avatar_endpoint_accepts_multipart_photos(monkeypatch):
    client = FakeHeyGen()
    monkeypatch.setattr(av, "HeyGenClient", lambda: client)
    app = FastAPI()
    app.include_router(router, prefix="/api")
    with TestClient(app) as http:
        response = http.post("/api/avatar-videos/avatars", data={"name": "Presenter", "look_names": ["", "Studio"]},
                             files=[("photos", ("a.jpg", photo(), "image/jpeg")), ("photos", ("b.jpg", photo(color=(90, 90, 200)), "image/jpeg"))])
        assert response.status_code == 201, response.text
        assert [look["name"] for look in response.json()["looks"]] == ["Presenter", "Studio"]
        bad = http.post("/api/avatar-videos/avatars", data={"name": "Presenter"}, files=[("photos", ("x.jpg", b"nope", "image/jpeg"))])
        assert bad.status_code == 400
        assert http.get("/api/avatar-videos/avatars/looks/bad id").status_code == 422


def test_render_request_maps_options_for_heygen():
    row = AvatarVideo(id=7, title="", script="  Hello there team.  ", avatar_id="look1", voice_id="v1",
                      options={"aspect_ratio": "9:16", "resolution": "720p", "engine": "avatar_v", "speed": 1.2, "background": "#0A2540"})
    body = av.build_request(row)
    assert body["avatar_id"] == "look1" and body["script"] == "Hello there team."
    assert body["aspect_ratio"] == "9:16" and body["resolution"] == "720p"
    assert body["engine"] == {"type": "avatar_v"}
    assert body["voice_settings"] == {"speed": 1.2}
    assert body["background"] == {"type": "color", "value": "#0A2540"}
    assert body["title"] == "Avatar video 7"
    assert "expressiveness" not in body and "motion_prompt" not in body


def test_photo_avatars_get_expression_and_motion_on_avatar_iv_only():
    row = AvatarVideo(id=12, script="Hello there team.", avatar_id="look1", avatar_type="photo_avatar", options={})
    body = av.build_request(row)
    assert body["expressiveness"] == "medium" and body["motion_prompt"] == av.PRESENTER_MOTION

    row.options = {"expressiveness": "wild", "motion_prompt": "  nods\n slowly  "}
    body = av.build_request(row)
    assert body["expressiveness"] == "medium" and body["motion_prompt"] == "nods slowly"

    row.options = {"expressiveness": "high", "motion_prompt": ""}
    body = av.build_request(row)
    assert body["expressiveness"] == "high" and "motion_prompt" not in body

    row.options = {"engine": "avatar_v"}
    assert "expressiveness" not in av.build_request(row) and "motion_prompt" not in av.build_request(row)
    twin = AvatarVideo(id=13, script="Hello there team.", avatar_id="look2", avatar_type="digital_twin", options={})
    assert "expressiveness" not in av.build_request(twin)


def test_drafts_without_a_voice_use_the_pipeline_voice(monkeypatch):
    monkeypatch.setattr(av.settings, "heygen_voice_id", "clone1")
    monkeypatch.setattr(av.settings, "heygen_voice_name", "Presenter (cloned)")
    row = AvatarVideo(id=8, script="Hello there team.", avatar_id="look1", options={})
    av.apply_fields(row, {"voice_id": "", "voice_name": ""})
    assert (row.voice_id, row.voice_name) == ("clone1", "Presenter (cloned)")
    assert av.build_request(row)["voice_id"] == "clone1"

    av.apply_fields(row, {"voice_id": "stock7", "voice_name": "Stock"})
    assert av.build_request(row)["voice_id"] == "stock7"

    monkeypatch.setattr(av.settings, "heygen_voice_id", "")
    blank = AvatarVideo(id=9, script="Hello there team.", avatar_id="look1", options={})
    av.apply_fields(blank, {})
    assert "voice_id" not in av.build_request(blank)


def test_pauses_mark_sentence_and_paragraph_ends_only():
    paced = av.pace_script('Leads go cold. Voice helps, e.g. by calling. He said "Go." Done!\n\nNext part? Yes.')
    assert paced == ('Leads go cold. <break time="0.5s"/> Voice helps, e.g. by calling. <break time="0.5s"/> '
                     'He said "Go." <break time="0.5s"/> Done! <break time="1s"/> Next part? <break time="0.5s"/> Yes.')
    own = 'Hold on. <break time="1.5s"/> Okay. Go.'
    assert av.pace_script(own) == own


def test_cloned_elevenlabs_voice_is_pinned_to_multilingual_v2_with_a_paced_script():
    row = AvatarVideo(id=10, script="Leads go cold. Voice calls them.", avatar_id="look1", voice_id="clone1", options={})
    body = av.build_request(row, voice_engine="elevenlabs")
    assert body["script"] == 'Leads go cold. <break time="0.5s"/> Voice calls them.'
    assert body["voice_settings"] == {"engine_settings": {"engine_type": "elevenlabs", "model": "eleven_multilingual_v2"}}

    row.options = {"pauses": False}
    plain = av.build_request(row)
    assert plain["script"] == "Leads go cold. Voice calls them." and "voice_settings" not in plain


def test_voice_engine_reads_the_private_elevenlabs_list():
    class Voices(FakeHeyGen):
        def voices(self, **kwargs):
            assert kwargs["engine"] == "elevenlabs"
            return {"data": [{"voice_id": "clone1"}]}

    client = Voices()
    assert av.voice_engine("clone1", client) == "elevenlabs"
    assert av.voice_engine("stock7", client) == ""


def eleven_draft(db, script="Leads go cold. Voice calls them back.", **options) -> AvatarVideo:
    row = AvatarVideo(status="draft", result={}, assets=[], options={"aspect_ratio": "auto", **options})
    av.apply_fields(row, {"script": script, "avatar_id": "seated1", "voice_id": "", "voice_name": ""})
    db.add(row)
    db.commit()
    return row


def test_elevenlabs_default_voice_narrates_once_then_heygen_lipsyncs_the_audio(db, monkeypatch):
    monkeypatch.setattr(av.settings, "elevenlabs_voice_id", "el123")
    monkeypatch.setattr(av.settings, "elevenlabs_voice_name", "Presenter (ElevenLabs)")
    eleven = FakeEleven()
    monkeypatch.setattr(av, "ElevenLabsClient", lambda: eleven)
    row = eleven_draft(db, speed=1.4)
    assert (row.voice_id, row.voice_name) == ("elevenlabs:el123", "Presenter (ElevenLabs)")

    preview = av.narrate(db, row)
    assert preview["stale"] is False and preview["url"].endswith("/narration.mp3")
    assert eleven.speeches[0]["voice_id"] == "el123"
    assert eleven.speeches[0]["text"] == 'Leads go cold. <break time="0.5s"/> Voice calls them back.'
    assert eleven.speeches[0]["settings"]["speed"] == 1.2

    heygen = Recorder()
    av.submit(db, row, client=heygen)
    assert len(eleven.speeches) == 1
    assert heygen.uploads[0]["mime"] == "audio/mpeg" and heygen.uploads[0]["key"].startswith("pmos-audio-")
    body = heygen.videos[0]["body"]
    assert body["audio_asset_id"] == "aud1" and body["aspect_ratio"] == "auto"
    assert not {"script", "voice_id", "voice_settings"} & body.keys()
    assert row.status == "submitted" and row.result["narration"]["voice_id"] == "el123"
    assert av.video_out(row)["narration"]["seconds"] == 2.0


def test_narration_goes_stale_when_the_script_changes(db, monkeypatch):
    monkeypatch.setattr(av.settings, "elevenlabs_voice_id", "el123")
    eleven = FakeEleven()
    monkeypatch.setattr(av, "ElevenLabsClient", lambda: eleven)
    row = eleven_draft(db)
    av.narrate(db, row)
    av.apply_fields(row, {"script": "Leads go cold. Voice calls them within a minute."})
    assert av.narration_info(row)["stale"] is True
    av.narrate(db, row)
    assert len(eleven.speeches) == 2 and av.narration_info(row)["stale"] is False


def test_fresh_narration_asset_not_found_is_retried_once(db, monkeypatch):
    monkeypatch.setattr(av.settings, "elevenlabs_voice_id", "el123")
    monkeypatch.setattr(av, "ElevenLabsClient", FakeEleven)
    heygen = Recorder(failures=["asset"])
    row = eleven_draft(db)
    av.submit(db, row, client=heygen)
    assert len(heygen.videos) == 2 and heygen.videos[0]["key"] != heygen.videos[1]["key"]
    assert row.heygen_video_id == "vid2"


def test_heygen_voices_skip_narration(db):
    row = AvatarVideo(id=11, script="Hello there team.", avatar_id="look1", voice_id="stock7", options={})
    with pytest.raises(ValueError, match="HeyGen voice"):
        av.narrate(db, row)


def test_clone_checks_formats_and_can_become_the_default(monkeypatch):
    eleven = FakeEleven()
    with pytest.raises(ValueError, match="not a supported audio"):
        av.clone_elevenlabs_voice("Presenter", [("notes.txt", b"hi")], client=eleven)
    saved = {}
    import app.services.workspace as workspace

    monkeypatch.setattr(workspace, "save_connection_settings", lambda provider, values: saved.update({provider: values}))
    out = av.clone_elevenlabs_voice("  Acme   Presenter ", [("/tmp/AUDIO.m4a", b"\x00" * 64)], make_default=True, client=eleven)
    assert eleven.clones[0]["samples"] == [("AUDIO.m4a", b"\x00" * 64, "audio/mp4")]
    assert out == {"voice_id": "el123", "id": "elevenlabs:el123", "name": "Acme Presenter",
                   "requires_verification": False, "default": True}
    assert saved == {"elevenlabs": {"voice_id": "el123", "voice_name": "Acme Presenter"}}


def test_cartesia_voice_wins_and_narrates_with_sonic_in_indian_english(db, monkeypatch):
    monkeypatch.setattr(av.settings, "avatar_cartesia_voice_id", "ca-77")
    monkeypatch.setattr(av.settings, "avatar_cartesia_voice_name", "Presenter (Cartesia)")
    monkeypatch.setattr(av.settings, "elevenlabs_voice_id", "el123")
    monkeypatch.setattr(av, "_pronunciation_dictionary", lambda script: "dict-acme" if "Acme" in script else "")
    cartesia = FakeCartesia()
    monkeypatch.setattr(av, "CartesiaClient", lambda: cartesia)
    row = eleven_draft(db, script="Leads go cold at Acme. Voice & you <win>.\n\nNext step.", speed=1.4)
    assert (row.voice_id, row.voice_name) == ("cartesia:ca-77", "Presenter (Cartesia)")

    av.narrate(db, row)
    spoken = cartesia.speeches[0]
    assert spoken["text"] == ('Leads go cold at Acme. <break time="400ms"/> Voice &amp; you &lt;win&gt;. '
                              '<break time="800ms"/> Next step.')
    assert (spoken["voice_id"], spoken["model_id"], spoken["locale"], spoken["accent"]) == ("ca-77", "sonic-3.6", "en-IN", "")
    assert spoken["speed"] == 1.4 and spoken["dictionary"] == "dict-acme"

    monkeypatch.setattr(av.settings, "avatar_cartesia_accent", "standard-hindi")
    assert av.narration_info(row)["stale"] is True
    av.narrate(db, row)
    assert cartesia.speeches[1]["accent"] == "standard-hindi" and cartesia.speeches[1]["locale"] == "en-IN"

    heygen = Recorder()
    av.submit(db, row, client=heygen)
    assert len(cartesia.speeches) == 2 and heygen.videos[0]["body"]["audio_asset_id"] == "aud1"
    assert row.result["narration"]["provider"] == "cartesia"


def test_prepare_clip_removes_room_rumble_and_keeps_the_voice():
    clip, seconds = av.prepare_clip("voice.wav", tone_wav())
    with wave.open(io.BytesIO(clip)) as out:
        rate, samples = out.getframerate(), array.array("h", out.readframes(out.getnframes()))
    assert (seconds, rate, max(abs(s) for s in samples) > 28000) == (9.0, 16000, True)
    assert level(samples, rate, 40) < 0.1 * level(samples, rate, 300)
    with pytest.raises(ValueError, match="at least 8 seconds"):
        av.prepare_clip("short.wav", tone_wav(seconds=3))


def test_cartesia_clone_records_the_spoken_language_then_adds_indian_english(monkeypatch):
    saved = {}
    import app.services.workspace as workspace

    monkeypatch.setattr(workspace, "save_connection_settings", lambda provider, values: saved.update({provider: values}))
    cartesia = FakeCartesia()
    out = av.clone_cartesia_voice(" Acme  Presenter ", "AUDIO.wav", tone_wav(), make_default=True, client=cartesia)
    clone = cartesia.clones[0]
    assert (clone["name"], clone["language"], clone["accent"]) == ("Acme Presenter", "hi", "standard-hindi")
    assert clone["clip"][0] == "voice.wav" and clone["clip"][2] == "audio/wav"
    assert cartesia.accents == [("ca-77", ["indian-english"])]
    assert out["id"] == "cartesia:ca-77" and out["accents"] == ["standard-hindi", "indian-english"]
    assert (av.AVATAR_DIR / "voices" / "ca-77.wav").read_bytes() == clone["clip"][1]
    assert saved == {"cartesia": {"avatar_voice_id": "ca-77", "avatar_voice_name": "Acme Presenter"}}

    kept = av.clone_cartesia_voice("Presenter", "AUDIO.wav", tone_wav(), client=FakeCartesia(accent_failure=True))
    assert kept["voice_id"] == "ca-77" and kept["accents"] == ["standard-hindi"] and "not enabled" in kept["accent_error"]
    with pytest.raises(ValueError, match="not a supported audio"):
        av.clone_cartesia_voice("Presenter", "notes.txt", b"hi", client=cartesia)


def test_elevenlabs_errors_surface_the_api_message():
    quota = httpx.Response(401, json={"detail": {"status": "quota_exceeded", "message": "You have 12 credits left."}})
    assert elevenlabs._error_message(quota) == ("You have 12 credits left.", "quota_exceeded")
    invalid = httpx.Response(422, json={"detail": [{"msg": "field required"}]})
    assert elevenlabs._error_message(invalid) == ("field required", "invalid_request")
    with pytest.raises(elevenlabs.ElevenLabsError, match="not connected"):
        elevenlabs.ElevenLabsClient(api_key="").subscription()
