"""Copy the workspace's prototype kit into a prototype working tree. Never write the product repo.

Kits live in `kits/<name>` (override the folder with PROTOTYPE_KIT_DIR). Every workspace gets
`starter`; a workspace can point PROTOTYPE_KIT at its own product kit, which may describe itself
in a `kit.json` (`rules`, `kit`, `notes`, `context_files`, `topics`, `routes`).
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from app.config import ROOT, settings

KIT_ROOT: Path | None = None
DEFAULT_KIT = "starter"

SKIP_DIRS = {
    "node_modules",
    "dist",
    ".git",
    ".output",
    ".tanstack",
    ".nitro",
    ".wrangler",
    "logs",
    "__pycache__",
    ".lovable",
}

SKIP_NAMES = {".ds_store", ".env", ".env.local", ".dev.vars"}

ROOT_FILES = {
    "package.json",
    "vite.config.ts",
    "tsconfig.json",
    "components.json",
    "eslint.config.js",
    "bunfig.toml",
    "index.html",
    "PORTING.md",
    "tailwind.port-extend.js",
}

TEXT_EXT = {
    ".tsx",
    ".ts",
    ".jsx",
    ".js",
    ".css",
    ".json",
    ".svg",
    ".md",
    ".toml",
    ".html",
    ".mjs",
    ".cjs",
}


def kits_dir() -> Path:
    configured = (settings.prototype_kit_dir or "").strip()
    return Path(configured).expanduser() if configured else ROOT / "kits"


def kit_name() -> str:
    name = re.sub(r"[^a-z0-9_-]", "", str(settings.prototype_kit or "").strip().lower())
    return name or DEFAULT_KIT


def kit_root() -> Path:
    """The active workspace's kit, falling back to `starter` when that kit is not installed."""
    if KIT_ROOT is not None:
        return KIT_ROOT
    vendored = kits_dir() / kit_name()
    if (vendored / "package.json").is_file():
        return vendored
    fallback = kits_dir() / DEFAULT_KIT
    return fallback if (fallback / "package.json").is_file() else vendored


def kit_available() -> bool:
    root = kit_root()
    return (root / "package.json").is_file() and (root / "src").is_dir()


def _skip(path: Path) -> bool:
    if path.name.lower() in SKIP_NAMES:
        return True
    return any(part in SKIP_DIRS for part in path.parts)


def iter_kit_paths() -> list[Path]:
    if not kit_available():
        return []
    root = kit_root()
    found: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file() or _skip(path.relative_to(root)):
            continue
        rel = path.relative_to(root).as_posix()
        if rel in ROOT_FILES or rel.startswith("src/") or rel.startswith("public/"):
            found.append(path)
    return sorted(found, key=lambda item: item.as_posix())


def kit_files() -> list[dict]:
    root = kit_root()
    rows: list[dict] = []
    for path in iter_kit_paths():
        rel = path.relative_to(root).as_posix()
        if path.suffix.lower() not in TEXT_EXT and rel not in ROOT_FILES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        rows.append({"path": rel, "content": text})
    return rows


def copy_kit(dest: Path) -> None:
    root = kit_root()
    dest = dest.resolve()
    dest.mkdir(parents=True, exist_ok=True)
    for path in iter_kit_paths():
        rel = path.relative_to(root)
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)


def link_node_modules(dest: Path) -> Path:
    dest = dest.resolve()
    dest.mkdir(parents=True, exist_ok=True)
    link = dest / "node_modules"
    source = kit_root() / "node_modules"

    def link_ok() -> bool:
        try:
            return (link.resolve() / "vite").exists()
        except OSError:
            return False

    if link.exists() or link.is_symlink():
        if link_ok():
            return link
        try:
            if link.is_symlink() or link.is_file():
                link.unlink()
            elif link.is_dir() and not any(link.iterdir()):
                link.rmdir()
            elif link.is_dir():
                return link
        except OSError:
            return link
    if source.is_dir():
        try:
            link.symlink_to(source, target_is_directory=True)
        except OSError:
            pass
    return link
