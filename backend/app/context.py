"""Request- and job-scoped workspace context.

Every API request and every queued run executes inside exactly one workspace. Code that reads
`settings`, writes files, or queries a workspace-scoped table resolves the workspace from here.
Plain `threading.Thread` and `ThreadPoolExecutor` do not inherit context variables, so background
work must start through `spawn()` or `ContextThreadPoolExecutor`.
"""

from __future__ import annotations

import contextvars
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Callable, Iterator


class NoWorkspaceError(RuntimeError):
    pass


@dataclass
class WorkspaceContext:
    id: int
    slug: str
    name: str = ""
    timezone: str = "Asia/Kolkata"
    # Settings values resolved from this workspace's connections and product profile.
    values: dict[str, Any] = field(default_factory=dict)
    profile: dict[str, Any] = field(default_factory=dict)
    llm: dict[str, Any] = field(default_factory=dict)
    user_id: int | None = None
    user_email: str = ""
    role: str = ""
    version: int = 0
    run_id: int | None = None

    def child(self, **changes: Any) -> "WorkspaceContext":
        data = {**self.__dict__, **changes}
        data["values"] = dict(self.values)
        return WorkspaceContext(**data)


_current: contextvars.ContextVar[WorkspaceContext | None] = contextvars.ContextVar("workspace", default=None)
_system: contextvars.ContextVar[bool] = contextvars.ContextVar("system_scope", default=False)


def current() -> WorkspaceContext | None:
    return _current.get()


def require() -> WorkspaceContext:
    ctx = _current.get()
    if ctx is None:
        raise NoWorkspaceError("No workspace is active for this request or job.")
    return ctx


def current_workspace_id() -> int | None:
    ctx = _current.get()
    return ctx.id if ctx else None


def is_system() -> bool:
    return _system.get()


def activate(ctx: WorkspaceContext | None) -> contextvars.Token:
    return _current.set(ctx)


def deactivate(token: contextvars.Token) -> None:
    _current.reset(token)


@contextmanager
def use(ctx: WorkspaceContext | None) -> Iterator[WorkspaceContext | None]:
    token = _current.set(ctx)
    try:
        yield ctx
    finally:
        _current.reset(token)


@contextmanager
def system() -> Iterator[None]:
    """Cross-workspace access for the scheduler, worker claims and migrations only."""
    token = _system.set(True)
    try:
        yield
    finally:
        _system.reset(token)


def spawn(target: Callable[..., Any], *args: Any, name: str | None = None, daemon: bool = True, **kwargs: Any) -> threading.Thread:
    ctx = contextvars.copy_context()
    thread = threading.Thread(target=ctx.run, args=(target, *args), kwargs=kwargs, name=name, daemon=daemon)
    thread.start()
    return thread


class ContextThreadPoolExecutor(ThreadPoolExecutor):
    def submit(self, fn, /, *args, **kwargs):  # type: ignore[override]
        ctx = contextvars.copy_context()
        return super().submit(ctx.run, fn, *args, **kwargs)
