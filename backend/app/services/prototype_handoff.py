"""Deterministic source and layout handoff; never reads or writes production config."""
import hashlib
import json
import re
from pathlib import Path

ASSETS = Path(__file__).resolve().parents[1] / "static" / "prototype-handoff"


def handoff_files(prototype_id: int, title: str, files: dict[str, str]) -> dict[str, str]:
    hashes = {path: hashlib.sha256(body.encode()).hexdigest() for path, body in sorted(files.items())}
    fingerprint = hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()
    try:
        package = json.loads(files.get("package.json", "{}"))
    except ValueError:
        package = {}
    geometry = []
    for path, body in sorted(files.items()):
        if not path.startswith("src/"):
            continue
        for number, line in enumerate(body.splitlines(), 1):
            if re.search(r"className|style=|(?:COLLAPSED|EXPANDED)\s*=", line) and re.search(r"(?:\b(?:p[xytrbl]?|m[xytrbl]?|gap|w|h|min-w|max-w|grid-cols|text|leading|items|justify)-|width|height|COLLAPSED|EXPANDED)", line):
                geometry.append({"file": path, "line": number, "source": line.strip()})
    manifest = {
        "version": 1, "prototype_id": prototype_id, "title": title,
        "source_fingerprint": fingerprint, "files": hashes,
        "dependencies": package.get("dependencies", {}),
        "css_sources": [p for p in files if p.endswith(".css")],
        "page_sources": [p for p in files if p.startswith("src/pages/")],
        "reference_root_px": 16, "reference_root_note": "Verify in the reference browser before building; pass --root-px if different.",
        "scope_attribute": f'data-prototype-ui="{prototype_id}"',
        "viewports": [{"width": 1440, "height": 900}, {"width": 1280, "height": 800}, {"width": 390, "height": 844}],
        "verification": "unmeasured", "geometry_sources": geometry,
    }
    out = {f"handoff/{p.name}": p.read_text() for p in ASSETS.iterdir() if p.is_file()}
    out["handoff/manifest.json"] = json.dumps(manifest, indent=2) + "\n"
    out["PORTING.md"] = out.pop("handoff/PORTING.md")
    if "PORTING.md" in files:
        out["handoff/previous-porting.md"] = files["PORTING.md"]
    return out
