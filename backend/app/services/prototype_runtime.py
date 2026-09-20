"""Run the Lovable Sense Vite preview for a prototype working tree."""

from __future__ import annotations

import atexit
import logging
import os
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

from app.services.prototype_lovable import KIT_ROOT, link_node_modules

log = logging.getLogger(__name__)

_LOCK = threading.Lock()
_PROCS: dict[int, subprocess.Popen] = {}
_PORTS: dict[int, int] = {}
_INSTALLING = False


def preview_port(prototype_id: int) -> int:
    return 41700 + (int(prototype_id) % 500)


def preview_url(prototype_id: int) -> str:
    return f"http://127.0.0.1:{preview_port(prototype_id)}/"


def _port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.4)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def _http_ok(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=2) as resp:
            return 200 <= int(resp.status) < 500
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def ensure_kit_install() -> str:
    global _INSTALLING
    vite = KIT_ROOT / "node_modules" / "vite"
    if vite.exists():
        return ""
    with _LOCK:
        if vite.exists():
            return ""
        if _INSTALLING:
            return "Installing Sense preview dependencies…"
        _INSTALLING = True
    npm = shutil_which("npm")
    if not npm:
        _INSTALLING = False
        return "npm is not installed. Install Node.js to run the Sense preview."
    log.info("npm install in %s", KIT_ROOT)
    try:
        result = subprocess.run(
            [npm, "install"],
            cwd=KIT_ROOT,
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
    if proc and proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


def _stop_all() -> None:
    for key in list(_PROCS):
        stop_preview(key)


atexit.register(_stop_all)


def ensure_preview(root: Path, prototype_id: int) -> tuple[str, str]:
    """Return (url, error). url is empty when the preview cannot start."""
    pid = int(prototype_id)
    port = preview_port(pid)
    url = preview_url(pid)
    err = ensure_kit_install()
    if err and not (KIT_ROOT / "node_modules" / "vite").exists():
        return "", err
    link_node_modules(root)
    package = root / "package.json"
    if not package.is_file():
        return "", "Sense kit is missing package.json in the prototype folder."

    with _LOCK:
        proc = _PROCS.get(pid)
        if proc is not None and proc.poll() is None and _http_ok(url):
            return url, ""
        if proc is not None and proc.poll() is not None:
            _PROCS.pop(pid, None)

    if _port_open(port) and _http_ok(url):
        return url, ""

    npx = shutil_which("npx")
    if not npx:
        return "", "npx is not installed. Install Node.js to run the Sense preview."

    log_path = root / ".vite-preview.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["BROWSER"] = "none"
    env["CI"] = "1"
    cmd = [npx, "vite", "dev", "--host", "127.0.0.1", "--port", str(port), "--strictPort"]
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

    with _LOCK:
        _PROCS[pid] = spawned
        _PORTS[pid] = port

    deadline = time.time() + 45
    while time.time() < deadline:
        if spawned.poll() is not None:
            tail = ""
            try:
                tail = log_path.read_text(encoding="utf-8", errors="ignore")[-600]
            except OSError:
                pass
            return "", f"Vite exited before the preview was ready. {tail}"
        if _http_ok(url):
            return url, ""
        time.sleep(0.4)
    return "", "Sense preview timed out while starting Vite. Check .vite-preview.log."
