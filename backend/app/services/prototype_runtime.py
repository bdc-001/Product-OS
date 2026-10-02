"""Run the workspace kit's Vite preview for a prototype working tree."""

from __future__ import annotations

import atexit
import logging
import os
import signal
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

from app.services.prototype_lovable import kit_root, link_node_modules

log = logging.getLogger(__name__)

PREVIEW_STARTING = "starting"

_LOCK = threading.Lock()
_PROCS: dict[int, subprocess.Popen] = {}
_PORTS: dict[int, int] = {}
_INSTALLING = False


def preview_port(prototype_id: int) -> int:
    return 41700 + (int(prototype_id) % 500)


def preview_url(prototype_id: int) -> str:
    return f"http://127.0.0.1:{preview_port(prototype_id)}/"


def preview_ready_url(prototype_id: int) -> str:
    """Return the Vite URL when that port is already serving, else empty."""
    port = preview_port(int(prototype_id))
    return preview_url(prototype_id) if _port_open(port) else ""


def _port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.4)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def _http_ok(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=1.2) as resp:
            return 200 <= int(resp.status) < 500
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def ensure_kit_install() -> str:
    global _INSTALLING
    root = kit_root()
    vite = root / "node_modules" / "vite"
    if vite.exists():
        return ""
    with _LOCK:
        if vite.exists():
            return ""
        if _INSTALLING:
            return "Installing preview dependencies…"
        _INSTALLING = True
    npm = shutil_which("npm")
    if not npm:
        _INSTALLING = False
        return "npm is not installed. Install Node.js to run the preview."
    log.info("npm install in %s", root)
    try:
        result = subprocess.run(
            [npm, "install"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=360,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        _INSTALLING = False
        return f"npm install failed: {exc}"
    _INSTALLING = False
    if result.returncode != 0:
        err = (result.stderr or result.stdout or "")[-800]
        return f"npm install failed: {err}"
    return ""


def shutil_which(name: str) -> str:
    from shutil import which

    return which(name) or ""


def stop_preview(prototype_id: int) -> None:
    with _LOCK:
        proc = _PROCS.pop(int(prototype_id), None)
        _PORTS.pop(int(prototype_id), None)
    if proc and getattr(proc, "poll", lambda: 1)() is None:
        terminate = getattr(proc, "terminate", None)
        if callable(terminate):
            terminate()
            try:
                proc.wait(timeout=5)
            except Exception:
                kill = getattr(proc, "kill", None)
                if callable(kill):
                    kill()


def _stop_all() -> None:
    for key in list(_PROCS):
        stop_preview(key)


atexit.register(_stop_all)


def _listener_pid(port: int) -> int | None:
    try:
        result = subprocess.run(
            ["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-t"],
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    for line in (result.stdout or "").split():
        try:
            return int(line)
        except ValueError:
            continue
    return None


def _free_stale_port(port: int) -> None:
    pid = _listener_pid(port)
    if not pid:
        return
    with _LOCK:
        ours = {proc.pid for proc in _PROCS.values() if proc.poll() is None}
    if pid in ours or pid == os.getpid():
        return
    try:
        os.kill(pid, signal.SIGTERM)
        time.sleep(0.25)
    except OSError:
        return


def _vite_command(root: Path, port: int) -> list[str] | None:
    args = ["dev", "--host", "127.0.0.1", "--port", str(port), "--strictPort", "--clearScreen", "false"]
    for binary in (root / "node_modules" / ".bin" / "vite", kit_root() / "node_modules" / ".bin" / "vite"):
        if binary.is_file():
            return [str(binary), *args]
    npx = shutil_which("npx")
    if npx:
        return [npx, "--no-install", "vite", *args]
    return None


def _read_log(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")[-600]
    except OSError:
        return ""


def ensure_preview(root: Path, prototype_id: int) -> tuple[str, str]:
    """Return (url, error). url is empty when the preview cannot start.

    PREVIEW_STARTING means Vite was spawned and the iframe should retry shortly.
    """
    pid = int(prototype_id)
    port = preview_port(pid)
    url = preview_url(pid)

    with _LOCK:
        proc = _PROCS.get(pid)
        running = proc is not None and proc.poll() is None
        if proc is not None and proc.poll() is not None:
            _PROCS.pop(pid, None)

    if running and _port_open(port):
        return url, ""
    if _port_open(port):
        return url, ""
    if running:
        return "", PREVIEW_STARTING

    err = ensure_kit_install()
    if err and not (kit_root() / "node_modules" / "vite").exists():
        return "", err
    link_node_modules(root)
    package = root / "package.json"
    if not package.is_file():
        return "", "The prototype kit is missing package.json in the prototype folder."

    cmd = _vite_command(root, port)
    if not cmd:
        return "", "Vite is not installed. Install Node.js to run the preview."

    log_path = root / ".vite-preview.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.pop("CI", None)
    env["BROWSER"] = "none"
    handle = log_path.open("ab", buffering=0)
    try:
        spawned = subprocess.Popen(
            cmd,
            cwd=root,
            env=env,
            stdout=handle,
            stderr=subprocess.STDOUT,
        )
    except OSError as exc:
        handle.close()
        return "", f"Could not start Vite: {exc}"
    handle.close()

    with _LOCK:
        _PROCS[pid] = spawned
        _PORTS[pid] = port

    if spawned.poll() is not None:
        tail = _read_log(log_path)
        return "", f"Vite exited before the preview was ready. {tail}".strip()
    return "", PREVIEW_STARTING
