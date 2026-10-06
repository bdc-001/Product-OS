"""The active workspace's brand kit: display name, logos and the PDF wordmark.

Owners upload `logo-dark`, `logo-light`, `mark` and `wordmark` files into the workspace `brand/` folder.
Workspaces without uploads get a generated text wordmark. A local install can also set `brand.pack`
to a name whose files sit in the git-ignored `static/artifacts/logos/` folder
(`<pack>-lockup-dark.svg`, `<pack>-lockup-light.svg`, `<pack>-mark.svg`).
"""

from __future__ import annotations

import base64
import html
from pathlib import Path

from app.storage import workspace_path

APP_DIR = Path(__file__).resolve().parents[1]
STATIC = APP_DIR / "static" / "artifacts"
STATIC_LOGOS = STATIC / "logos"
ASSETS = APP_DIR / "assets"
MIME = {".svg": "image/svg+xml", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}
def _profile() -> dict:
    from app.services.profile import load_profile

    return load_profile()


def brand_pack() -> str:
    try:
        pack = str((_profile().get("brand") or {}).get("pack") or "").strip().lower()
    except Exception:
        return ""
    return pack if pack.replace("-", "").replace("_", "").isalnum() else ""


def artifact_path(name: str) -> Path:
    """A design brief or stylesheet under `static/artifacts`; the brand pack's copy in the
    git-ignored `static/artifacts/packs/<pack>/` wins when present."""
    pack = brand_pack()
    packed = STATIC / "packs" / pack / name if pack else None
    return packed if packed and packed.is_file() else STATIC / name


def _pack_file(pack: str, stem: str) -> Path:
    return {
        "logo-dark": STATIC_LOGOS / f"{pack}-lockup-dark.svg",
        "logo-light": STATIC_LOGOS / f"{pack}-lockup-light.svg",
        "mark": STATIC_LOGOS / f"{pack}-mark.svg",
        "wordmark": ASSETS / "logo.png",
    }.get(stem, STATIC_LOGOS / f"{pack}-{stem}.svg")


def brand_name() -> str:
    profile = _profile()
    return profile.get("company_name") or profile.get("product_name") or profile.get("workspace") or "Product"


def _uploaded(stem: str, exts: tuple[str, ...] = tuple(MIME)) -> Path | None:
    try:
        folder = workspace_path("brand")
    except Exception:
        return None
    for ext in exts:
        path = folder / f"{stem}{ext}"
        if path.is_file():
            return path
    return None


def _asset(stem: str, exts: tuple[str, ...] = tuple(MIME)) -> Path | None:
    found = _uploaded(stem, exts)
    if found:
        return found
    pack = brand_pack()
    packed = _pack_file(pack, stem) if pack else None
    return packed if packed and packed.is_file() and packed.suffix in exts else None


def brand_asset(stem: str) -> Path | None:
    """Uploaded or packed `logo-dark` / `logo-light` / `mark` file, if the workspace has one."""
    return _asset(stem)


def mark_svg() -> str:
    initial = html.escape((brand_name()[:1] or "P").upper())
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="40" height="40" viewBox="0 0 40 40">'
        '<circle cx="20" cy="20" r="19" fill="#2563EB"/>'
        f'<text x="20" y="27" text-anchor="middle" font-family="Inter, Helvetica, Arial, sans-serif" font-size="20" font-weight="700" fill="#FFFFFF">{initial}</text>'
        "</svg>"
    )


def wordmark_svg(*, dark: bool) -> str:
    name = html.escape(brand_name())
    fill = "#FFFFFF" if dark else "#050505"
    width = max(80, 15 * len(brand_name()) + 8)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="32" viewBox="0 0 {width} 32">'
        f'<text x="0" y="24" font-family="Inter, Helvetica, Arial, sans-serif" font-size="24" font-weight="700" fill="{fill}">{name}</text>'
        "</svg>"
    )


def logo_data_uri(*, dark: bool) -> str:
    path = _asset("logo-dark" if dark else "logo-light")
    if path is None:
        return "data:image/svg+xml;base64," + base64.b64encode(wordmark_svg(dark=dark).encode()).decode("ascii")
    return f"data:{MIME[path.suffix.lower()]};base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def pdf_wordmark() -> Path | None:
    """PNG/JPEG wordmark for fpdf release-note headers, or None to print the name only."""
    return _asset("wordmark", (".png", ".jpg", ".jpeg"))


def pdf_heading(kind: str = "Product release notes") -> str:
    return f"{brand_name().upper()}  ·  {kind}"
