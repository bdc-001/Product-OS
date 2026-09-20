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
MAX_IDENTICAL_RUN_SECONDS = 1.0
MIN_MOTION_REGION_FRACTION = 0.12
MIN_VIDEO_BITRATE = {(1920, 1080): 220_000, (1080, 1920): 180_000}


def craft_for_scenes(scenes: list[dict]) -> list[dict]:
    """Mechanical treatment, luma and transition. The writer cannot choose a flat card."""
    counts: dict[str, int] = {}
    out = []
    prev_luma = None
    prev_visual = None
    photo = False
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
        plate = None
        if not photo and visual in {"flow", "orchestration"}:
            plate = "signal-flow.jpg"
            photo = True
        out.append({"luma": luma, "treatment": treatment, "transition": TRANSITIONS[index % 4], "plate": plate})
        prev_luma, prev_visual = luma, visual
    return out


def _saturation_luma(pixel: tuple[int, int, int]) -> tuple[float, float]:
    red, green, blue = pixel
    maximum, minimum = max(red, green, blue), min(red, green, blue)
    saturation = 0.0 if maximum == 0 else (maximum - minimum) / maximum
    luma = 0.2126 * red + 0.7152 * green + 0.0722 * blue
    return saturation, luma


def measure_frame(image: Image.Image) -> dict:
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
    if mean_sat < MIN_MEAN_SATURATION:
        issues.append(f"mean saturation {mean_sat:.3f} below {MIN_MEAN_SATURATION}")
    if p90 < MIN_P90_SATURATION:
        issues.append(f"p90 saturation {p90:.3f} below {MIN_P90_SATURATION}")
    if gradient_area < MIN_GRADIENT_AREA:
        issues.append(f"soft-gradient area {gradient_area:.2%} below {MIN_GRADIENT_AREA:.0%}")
    if luma_std < MIN_LUMA_STD and mean_sat < MIN_MEAN_SATURATION + 0.05:
        issues.append(f"luma std {luma_std:.1f} below {MIN_LUMA_STD} (blank or flat fill)")
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


def is_blank_frame(report: dict) -> bool:
    return report["luma_std"] < 6 and report["mean_saturation"] < 0.05


def measure_sequence(frames: list[Image.Image], fps: float = 2.0) -> dict:
    if not frames:
        return {"passed": False, "issues": ["no frames to inspect"]}
    reports = [measure_frame(frame) for frame in frames]
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
    blanks = sum(1 for report in reports if is_blank_frame(report))
    mean_sat = sum(report["mean_saturation"] for report in reports) / len(reports)
    mean_p90 = sum(report["p90_saturation"] for report in reports) / len(reports)
    mean_grad = sum(report["gradient_area"] for report in reports) / len(reports)
    mean_luma = sum(report["luma_std"] for report in reports) / len(reports)
    issues = []
    if blanks:
        issues.append(f"{blanks} blank frames")
    if mean_sat < MIN_MEAN_SATURATION:
        issues.append(f"film mean saturation {mean_sat:.3f} below {MIN_MEAN_SATURATION}")
    if mean_p90 < MIN_P90_SATURATION:
        issues.append(f"film p90 saturation {mean_p90:.3f} below {MIN_P90_SATURATION}")
    if mean_grad < MIN_GRADIENT_AREA:
        issues.append(f"film soft-gradient area {mean_grad:.2%} below {MIN_GRADIENT_AREA:.0%}")
    if mean_luma < MIN_LUMA_STD and mean_sat < MIN_MEAN_SATURATION + 0.05:
        issues.append(f"film luma std {mean_luma:.1f} below {MIN_LUMA_STD} (blank or flat fill)")
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


def evaluate_encoded_film(path: Path, aspect: str, ffmpeg: str, ffprobe: str, fps: float = 2.0) -> dict:
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
    motion = measure_sequence(frames, fps=fps)
    # Remotion's ffmpeg build has no freezedetect filter; identical-frame runs are measured from samples.
    issues = motion["issues"]
    report = {"passed": density["passed"] and motion["passed"], "issues": issues, "bitrate": density, "motion": motion}
    if not report["passed"]:
        raise ValueError("Film craft gate: " + "; ".join(issues or ["encoded picture failed density checks"]))
    return report
