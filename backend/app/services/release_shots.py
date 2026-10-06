"""Release-note screenshots rendered from the shipped product frontend code.

The release diff names the frontend files that changed. A planner reads that source and
writes shot specs: which component file to mount, its props, and fixture JSON for every
API call it makes. The product checkout's own Vite serves each component alone
(`static/release-shots/harness-server.mjs`); Playwright answers the API calls from the
fixtures and crops the rendered block. Shots that do not render the fixture data, hit an
error boundary, or fail visual review are repaired once, then dropped rather than shipped.
"""

from __future__ import annotations

import base64
import fnmatch
import glob
import hashlib
import json
import logging
import os
import re
import shutil
import socket
import subprocess
import threading
import time
from pathlib import Path
from urllib.parse import urlparse

from app.context import spawn
from app.clients.llm import LLMJsonError, chat_json
from app.config import settings
from app.services.codebase import _git, codebase_root
from app.services.prompts import with_preamble
from app.storage import WorkspaceDir, from_stored, to_stored

log = logging.getLogger(__name__)

HARNESS = Path(__file__).resolve().parents[1] / "static" / "release-shots" / "harness-server.mjs"
SHOTS_ROOT = WorkspaceDir("release_shots")
CACHE_DIR = WorkspaceDir("release_shots", ".vite-cache")
TENANT = "acme-demo"
MAX_SHOTS = 4
DEVICE_SCALE = 2
SECTIONS = ["Functional Overview", "Navigation", "How to Use", "Configuration Options", "Outcome Analysis"]
CODE_EXT = (".jsx", ".tsx", ".js", ".ts")
ALLOWED_HOSTS = ("fonts.googleapis.com", "fonts.gstatic.com")
SHOT_ID = re.compile(r"[^a-z0-9-]+")
CORS = {"Access-Control-Allow-Origin": "*", "Access-Control-Allow-Headers": "*", "Access-Control-Allow-Methods": "*"}

PLAN_PROMPT = with_preamble(
    """You plan product screenshots for a [[company]] client release note. Each screenshot is
rendered from the shipped React code: ONE component file is mounted alone (a Redux store
and a MemoryRouter at /tenant/acme-demo are already provided) and every API call it makes
is answered by fixture JSON you write. Nothing else from the app is on the page.

Input: `features` (what shipped) and `frontend` (changed frontend files with path, diff,
source, API client snippets, and `used_by` showing how a parent renders the component).

Pick the views a reader needs to understand the feature: the new table, card row, filter
bar, modal or settings panel. Skip features with no visible UI change. At most 4 shots,
at most 2 per feature. Prefer the smallest component that shows the whole new surface
(a section, not the whole page). Never invent UI that is not in the source.

Each shot:
- id: short kebab-case, unique.
- feature: the exact feature name from `features`.
- module: a path from `frontend` starting "src/" (the changed file or its parent from used_by).
- export: "default" or the named export.
- props: JSON props the component needs, copied from the parent usage. No functions;
  omit callbacks. Dates as ISO strings.
- noop_props (optional): names of callback props the component cannot render without,
  such as a modal's onClose; each receives a function that does nothing.
- mocks: every API call made on mount, as {"method": "GET|POST|PUT|DELETE", "path":
  "/{tenant}/...", "json": <response body>}. `path` is the URL path after /v1, with
  {tenant} for the tenant segment and * as a wildcard. The body must have exactly the
  shape the code reads: follow the API client snippet (e.g. `return { data: response.data }`
  means the component's `res.data` is your body).
- expect_text: 1-3 strings that only appear if your fixture data rendered (a row name or
  a number from your data, formatted the way the component formats it).
- actions (optional): steps after render, e.g. {"type": "click", "text": "Next"},
  {"type": "click", "selector": "button[aria-expanded]"}, {"type": "select", "selector":
  "select[aria-label='Tool type']", "value": "custom_action"}, {"type": "hover",
  "selector": "..."}, {"type": "wait", "ms": 300}. Native <select> menus cannot be shown open.
- crop (optional): CSS selector inside the component to capture instead of all of it.
- width: stage width in px, 360-1440. A full-width analytics block is about 1100; a modal 720.
- providers (optional): wrappers from src/contexts/ when the component calls their hooks,
  e.g. {"module": "src/contexts/AuthContext.jsx", "export": "AuthProvider"}. Add mocks
  for any calls the provider makes.
- local_storage (optional): {"key": "string value"} the component reads.
- route / route_path (optional, for page components that read useParams): the URL, e.g.
  "/tenant/acme-demo/campaigns/c1/leads", and its react-router pattern, e.g.
  "/tenant/:tenantId/campaigns/:campaignId/leads". Default "/tenant/acme-demo" and
  "/tenant/:tenantId/*".
- section: the release-note section it illustrates, one of: """
    + ", ".join(SECTIONS)
    + """.
- caption: one factual sentence naming what the image shows.
- shows: what the reader should notice, used to place the image beside the right text.

Fixture data: plausible B2B volumes, generic names (Acme Lending, "Payment reminder",
fetch_customer_data), no real customer, employee or person names, no real phone numbers
or emails. Make numbers internally consistent (totals add up, rates match counts).

Return JSON: {"shots": [...], "skipped": [{"feature": "...", "reason": "..."}]}
"""
)

REPAIR_PROMPT = with_preamble(
    """A planned release-note screenshot failed. You get the shot spec, the failure, API
requests that had no fixture, browser console errors, the text that did render, the
component source, and (when available) the failed render itself. Return the corrected
shot as {"shot": {...}} using the same fields, or {"shot": null, "reason": "..."} when
the component cannot render in isolation. Common fixes: add the missing mock, fix the
response shape to what the code reads, pass a required prop, add a provider, change
expect_text to how the component formats the value.
"""
)

REVIEW_PROMPT = with_preamble(
    """You review product screenshots before they go into a client release note. Each
image is a React component rendered with fixture data. For each image, decide whether it
is fit to publish: real product UI fully rendered, no error message, no loading spinner
or skeleton, not an empty state (unless the caption says so), nothing clipped mid-control,
data that looks plausible, no real person or company names. Return JSON:
{"reviews": [{"id": "<shot id>", "ok": true|false, "reason": "<short reason when not ok>"}]}
"""
)


def ui_subdir() -> str:
    """The repository's frontend folder (Repositories → UI path)."""
    return (settings.repo_ui_path or "").strip().strip("/")


def ui_root() -> Path | None:
    configured = (settings.release_shots_ui_path or "").strip()
    if configured:
        root = Path(configured).expanduser()
    elif ui_subdir():
        root = codebase_root() / ui_subdir()
    else:
        return None
    return root if (root / "package.json").is_file() else None


def node_binary() -> str:
    configured = (settings.release_shots_node or "").strip()
    if configured and Path(configured).is_file():
        return configured
    found = shutil.which("node")
    if found:
        return found
    # launchd jobs do not load nvm, so look where nvm and Homebrew install node.
    candidates = sorted(glob.glob(str(Path.home() / ".nvm/versions/node/*/bin/node")), reverse=True)
    candidates += ["/opt/homebrew/bin/node", "/usr/local/bin/node"]
    return next((path for path in candidates if Path(path).is_file()), "")


def readiness() -> dict:
    if not settings.release_shots_enabled:
        return {"ok": False, "reason": "Release screenshots are off (RELEASE_SHOTS_ENABLED=false)."}
    root = ui_root()
    if not root:
        if not ui_subdir() and not (settings.release_shots_ui_path or "").strip():
            return {"ok": False, "reason": "No frontend folder is set on the repository. Add a UI path in Repositories."}
        return {"ok": False, "reason": f"Frontend not found at {ui_subdir() or settings.release_shots_ui_path} (no package.json)."}
    if not (root / "node_modules" / "vite").is_dir():
        return {"ok": False, "reason": f"Product frontend dependencies are not installed. Run npm ci in {root}."}
    if not node_binary():
        return {"ok": False, "reason": "node is not installed or not on PATH."}
    try:
        import playwright.sync_api  # noqa: F401
    except ImportError:
        return {"ok": False, "reason": "Python Playwright is not installed (pip install playwright; playwright install chromium)."}
    return {"ok": True, "reason": "", "ui": str(root)}


def _ui_rel(root: Path) -> str:
    try:
        return str(root.resolve().relative_to(codebase_root().resolve()))
    except ValueError:
        return ui_subdir()


def _git_out(repo: Path, *args: str) -> str:
    proc = _git(repo, *args, timeout=90, exclusive=False)
    return proc.stdout if proc.returncode == 0 else ""


def _is_component_file(path: str) -> bool:
    lowered = path.lower()
    if not lowered.endswith(CODE_EXT) or "/src/" not in f"/{lowered}":
        return False
    return not any(part in lowered for part in ("__tests__", ".test.", ".spec.", ".stories.", "/mocks/", "/types/"))


def _api_snippets(root: Path, source: str) -> list[dict]:
    api_file = root / "src" / "services" / "api.js"
    text = api_file.read_text(errors="ignore") if api_file.is_file() else ""
    lines = text.splitlines()
    out = []
    for method in dict.fromkeys(re.findall(r"\b\w+API\.(\w+)\s*\(", source)):
        pattern = re.compile(rf"^\s*{re.escape(method)}\s*:\s*(async\b|\()")
        for i, line in enumerate(lines):
            if pattern.match(line):
                out.append({"method": method, "file": "src/services/api.js", "code": "\n".join(lines[i : i + 32])})
                break
        if len(out) >= 4:
            break
    for rel in re.findall(r"from\s+['\"](\.{1,2}/[^'\"]*[Aa]pi[^'\"]*)['\"]", source)[:2]:
        out.append({"file": rel, "code": ""})
    return out


def _used_by(repo: Path, ui_rel: str, module: str) -> list[str]:
    name = Path(module).stem
    if not name or name == "index":
        return []
    hits = _git_out(repo, "grep", "-n", "-A", "14", "-e", f"<{name}[ >]", "-e", f"<{name}$", "--", f"{ui_rel}/src")
    blocks = [block.strip() for block in hits.split("\n--\n") if block.strip()]
    return [block[:1600] for block in blocks[:2]]


def frontend_evidence(base_sha: str, head_sha: str) -> dict:
    root = ui_root()
    repo = codebase_root()
    if not root or not base_sha or not head_sha:
        return {"files": []}
    ui_rel = _ui_rel(root)
    spec = f"{base_sha}..{head_sha}"
    stat = _git_out(repo, "diff", "--numstat", spec, "--", f"{ui_rel}/src")
    changed = []
    for line in stat.splitlines():
        parts = line.split("\t")
        if len(parts) != 3 or not _is_component_file(parts[2]):
            continue
        added = int(parts[0]) if parts[0].isdigit() else 0
        changed.append((added, parts[2]))
    changed.sort(reverse=True)
    files = []
    for added, path in changed[:10]:
        rel = path[len(ui_rel) + 1 :] if path.startswith(ui_rel + "/") else path
        entry = {"path": rel, "lines_added": added, "diff": _git_out(repo, "diff", spec, "--", path)[:2500]}
        if len(files) < 6:
            entry.update(_component_context(root, repo, ui_rel, rel))
        files.append(entry)
    return {"files": files, "ui_rel": ui_rel}


def _component_context(root: Path, repo: Path, ui_rel: str, rel: str) -> dict:
    disk = root / rel
    source = disk.read_text(errors="ignore") if disk.is_file() else ""
    if not source:
        return {}
    return {"source": source[:9000], "api": _api_snippets(root, source), "used_by": _used_by(repo, ui_rel, rel)}


def component_evidence(paths: list[str], spec: str = "") -> dict:
    """Planner evidence for existing components (repo- or UI-relative paths); `spec` adds their diff."""
    root = ui_root()
    if not root:
        return {"files": []}
    repo = codebase_root()
    ui_rel = _ui_rel(root)
    files = []
    for path in dict.fromkeys(paths):
        rel = path[len(ui_rel) + 1 :] if path.startswith(ui_rel + "/") else path
        if not _is_component_file(rel):
            continue
        context = _component_context(root, repo, ui_rel, rel)
        if context:
            if spec:
                context["diff"] = _git_out(repo, "diff", spec, "--", f"{ui_rel}/{rel}")[:2500]
            files.append({"path": rel, **context})
        if len(files) >= 6:
            break
    return {"files": files, "ui_rel": ui_rel}


def _slug(text: str, fallback: str) -> str:
    slug = SHOT_ID.sub("-", (text or "").lower()).strip("-")[:48]
    return slug or fallback


def _clean_module(value: str, root: Path) -> str:
    rel = str(value or "").strip().lstrip("/")
    if not rel.startswith("src/") or ".." in rel.split("/"):
        return ""
    return rel if (root / rel).is_file() else ""


def _clean_route(raw: dict) -> dict:
    route = str(raw.get("route") or "").strip()
    pattern = str(raw.get("route_path") or "").strip()
    if not route.startswith(f"/tenant/{TENANT}") or any(c in route for c in "?#\\") or ".." in route:
        route = f"/tenant/{TENANT}"
    if not pattern.startswith("/tenant/:tenantId") or ".." in pattern:
        pattern = "/tenant/:tenantId/*"
    return {"route": route, "route_path": pattern}


def clean_shot(raw: dict, root: Path, index: int, features: list[str]) -> dict | None:
    if not isinstance(raw, dict):
        return None
    module = _clean_module(str(raw.get("module") or ""), root)
    if not module:
        return None
    providers = []
    for item in raw.get("providers") or []:
        if not isinstance(item, dict):
            continue
        provider_module = _clean_module(str(item.get("module") or ""), root)
        if provider_module.startswith("src/contexts/"):
            providers.append({"module": "/" + provider_module, "export": str(item.get("export") or "default")})
    mocks = []
    for item in raw.get("mocks") or []:
        if isinstance(item, dict) and str(item.get("path") or "").strip():
            mocks.append(
                {
                    "method": str(item.get("method") or "GET").upper(),
                    "path": str(item.get("path")).strip(),
                    "status": int(item.get("status") or 200),
                    "json": item.get("json", {}),
                }
            )
    actions = [item for item in (raw.get("actions") or []) if isinstance(item, dict) and item.get("type")][:6]
    storage = raw.get("local_storage") if isinstance(raw.get("local_storage"), dict) else {}
    section = str(raw.get("section") or "").strip()
    feature = str(raw.get("feature") or "").strip()
    return {
        "id": _slug(str(raw.get("id") or ""), f"shot-{index + 1}"),
        "feature": feature if feature in features or not features else (features[0] if len(features) == 1 else feature),
        "module": "/" + module,
        "export": str(raw.get("export") or "default"),
        "props": raw.get("props") if isinstance(raw.get("props"), dict) else {},
        "noop_props": [name for name in (raw.get("noop_props") or []) if isinstance(name, str) and re.fullmatch(r"on[A-Z]\w{0,40}", name)][:6],
        "providers": providers,
        "mocks": mocks,
        "expect_text": [str(t) for t in (raw.get("expect_text") or []) if str(t).strip()][:3],
        "actions": actions,
        "crop": str(raw.get("crop") or "").strip(),
        "width": max(360, min(1440, int(raw.get("width") or 1100))),
        "local_storage": {str(k): str(v) for k, v in storage.items()},
        **_clean_route(raw),
        "section": section if section in SECTIONS else "Functional Overview",
        "caption": str(raw.get("caption") or "").strip()[:200],
        "shows": str(raw.get("shows") or "").strip()[:300],
    }


def plan_shots(features: list[dict], evidence: dict) -> tuple[list[dict], list[dict]]:
    root = ui_root()
    if not root or not evidence.get("files"):
        return [], []
    names = [str(item.get("name") or "") for item in features if isinstance(item, dict)]
    raw = chat_json(
        surface="release_shots",
        system=PLAN_PROMPT,
        payload={
            "features": [
                {k: item.get(k) for k in ("name", "what", "why", "modules", "evidence")}
                for item in features
                if isinstance(item, dict)
            ],
            "frontend": evidence["files"],
        },
        temperature=0.2,
        max_chars=60000,
        timeout=300,
        reasoning_effort="high",
    )
    shots, seen = [], set()
    for i, item in enumerate(raw.get("shots") or []):
        shot = clean_shot(item, root, i, names)
        if not shot or shot["id"] in seen:
            continue
        seen.add(shot["id"])
        shots.append(shot)
        if len(shots) >= MAX_SHOTS:
            break
    skipped = [item for item in (raw.get("skipped") or []) if isinstance(item, dict)][:8]
    return shots, skipped


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class HarnessServer:
    """Runs harness-server.mjs for the duration of a capture batch."""

    def __init__(self, ui: Path, *, timeout: float = 180.0):
        self.ui = ui
        self.timeout = timeout
        self.proc: subprocess.Popen | None = None
        self.lines: list[str] = []
        self.url = ""

    def __enter__(self) -> str:
        node = node_binary()
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        port = _free_port()
        env = {**os.environ, "PATH": f"{Path(node).parent}:{os.environ.get('PATH', '')}", "BROWSER": "none"}
        self.proc = subprocess.Popen(
            [node, str(HARNESS), "--ui", str(self.ui), "--cache", str(CACHE_DIR), "--port", str(port)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=env,
        )
        ready = threading.Event()

        def drain() -> None:
            for line in self.proc.stdout:  # type: ignore[union-attr]
                self.lines.append(line.rstrip())
                del self.lines[:-80]
                if line.startswith("READY "):
                    self.url = line.split(" ", 1)[1].strip()
                    ready.set()
            ready.set()

        spawn(drain, name="release-shots-vite")
        if not ready.wait(self.timeout) or not self.url:
            self.__exit__(None, None, None)
            raise RuntimeError("Screenshot harness did not start: " + " | ".join(self.lines[-6:]))
        return self.url

    def __exit__(self, *exc) -> None:
        if not self.proc:
            return
        try:
            self.proc.terminate()
            self.proc.wait(timeout=8)
        except Exception:
            self.proc.kill()
        self.proc = None


def _mock_for(mocks: list[dict], method: str, path: str) -> dict | None:
    tail = path[len("/v1") :] if path.startswith("/v1") else path
    for mock in mocks:
        if mock["method"] not in {method, "ANY"}:
            continue
        pattern = mock["path"].replace("{tenant}", "*").replace(":tenantId", "*").split("?")[0]
        if not pattern.startswith("/"):
            pattern = "/" + pattern
        if fnmatch.fnmatchcase(tail, pattern) or tail.endswith(pattern.lstrip("*")):
            return mock
    return None


def _init_script(shot: dict) -> str:
    storage = {
        "access_token": "release-shot",
        "refresh_token": "release-shot",
        "tenant_id": TENANT,
        "user": json.dumps({"id": 1, "name": "Demo Admin", "email": "admin@example.com", "tenant_id": TENANT, "role": "admin"}),
        **shot.get("local_storage", {}),
    }
    spec = {key: shot.get(key) for key in ("module", "export", "props", "noop_props", "providers", "width", "route", "route_path")}
    spec["padding"] = 16
    spec["background"] = "#ffffff"
    return (
        f"window.__RELEASE_SHOT__ = {json.dumps(spec)};"
        f"for (const [k, v] of Object.entries({json.dumps(storage)})) {{ try {{ localStorage.setItem(k, v) }} catch (e) {{}} }}"
    )


def _is_blank(png: Path) -> bool:
    from PIL import Image, ImageStat

    with Image.open(png) as image:
        stat = ImageStat.Stat(image.convert("L"))
    return stat.stddev[0] < 4


def _run_action(page, action: dict) -> None:
    kind = str(action.get("type") or "").lower()
    selector = str(action.get("selector") or "")
    target = page.locator(selector).first if selector else page.get_by_text(str(action.get("text") or ""), exact=False).first
    if kind == "click":
        target.click(timeout=5000)
    elif kind == "select":
        target.select_option(str(action.get("value") or ""), timeout=5000)
    elif kind == "hover":
        target.hover(timeout=5000)
    elif kind == "type":
        target.fill(str(action.get("value") or ""), timeout=5000)
    elif kind == "wait":
        page.wait_for_timeout(min(3000, int(action.get("ms") or 300)))
    page.wait_for_timeout(350)


def render_shot(context, base_url: str, shot: dict, out: Path, *, first: bool = False) -> dict:
    result = {k: shot[k] for k in ("id", "feature", "module", "section", "caption", "shows")}
    result.update({"status": "failed", "error": "", "unmatched": [], "console": []})
    page = context.new_page()
    unmatched: list[str] = []
    console: list[str] = []

    def route(route_obj) -> None:
        request = route_obj.request
        parsed = urlparse(request.url)
        if parsed.hostname in ALLOWED_HOSTS:
            return route_obj.continue_()
        if parsed.path.startswith("/v1/") or (parsed.hostname == "127.0.0.1" and parsed.path.startswith("/api/")):
            if request.method == "OPTIONS":
                return route_obj.fulfill(status=204, headers=CORS)
            mock = _mock_for(shot["mocks"], request.method, parsed.path)
            if mock:
                return route_obj.fulfill(status=mock["status"], headers=CORS, content_type="application/json", body=json.dumps(mock["json"]))
            unmatched.append(f"{request.method} {parsed.path}")
            return route_obj.fulfill(status=200, headers=CORS, content_type="application/json", body="{}")
        if parsed.hostname != "127.0.0.1":
            return route_obj.abort()
        return route_obj.continue_()

    page.on("console", lambda msg: console.append(msg.text[:300]) if msg.type == "error" else None)
    page.add_init_script(_init_script(shot))
    page.route("**/*", route)
    try:
        page.goto(f"{base_url}/tenant/{TENANT}/release-shot", wait_until="domcontentloaded", timeout=120000)
        page.wait_for_function("() => window.__SHOT_STATUS__", timeout=180000 if first else 60000)
        status = page.evaluate("() => window.__SHOT_STATUS__")
        if status.get("state") == "error":
            raise RuntimeError("Component failed to mount: " + status.get("detail", "")[:600])
        try:
            page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            pass
        for text in shot["expect_text"]:
            try:
                page.get_by_text(text, exact=False).first.wait_for(state="visible", timeout=12000)
            except Exception as exc:
                raise RuntimeError(f"Fixture data did not render: '{text}' is not visible") from exc
        for action in shot["actions"]:
            _run_action(page, action)
        page.evaluate("() => document.fonts.ready")
        page.wait_for_timeout(900)
        status = page.evaluate("() => window.__SHOT_STATUS__")
        if status.get("state") == "error":
            raise RuntimeError("Component crashed after render: " + status.get("detail", "")[:600])
        target = page.locator("#shot-root").locator(shot["crop"]).first if shot["crop"] else page.locator("#shot-stage")
        box = target.bounding_box()
        if not box or box["width"] < 120 or box["height"] < 40:
            raise RuntimeError("Rendered block is empty or too small to use")
        out.parent.mkdir(parents=True, exist_ok=True)
        target.screenshot(path=str(out), animations="disabled")
        if _is_blank(out):
            raise RuntimeError("Screenshot is blank")
        result.update(
            status="ok",
            path=to_stored(out),
            width=round(box["width"]),
            height=round(box["height"]),
            sha=hashlib.sha256(out.read_bytes()).hexdigest()[:16],
        )
    except Exception as exc:
        result["error"] = str(exc)[:600]
        try:
            result["visible_text"] = page.locator("#shot-root").inner_text(timeout=2000)[:1500]
            debug = out.with_name(out.stem + ".failed.png")
            page.locator("#shot-stage").screenshot(path=str(debug), timeout=5000)
            result["debug_path"] = str(debug)
        except Exception:
            pass
    finally:
        result["unmatched"] = list(dict.fromkeys(unmatched))[:12]
        result["console"] = console[:8]
        page.close()
    return result


def _image_payload(path: Path) -> dict:
    data = base64.b64encode(path.read_bytes()).decode()
    return {"url": f"data:image/png;base64,{data}", "data": data, "media_type": "image/png"}


def repair_shot(shot: dict, result: dict, evidence: dict, root: Path, features: list[str]) -> dict | None:
    source = next((f.get("source", "") for f in evidence.get("files") or [] if "/" + f.get("path", "") == shot["module"]), "")
    if not source:
        disk = root / shot["module"].lstrip("/")
        source = disk.read_text(errors="ignore")[:9000] if disk.is_file() else ""
    image = result.get("debug_path") or (str(from_stored(result["path"])) if result.get("path") else "")
    try:
        raw = chat_json(
            surface="release_shots",
            system=REPAIR_PROMPT,
            payload={
                "shot": {**shot, "module": shot["module"].lstrip("/")},
                "failure": result.get("error") or result.get("review") or "",
                "unmatched_requests": result.get("unmatched") or [],
                "console_errors": result.get("console") or [],
                "visible_text": result.get("visible_text") or "",
                "source": source,
            },
            temperature=0.2,
            max_chars=40000,
            timeout=240,
            images=[_image_payload(Path(image))] if image and Path(image).is_file() else None,
        )
    except LLMJsonError:
        log.exception("release shot repair failed for %s", shot["id"])
        return None
    fixed = clean_shot(raw.get("shot") or {}, root, 0, features) if isinstance(raw.get("shot"), dict) else None
    if fixed:
        fixed["id"] = shot["id"]
    return fixed


def review_shots(results: list[dict]) -> dict[str, str]:
    """Return {shot id: reason} for shots the visual review rejects."""
    ok = [item for item in results if item.get("status") == "ok" and item.get("path")]
    if not ok:
        return {}
    try:
        raw = chat_json(
            surface="release_shots",
            system=REVIEW_PROMPT,
            payload={"images_in_order": [{"id": item["id"], "caption": item["caption"], "shows": item["shows"]} for item in ok]},
            temperature=0,
            max_chars=8000,
            timeout=180,
            images=[_image_payload(from_stored(item["path"])) for item in ok[:4]],
        )
    except LLMJsonError:
        log.warning("release shot review unavailable; keeping rule-checked shots")
        return {}
    rejected = {}
    for review in raw.get("reviews") or []:
        if isinstance(review, dict) and review.get("ok") is False:
            rejected[str(review.get("id") or "")] = str(review.get("reason") or "Failed visual review")[:300]
    return rejected


def render_batch(
    shots: list[dict],
    out_dir: Path,
    *,
    evidence: dict | None = None,
    features: list[str] | None = None,
    repair: bool = True,
) -> list[dict]:
    from playwright.sync_api import sync_playwright

    root = ui_root()
    if not root:
        raise RuntimeError(readiness()["reason"])
    evidence = evidence or {"files": []}
    features = features or []
    out_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict] = []
    with HarnessServer(root) as base_url, sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1480, "height": 1000},
            device_scale_factor=DEVICE_SCALE,
            reduced_motion="reduce",
            locale="en-IN",
            timezone_id="Asia/Kolkata",
        )
        try:
            by_id = {shot["id"]: shot for shot in shots}
            for i, shot in enumerate(shots):
                results.append(render_shot(context, base_url, shot, out_dir / f"{shot['id']}.png", first=i == 0))
            for reason_id, reason in review_shots(results).items():
                for item in results:
                    if item["id"] == reason_id:
                        item.update(status="failed", review=reason, error=f"Visual review: {reason}")
            for i, item in enumerate(results):
                if not repair or item["status"] == "ok" or item["id"] not in by_id:
                    continue
                fixed = repair_shot(by_id[item["id"]], item, evidence, root, features)
                if not fixed:
                    continue
                retry = render_shot(context, base_url, fixed, out_dir / f"{fixed['id']}.png")
                if retry["status"] == "ok" and review_shots([retry]):
                    retry.update(status="failed", error="Visual review rejected the repaired shot")
                retry["repaired"] = True
                retry["first_failure"] = item.get("error") or ""
                results[i] = retry
        finally:
            context.close()
            browser.close()
    return results


def capture_release_shots(*, job_id: int, base_sha: str, head_sha: str, features: list[dict]) -> dict:
    """Plan, render and check screenshots for one release job. Never raises."""
    started = time.time()
    ready = readiness()
    if not ready["ok"]:
        return {"status": "skipped", "reason": ready["reason"], "shots": []}
    try:
        evidence = frontend_evidence(base_sha, head_sha)
        if not evidence.get("files"):
            return {"status": "skipped", "reason": "No product frontend files changed in this release.", "shots": []}
        shots, skipped = plan_shots(features, evidence)
        if not shots:
            return {"status": "skipped", "reason": "No screen in the frontend diff to capture.", "shots": [], "skipped": skipped}
        names = [str(item.get("name") or "") for item in features if isinstance(item, dict)]
        out_dir = SHOTS_ROOT / f"job-{job_id}"
        results = render_batch(shots, out_dir, evidence=evidence, features=names)
        ok = [item for item in results if item["status"] == "ok"]
        return {
            "status": "ok" if ok else "failed",
            "reason": "" if ok else "No screenshot rendered cleanly. See each shot's error.",
            "shots": results,
            "skipped": skipped,
            "specs": shots,
            "seconds": round(time.time() - started),
        }
    except LLMJsonError as exc:
        log.exception("release shot planning failed")
        return {"status": "failed", "reason": f"Screenshot planner unavailable: {exc}"[:300], "shots": []}
    except Exception as exc:
        log.exception("release shot capture failed")
        return {"status": "failed", "reason": str(exc)[:300], "shots": []}


def good_shots(capture: dict | None, features: list[str] | None = None) -> list[dict]:
    wanted = {name.strip() for name in features or [] if name and name.strip()}
    out = []
    for item in (capture or {}).get("shots") or []:
        if not isinstance(item, dict) or item.get("status") != "ok" or not item.get("path"):
            continue
        if not from_stored(item["path"]).is_file():
            continue
        if wanted and item.get("feature") and item["feature"] not in wanted:
            continue
        out.append(item)
    return out


def shot_catalog(shots: list[dict]) -> list[dict]:
    return [{k: item.get(k, "") for k in ("id", "feature", "section", "caption", "shows")} for item in shots]
