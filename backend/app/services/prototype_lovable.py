"""Copy the checked-in Lovable Sense app into a prototype working tree. Never write go_services."""

from __future__ import annotations

import shutil
from pathlib import Path

from app.config import ROOT

KIT_ROOT = ROOT / "debff5d2-8aaa-4ee5-8522-7112774c3c48"

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


def kit_available() -> bool:
    return (KIT_ROOT / "package.json").is_file() and (KIT_ROOT / "src").is_dir()


def _skip(path: Path) -> bool:
    if path.name.lower() in SKIP_NAMES:
        return True
    return any(part in SKIP_DIRS for part in path.parts)


def iter_kit_paths() -> list[Path]:
    if not kit_available():
        return []
    found: list[Path] = []
    for path in KIT_ROOT.rglob("*"):
        if not path.is_file() or _skip(path.relative_to(KIT_ROOT)):
            continue
        rel = path.relative_to(KIT_ROOT).as_posix()
        if rel in ROOT_FILES or rel.startswith("src/") or rel.startswith("public/"):
            found.append(path)
    return sorted(found, key=lambda item: item.as_posix())


def kit_files() -> list[dict]:
    rows: list[dict] = []
    for path in iter_kit_paths():
        rel = path.relative_to(KIT_ROOT).as_posix()
        if path.suffix.lower() not in TEXT_EXT and rel not in ROOT_FILES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        rows.append({"path": rel, "content": text})
    return rows


def copy_kit(dest: Path) -> None:
    dest = dest.resolve()
    dest.mkdir(parents=True, exist_ok=True)
    for path in iter_kit_paths():
        rel = path.relative_to(KIT_ROOT)
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)


def link_node_modules(dest: Path) -> Path:
    dest = dest.resolve()
    dest.mkdir(parents=True, exist_ok=True)
    link = dest / "node_modules"
    source = KIT_ROOT / "node_modules"
    if link.exists() or link.is_symlink():
        return link
    if source.is_dir():
        link.symlink_to(source, target_is_directory=True)
    return link
