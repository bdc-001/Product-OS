"""Workspace file storage under DATA_DIR/workspaces/<slug>/.

Module-level folder constants (`CAMPAIGN_DIR`, `ARTIFACT_DIR`, ...) are `WorkspaceDir` objects:
they behave like `pathlib.Path` but resolve against the active workspace each time they are used.
Paths saved to the database are stored relative to the workspace root (`to_stored`) and resolved
with `from_stored`, so the same rows work on a laptop and on the hosted volume.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from app import context
from app.config import data_root

SLUG_RE = re.compile(r"[^a-z0-9-]+")


def safe_slug(value: str, fallback: str = "workspace") -> str:
    slug = SLUG_RE.sub("-", (value or "").strip().lower()).strip("-")
    return slug[:60] or fallback


def workspaces_root() -> Path:
    return data_root() / "workspaces"


def workspace_root(slug: str | None = None) -> Path:
    name = slug or context.require().slug
    return workspaces_root() / safe_slug(name)


def workspace_path(*parts: str | os.PathLike) -> Path:
    return workspace_root().joinpath(*[str(p) for p in parts])


def platform_path(*parts: str | os.PathLike) -> Path:
    return data_root().joinpath(*[str(p) for p in parts])


class WorkspaceDir(os.PathLike):
    """A `Path` that resolves under the active workspace on every use."""

    __slots__ = ("_parts",)

    def __init__(self, *parts: str) -> None:
        self._parts = tuple(str(p) for p in parts)

    def path(self) -> Path:
        return workspace_root().joinpath(*self._parts)

    def __fspath__(self) -> str:
        return str(self.path())

    def __str__(self) -> str:
        return str(self.path())

    def __repr__(self) -> str:
        return f"WorkspaceDir({'/'.join(self._parts)!r})"

    def __format__(self, spec: str) -> str:
        return format(str(self.path()), spec)

    def __truediv__(self, other: str | os.PathLike) -> Path:
        return self.path() / other

    def __getattr__(self, name: str):
        return getattr(self.path(), name)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, WorkspaceDir):
            return self._parts == other._parts
        if isinstance(other, (str, os.PathLike)):
            return self.path() == Path(other)
        return NotImplemented

    def __hash__(self) -> int:
        return hash(("WorkspaceDir", self._parts))


def to_stored(path: str | os.PathLike | None) -> str:
    """Store a file path relative to the workspace root when it lives inside it."""
    if not path:
        return ""
    candidate = Path(path)
    try:
        root = workspace_root()
    except context.NoWorkspaceError:
        return str(candidate)
    try:
        return candidate.resolve().relative_to(root.resolve()).as_posix()
    except (ValueError, OSError):
        return str(candidate)


def from_stored(value: str | os.PathLike | None) -> Path | None:
    """Resolve a stored path. Absolute paths from another machine are remapped by their data suffix."""
    if not value:
        return None
    text = str(value)
    candidate = Path(text)
    if not candidate.is_absolute():
        resolved = workspace_root() / candidate
        if not resolved.exists() and candidate.parts[:1] == ("data",):
            # Rows written before workspaces stored paths relative to the repo root.
            return workspace_root().joinpath(*candidate.parts[1:])
        return resolved
    if candidate.exists():
        return candidate
    posix = candidate.as_posix()
    marker = "/workspaces/"
    if marker in posix:
        tail = posix.split(marker, 1)[1]
        parts = tail.split("/", 1)
        if len(parts) == 2:
            return workspace_root() / parts[1]
    if "/data/" in posix:
        return workspace_root() / posix.split("/data/", 1)[1]
    return candidate
