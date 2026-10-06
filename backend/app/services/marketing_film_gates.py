"""Numeric craft gates for launch films. Structure QA cannot see these failures."""
from __future__ import annotations

import hashlib
import math
import statistics
import subprocess
import tempfile
from pathlib import Path

from PIL import Image

TRANSITIONS = ("cross-dissolve", "matched-element", "masked-wipe", "camera-push")
STATEMENT_TREATMENTS = ("centre-dark", "left-light", "emphasis-dark")
CONTRAST_TREATMENTS = ("split-dark", "split-light")
HUB_TREATMENTS = ("hub-dark", "hub-light")
STAGE_TREATMENT = "stage-light"
DEVICE_VISUALS = {"call", "conversation"}

MIN_MEAN_SATURATION = 0.10
MIN_P90_SATURATION = 0.22
MIN_GRADIENT_AREA = 0.30
MIN_LUMA_STD = 14.0
CLASSIC_GATES = {"mean_saturation": MIN_MEAN_SATURATION, "p90_saturation": MIN_P90_SATURATION,
                 "gradient_area": MIN_GRADIENT_AREA, "luma_std": MIN_LUMA_STD, "blank_luma_std": 6.0, "blank_saturation": 0.05}
# Aura is a pale white field by design: saturation lives in the bottom glow and the objects, so the floors drop to
# what a white frame with its glow measures. A frame is blank only when even the glow is gone.
AURA_GATES = {"mean_saturation": 0.03, "p90_saturation": 0.08, "gradient_area": 0.12, "luma_std": 3.0,
              "blank_luma_std": 1.5, "blank_saturation": 0.012}
MAX_IDENTICAL_RUN_SECONDS = 1.0
MIN_MOTION_REGION_FRACTION = 0.12
MIN_VIDEO_BITRATE = {(1920, 1080): 220_000, (1080, 1920): 180_000}


def craft_for_scenes(scenes: list[dict]) -> list[dict]:
    """Mechanical treatment, luma and transition. The writer cannot choose a flat card."""
    counts: dict[str, int] = {}
    out = []
    prev_luma = None
    prev_visual = None
    for index, scene in enumerate(scenes):
        visual = scene.get("visual") or "statement"
        counts[visual] = counts[visual] + 1 if visual == prev_visual else 0
        slot = counts[visual]
        if visual in DEVICE_VISUALS:
            treatment = STAGE_TREATMENT
            luma = "light"
        elif visual == "statement" or not scene.get("visual"):
            treatment = STATEMENT_TREATMENTS[slot % 3]
            luma = "light" if "light" in treatment else "dark"
        elif visual == "contrast":
            treatment = CONTRAST_TREATMENTS[slot % 2]
            luma = "light" if "light" in treatment else "dark"
        elif visual in {"orchestration", "stack"}:
            treatment = HUB_TREATMENTS[slot % 2]
            luma = "light" if "light" in treatment else "dark"
        else:
            luma = "dark" if prev_luma == "light" else "light"
            treatment = f"{visual}-{luma}"
        if prev_luma == luma and visual not in {"statement", "contrast"} and visual not in DEVICE_VISUALS:
            luma = "light" if luma == "dark" else "dark"
            treatment = treatment.replace("dark", "light") if luma == "light" else treatment.replace("light", "dark")
        out.append({"luma": luma, "treatment": treatment, "transition": TRANSITIONS[index % 4], "plate": None})
        prev_luma, prev_visual = luma, visual
    return out


LAUNCH_TRANSITIONS = {"call": "fade", "ui": "push", "volume": "slide", "messages": "slide", "chat": "fade", "search": "fade",
                      "docs": "push", "pulse": "fade", "fields": "slide", "relay": "wipe", "waveform": "slide",
                      "lockscreen": "fade", "typewriter": "fade", "versus": "push", "arcs": "wipe", "presenting": "fade",
                      "india": "wipe", "pool": "slide", "pills": "fade", "network": "fade", "stat": "fade", "toggles": "fade",
                      "bloom": "fade", "screenshot": "fade"}
# Aura never hard-cuts: the next block sharpens through the last (blur), emerges from the centre (zoom) or grows
# out of a dot. The shot after a call opens through the hang-up's white fill.
AURA_TRANSITIONS = {"call": "dot", "presenting": "zoom", "network": "zoom", "bloom": "zoom", "screenshot": "zoom", "endcard": "dot"}
AURA_MORPHS = {"blur", "zoom", "dot", "fill"}

# Twelve classic backgrounds, three per field, plus Aura's single airy field. Each film uses one theme end to end so
# its world stays cohesive; themes differ in dominant tone (white, dark or brand blue) and in which field carries type
# and product.
LAUNCH_BACKGROUNDS = {
    "light": ("cloud", "horizon", "grid"),
    "stage": ("stage", "porcelain", "tint"),
    "brand": ("brand", "beam", "deep"),
    "dark": ("midnight", "ink", "rings"),
    "aura": ("aura",),
}
AURA_THEME = "aura"
LAUNCH_THEMES = {
    AURA_THEME: {"statement": "aura", "product": "aura", "bg": {"aura": "aura"}},
    "daylight": {"statement": "light", "product": "brand", "bg": {"light": "cloud", "stage": "stage", "brand": "brand", "dark": "midnight"}},
    "horizon": {"statement": "light", "product": "brand", "bg": {"light": "horizon", "stage": "porcelain", "brand": "beam", "dark": "rings"}},
    "editorial": {"statement": "light", "product": "stage", "bg": {"light": "grid", "stage": "tint", "brand": "deep", "dark": "ink"}},
    "night": {"statement": "dark", "product": "dark", "bg": {"light": "cloud", "stage": "stage", "brand": "deep", "dark": "ink"}},
    "blueprint": {"statement": "brand", "product": "brand", "bg": {"light": "horizon", "stage": "tint", "brand": "beam", "dark": "midnight"}},
    "eclipse": {"statement": "dark", "product": "brand", "bg": {"light": "grid", "stage": "porcelain", "brand": "deep", "dark": "rings"}},
}
CLASSIC_THEMES = tuple(name for name in LAUNCH_THEMES if name != AURA_THEME)
# The classic fallback for callers that name no theme; new films get Aura from film_world.
DEFAULT_LAUNCH_THEME = "daylight"
LAUNCH_SCORES = ("launch-pulse-v1", "launch-drive-v1")
# Aura films are cut fast, so they rotate only the high-energy beds.
AURA_SCORES = ("launch-surge-v1", "launch-drive-v1")

# Film styles rotate like themes, but change the frame grammar itself: each has its own opening devices and
# signature shots, so consecutive films never share the same sequence of frames.
FILM_STYLES = {
    "call": {"open": {"volume", "call", "messages", "pool"}, "signature": {"call", "volume", "messages"},
             "arc": "a lived call that quietly goes wrong, heard on the handset"},
    "chat": {"open": {"chat", "search"}, "signature": {"chat", "search", "docs", "pulse"},
             "arc": "a question typed into a chat or a search box, the answer that never comes or comes wrong, the pile of work behind it"},
    "signal": {"open": {"fields", "waveform"}, "signature": {"fields", "relay", "waveform", "orbit"},
               "arc": "information moving between channels and systems, and the one detail that slips through"},
    "compare": {"open": {"lockscreen", "pool"}, "signature": {"lockscreen", "typewriter", "versus", "arcs"},
                "arc": "the same moment handled two ways, the quiet cost of the usual way set against the better one"},
}
DEFAULT_FILM_STYLE = "call"
# Every film sells a voice agent, so every style keeps one live call and the "Presenting <feature>" title card.
SHARED_SHOTS = {"kinetic", "ui", "endcard", "call", "presenting", "india", "pool"}
# Aura's signature shots join every style; network is Aura's mechanism shot and replaces orbit and relay.
AURA_SHOTS = {"pills", "network", "stat", "toggles", "bloom", "screenshot"}
AURA_REPLACES = {"orbit", "relay"}
# Films logged before the kit rotated drew their call from the style: a handset in the call style, glass elsewhere.
CALL_LOOKS = {"call": "handset", "chat": "glass", "signal": "glass", "compare": "glass"}
# The recurring set pieces each rotate independently against the film log, so no two consecutive films share
# a call screen, a ringtone, a title card or a close. Declared order is the order never-used variants are taken.
# "ink" is mono on black, too close to rotate as its own close; logged films that used it still render it.
FILM_KIT = {
    "call": ("duet", "handset", "glass", "flat", "split"),
    "ring": ("marimba", "classic", "pulse", "buzz"),
    "presenting": ("type", "lockup", "bold", "hub"),
    "endcard": ("recap", "poster", "lockup", "mono"),
}
LEGACY_KIT = {"ring": "marimba", "presenting": "type", "endcard": "mono"}
# Aura's own set pieces: the call rings out of waveform strands, the title card bursts a gem swarm, the close
# slides the wordmark out over the tagline. The ringtone still rotates.
AURA_KIT = {"call": ("rings",), "ring": FILM_KIT["ring"], "presenting": ("swarm",), "endcard": ("tagline",)}
KIT_FIELDS = {
    "call": {"handset": "stage", "glass": "dark", "flat": "light", "split": "stage", "duet": "light", "rings": "aura"},
    "presenting": {"type": "light", "lockup": "brand", "bold": "light", "hub": "dark", "swarm": "aura"},
    "endcard": {"mono": "light", "lockup": "light", "ink": "dark", "recap": "light", "poster": "brand", "tagline": "aura"},
}
STYLE_VISUAL_FIELDS = {"chat": "light", "search": "light", "lockscreen": "light", "typewriter": "light", "versus": "light",
                       "docs": "brand", "arcs": "brand", "pulse": "brand", "fields": "dark", "relay": "dark", "waveform": "dark",
                       "india": "light", "pool": "light", "pills": "aura", "network": "aura", "stat": "aura", "toggles": "aura",
                       "bloom": "aura", "screenshot": "aura"}


def is_aura(look: str | None) -> bool:
    """New films render in Aura unless their look names a classic theme."""
    return (look or AURA_THEME).strip().lower() == AURA_THEME


def film_kit(log: list[dict], own: dict | None = None, *, aura: bool = False) -> dict[str, str]:
    """The least recently used variant of each set piece across the logged films; a re-render keeps its own kit."""
    own = own or {}
    kit = {}
    for part, options in (AURA_KIT if aura else FILM_KIT).items():
        mine = (own.get("kit") or {}).get(part)
        if mine in options or (mine and mine in KIT_FIELDS.get(part, {})):
            kit[part] = mine
            continue
        # Films logged before the kit existed used the style's call look and the first ringtone and cards.
        used = [(e.get("kit") or {}).get(part) or (CALL_LOOKS.get(e.get("style") or DEFAULT_FILM_STYLE) if part == "call" else LEGACY_KIT[part])
                for e in log]
        kit[part] = least_recent(options, used)
    return kit


def style_shots(style: str, aura: bool = False) -> set[str]:
    """Every shot a film of this style may use. The call style keeps its orbit as the mechanism shot; under Aura the
    signature shots join every style and network takes over from orbit and relay."""
    plan = FILM_STYLES.get(style, FILM_STYLES[DEFAULT_FILM_STYLE])
    shots = plan["signature"] | plan["open"] | SHARED_SHOTS | ({"orbit"} if style == DEFAULT_FILM_STYLE else set())
    return (shots - AURA_REPLACES) | AURA_SHOTS if aura else shots


def style_opens(style: str, aura: bool = False) -> set[str]:
    """Opening shots for a style; Aura films may also open on floating capability pills."""
    plan = FILM_STYLES.get(style, FILM_STYLES[DEFAULT_FILM_STYLE])
    return plan["open"] | {"pills"} if aura else set(plan["open"])

# Scale shots rotate through single-object layouts; "wall" (the dense card grid) is only used when pinned.
LAUNCH_LAYOUTS = {"volume": ("dots", "timeline", "dialer"), "messages": ("thread", "lanes", "phone")}
PINNED_LAYOUTS = {"volume": ("wall",), "messages": ("wall",)}


def _landed_share(scene: dict) -> float:
    rows = (scene.get("screen") or {}).get("rows") or []
    return sum(row.get("hint") in {"delivered", "read"} for row in rows) / len(rows) if rows else 0.0


def launch_layouts(scenes: list[dict], seed: str = "") -> list[str | None]:
    """A pinned layout wins; otherwise the seed picks where each film enters the rotation and repeats step onward."""
    seen: dict[str, int] = {}
    out: list[str | None] = []
    for scene in scenes:
        visual = scene.get("visual")
        options = LAUNCH_LAYOUTS.get(visual)
        if not options:
            out.append(None)
            continue
        pinned = scene.get("layout")
        if pinned in options + PINNED_LAYOUTS[visual]:
            out.append(pinned)
            continue
        start = int(hashlib.sha256(f"{seed.strip().lower()}:{visual}".encode("utf-8")).hexdigest(), 16) % len(options) if seed.strip() else 0
        # The lock screen only receives what landed, so it cannot tell a story about failed sends.
        ordered = [options[(start + i) % len(options)] for i in range(len(options))]
        eligible = [name for name in ordered if name != "phone" or _landed_share(scene) >= 0.75]
        out.append(eligible[seen.get(visual, 0) % len(eligible)])
        seen[visual] = seen.get(visual, 0) + 1
    return out


def launch_theme(video: dict) -> str:
    """An explicit look wins; every other film is Aura. Classic themes render only when a look names one."""
    look = (video.get("look") or "").strip().lower()
    return look if look in LAUNCH_THEMES else AURA_THEME


def least_recent(options: tuple[str, ...], used: list[str]) -> str:
    """Never-used options first in declared order, then whichever was used longest ago (`used` is oldest first)."""
    last = {name: i for i, name in enumerate(used) if name in options}
    return min(options, key=lambda name: last.get(name, -1))


def launch_field(scene: dict, index: int, theme: str = DEFAULT_LAUNCH_THEME, style: str = DEFAULT_FILM_STYLE,
                 kit: dict | None = None) -> str:
    """Each kit variant owns its field (handset on the stage, glass in the dark, ink close on black); scale and
    mechanism sit in the dark; the theme places type and product."""
    if theme == AURA_THEME:
        return "aura"
    plan = LAUNCH_THEMES.get(theme) or LAUNCH_THEMES[DEFAULT_LAUNCH_THEME]
    field = _classic_field(scene, index, plan, style, kit)
    # Aura shots and set pieces own the aura field, which classic themes do not draw.
    return field if field in plan["bg"] else plan["product"]


def _classic_field(scene: dict, index: int, plan: dict, style: str, kit: dict | None) -> str:
    visual = scene.get("visual")
    if visual in STYLE_VISUAL_FIELDS:
        return STYLE_VISUAL_FIELDS[visual]
    if visual in KIT_FIELDS:
        default = CALL_LOOKS.get(style, "handset") if visual == "call" else FILM_KIT[visual][0]
        return KIT_FIELDS[visual][(kit or {}).get(visual) or default]
    if visual in {"volume", "orbit", "messages"}:
        return "dark"
    if visual == "ui":
        return plan["product"]
    return plan["statement"] if index == 0 or scene.get("kind") == "problem" else "brand"


def launch_craft(scenes: list[dict], theme: str = DEFAULT_LAUNCH_THEME, seed: str = "", style: str = DEFAULT_FILM_STYLE,
                 kit: dict | None = None) -> list[dict]:
    """Field, background, layout, luma and entrance for the launch grammar. Consecutive calls and screens share one field."""
    theme = theme if theme in LAUNCH_THEMES else DEFAULT_LAUNCH_THEME
    plan = LAUNCH_THEMES[theme]
    aura = theme == AURA_THEME
    layouts = launch_layouts(scenes, seed)
    kit = kit or {}
    pieces = AURA_KIT if aura else FILM_KIT
    variants = {"call": kit.get("call") or ("rings" if aura else CALL_LOOKS.get(style, "handset")),
                "presenting": kit.get("presenting") or pieces["presenting"][0],
                "endcard": kit.get("endcard") or pieces["endcard"][0]}
    out = []
    for index, scene in enumerate(scenes):
        field = launch_field(scene, index, theme, style, variants)
        visual = scene.get("visual") or "kinetic"
        # A type card never sits on the same blue as the shot before it; the theme's statement field keeps the cut visible.
        if visual == "kinetic" and field == "brand" and out and out[-1]["field"] == "brand":
            field = plan["statement"] if plan["statement"] != "brand" else "light"
        if aura:
            after_call = index and scenes[index - 1].get("visual") == "call" and visual != "call"
            transition = "fill" if after_call else AURA_TRANSITIONS.get(visual, "blur")
        else:
            transition = LAUNCH_TRANSITIONS.get(visual, "wipe")
        out.append({"luma": "light" if field in {"light", "stage", "aura"} else "dark", "treatment": f"launch-{visual}-{field}",
                    "transition": transition, "plate": None, "field": field,
                    "bg": plan["bg"][field], "theme": theme, **({"layout": layouts[index]} if layouts[index] else {}),
                    **({"look": variants[visual]} if visual in variants else {}),
                    **({"ring": kit["ring"]} if visual == "call" and kit.get("ring") else {})})
    return out


def _saturation_luma(pixel: tuple[int, int, int]) -> tuple[float, float]:
    red, green, blue = pixel
    maximum, minimum = max(red, green, blue), min(red, green, blue)
    saturation = 0.0 if maximum == 0 else (maximum - minimum) / maximum
    luma = 0.2126 * red + 0.7152 * green + 0.0722 * blue
    return saturation, luma


def measure_frame(image: Image.Image, gates: dict | None = None) -> dict:
    gates = gates or CLASSIC_GATES
    rgb = image.convert("RGB").resize((160, 90), Image.Resampling.BILINEAR)
    raw = rgb.tobytes()
    pixels = [(raw[i], raw[i + 1], raw[i + 2]) for i in range(0, len(raw), 3)]
    sats, lumas = zip(*(_saturation_luma(pixel) for pixel in pixels))
    ordered = sorted(sats)
    p90 = ordered[min(len(ordered) - 1, int(len(ordered) * 0.9))]
    width, height = rgb.size
    tiles, lively = 0, 0
    for top in range(0, height, 8):
        for left in range(0, width, 8):
            cell = [pixels[(y * width) + x] for y in range(top, min(top + 8, height)) for x in range(left, min(left + 8, width))]
            tiles += 1
            channels = list(zip(*cell))
            if cell and max(max(channel) - min(channel) for channel in channels) > 5:
                lively += 1
    gradient_area = lively / max(1, tiles)
    luma_std = statistics.pstdev(lumas) if len(lumas) > 1 else 0.0
    mean_sat = sum(sats) / len(sats)
    issues = []
    if mean_sat < gates["mean_saturation"]:
        issues.append(f"mean saturation {mean_sat:.3f} below {gates['mean_saturation']}")
    if p90 < gates["p90_saturation"]:
        issues.append(f"p90 saturation {p90:.3f} below {gates['p90_saturation']}")
    if gradient_area < gates["gradient_area"]:
        issues.append(f"soft-gradient area {gradient_area:.2%} below {gates['gradient_area']:.0%}")
    if luma_std < gates["luma_std"] and mean_sat < gates["mean_saturation"] + 0.05:
        issues.append(f"luma std {luma_std:.1f} below {gates['luma_std']} (blank or flat fill)")
    return {"passed": not issues, "issues": issues, "mean_saturation": mean_sat, "p90_saturation": p90,
            "gradient_area": gradient_area, "luma_std": luma_std}


def _thumb_hash(image: Image.Image) -> str:
    thumb = image.convert("RGB").resize((32, 18), Image.Resampling.BILINEAR)
    return hashlib.sha256(thumb.tobytes()).hexdigest()[:16]


def _region_signature(image: Image.Image, cols=4, rows=3) -> list[str]:
    rgb = image.convert("RGB")
    width, height = rgb.size
    cw, ch = max(1, width // cols), max(1, height // rows)
    marks = []
    for row in range(rows):
        for col in range(cols):
            tile = rgb.crop((col * cw, row * ch, min(width, (col + 1) * cw), min(height, (row + 1) * ch)))
            marks.append(_thumb_hash(tile))
    return marks


def is_blank_frame(report: dict, gates: dict | None = None) -> bool:
    gates = gates or CLASSIC_GATES
    return report["luma_std"] < gates["blank_luma_std"] and report["mean_saturation"] < gates["blank_saturation"]


def measure_sequence(frames: list[Image.Image], fps: float = 2.0, gates: dict | None = None) -> dict:
    gates = gates or CLASSIC_GATES
    if not frames:
        return {"passed": False, "issues": ["no frames to inspect"]}
    reports = [measure_frame(frame, gates) for frame in frames]
    hashes = [_thumb_hash(frame) for frame in frames]
    run = longest = 1
    for previous, current in zip(hashes, hashes[1:]):
        run = run + 1 if previous == current else 1
        longest = max(longest, run)
    freeze = (longest / fps) if fps else longest
    moving = 0
    regions = len(_region_signature(frames[0]))
    for previous, current in zip(frames, frames[1:]):
        changed = sum(a != b for a, b in zip(_region_signature(previous), _region_signature(current)))
        if changed / regions >= MIN_MOTION_REGION_FRACTION:
            moving += 1
    motion = moving / max(1, len(frames) - 1)
    blanks = sum(1 for report in reports if is_blank_frame(report, gates))
    mean_sat = sum(report["mean_saturation"] for report in reports) / len(reports)
    mean_p90 = sum(report["p90_saturation"] for report in reports) / len(reports)
    mean_grad = sum(report["gradient_area"] for report in reports) / len(reports)
    mean_luma = sum(report["luma_std"] for report in reports) / len(reports)
    issues = []
    if blanks:
        issues.append(f"{blanks} blank frames")
    if mean_sat < gates["mean_saturation"]:
        issues.append(f"film mean saturation {mean_sat:.3f} below {gates['mean_saturation']}")
    if mean_p90 < gates["p90_saturation"]:
        issues.append(f"film p90 saturation {mean_p90:.3f} below {gates['p90_saturation']}")
    if mean_grad < gates["gradient_area"]:
        issues.append(f"film soft-gradient area {mean_grad:.2%} below {gates['gradient_area']:.0%}")
    if mean_luma < gates["luma_std"] and mean_sat < gates["mean_saturation"] + 0.05:
        issues.append(f"film luma std {mean_luma:.1f} below {gates['luma_std']} (blank or flat fill)")
    if freeze > MAX_IDENTICAL_RUN_SECONDS + 1e-6:
        issues.append(f"identical-frame run {freeze:.2f}s exceeds {MAX_IDENTICAL_RUN_SECONDS}s")
    if motion < MIN_MOTION_REGION_FRACTION:
        issues.append(f"moving-region share {motion:.2%} below {MIN_MOTION_REGION_FRACTION:.0%}")
    return {"passed": not issues, "issues": issues, "freeze_seconds": freeze, "motion_fraction": motion,
            "frames": len(frames), "frame_reports": reports, "mean_saturation": mean_sat, "mean_gradient_area": mean_grad}


def bitrate_floor(width: int, height: int) -> int:
    return MIN_VIDEO_BITRATE.get((width, height), 180_000)


def assert_encode_density(info: dict, aspect: str) -> dict:
    """A suspiciously small encode is an empty or frozen picture."""
    picture = next((stream for stream in info.get("streams", []) if stream.get("codec_type") == "video"), {})
    width = int(picture.get("width") or (1080 if aspect == "portrait" else 1920))
    height = int(picture.get("height") or (1920 if aspect == "portrait" else 1080))
    raw = picture.get("bit_rate") or info.get("format", {}).get("bit_rate") or 0
    try:
        total = int(float(raw))
    except (TypeError, ValueError):
        total = 0
    audio = next((stream for stream in info.get("streams", []) if stream.get("codec_type") == "audio"), {})
    try:
        audio_rate = int(float(audio.get("bit_rate") or 192000))
    except (TypeError, ValueError):
        audio_rate = 192000
    video_rate = total - audio_rate if picture.get("bit_rate") in (None, "", "N/A") else total
    floor = bitrate_floor(width, height)
    if video_rate < floor:
        raise ValueError(f"Encoded picture bitrate {video_rate} is below the {floor} craft floor; the master is too empty to ship.")
    return {"video_bitrate": video_rate, "floor": floor, "passed": True}


def _run(command: list[str], timeout=120) -> subprocess.CompletedProcess:
    env = None
    binary = Path(command[0])
    if binary.name in {"ffmpeg", "ffprobe"} and "@remotion" in str(binary):
        import os
        import platform
        env = os.environ.copy()
        env["DYLD_LIBRARY_PATH" if platform.system() == "Darwin" else "LD_LIBRARY_PATH"] = str(binary.parent)
    return subprocess.run(command, capture_output=True, text=True, timeout=timeout, env=env)


def evaluate_encoded_film(path: Path, aspect: str, ffmpeg: str, ffprobe: str, fps: float = 2.0, *, aura: bool = False) -> dict:
    probe = _run([ffprobe, "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)])
    if probe.returncode:
        detail = (probe.stderr or probe.stdout or "").strip().splitlines()[-1:] or ["unknown probe error"]
        raise ValueError("Could not probe the encoded film for craft gates: " + detail[0][:240])
    import json
    info = json.loads(probe.stdout)
    density = assert_encode_density(info, aspect)
    with tempfile.TemporaryDirectory() as folder:
        pattern = str(Path(folder) / "%04d.png")
        extract = _run([ffmpeg, "-y", "-i", str(path), "-r", str(fps), "-an", pattern], timeout=180)
        if extract.returncode:
            raise ValueError("Could not sample frames for craft gates.")
        frames = [Image.open(item).copy() for item in sorted(Path(folder).glob("*.png"))]
    motion = measure_sequence(frames, fps=fps, gates=AURA_GATES if aura else CLASSIC_GATES)
    # Remotion's ffmpeg build has no freezedetect filter; identical-frame runs are measured from samples.
    issues = motion["issues"]
    report = {"passed": density["passed"] and motion["passed"], "issues": issues, "bitrate": density, "motion": motion}
    if not report["passed"]:
        raise ValueError("Film craft gate: " + "; ".join(issues or ["encoded picture failed density checks"]))
    return report
