"""One release note per shipped feature, in the workspace's release-note format.

Every note is a Drive copy of the template doc, so the header logo and the Release Note /
module dropdown chips carry over (the Docs API cannot create dropdown chips). Only the title
text and everything below the title line are rewritten: dek, 📌 sections of lead: text
bullets, framed product screenshots, conceptual diagrams, divider, sign-off.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import shutil
from collections import Counter
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageOps

from app.clients.llm import LLMJsonError, chat_json
from app.config import ROOT, settings
from app.services import repos
from app.services.codebase import _git, codebase_root
from app.services.gdocs import DocBuilder, _docs, _docs_batch, _drive, pt, rgb_color, trash_file, utf16_len
from app.services.gdrive import ensure_year_folder, explain_drive_error
from app.services.pdf_notes import drive_doc_name, write_release_pdf
from app.services.prompts import with_preamble
from app.storage import WorkspaceDir, from_stored, to_stored

log = logging.getLogger(__name__)

STATIC = Path(__file__).resolve().parents[1] / "static" / "artifacts"
EXAMPLE = json.loads((STATIC / "release-note-example.json").read_text())
RULES_FILE = ROOT / ".cursor" / "rules" / "activate-release-notes.mdc"
ASSETS_ROOT = WorkspaceDir("release_notes", "assets")

FONT = "Nunito"
LINK = "1155CC"
CONTENT_WIDTH_PT = 510.0
FIGURE_WIDTH_PT = 492.75
MAX_SHOT_HEIGHT_PT = 280.0
PX_TO_PT = 0.75
FRAME_PAD_PX = 12
FRAME_BORDER_PX = 1
DEVICE_SCALE = 2
MAX_SECTIONS = 8
MAX_FIGURES = 2

FALLBACK_RULES = """Decide what someone needs to know about the release, explain the non-obvious behaviour
precisely, and let the UI explain the rest. Write as a PM to CSMs/operators. Open with 1-2 sentences:
what shipped, what visibility it gives, where it lives. Noun headings, not "How to...". Bold concept
first, then 1-2 sentences. One idea per bullet. Keep formulas, thresholds, status transitions,
exclusions, and scope rules. Omit observable UI trivia. One Note: for a real exception. End on why it
matters operationally. Factual tone; no marketing fluff. Never invent behaviour."""

STOP = {
    "with", "that", "this", "from", "into", "when", "they", "their", "them", "have", "will", "been", "were",
    "what", "which", "your", "each", "only", "also", "more", "than", "then", "there", "about", "after",
    "before", "does", "without", "users", "user", "feature", "features", "shipped", "release", "now",
    "can", "new", "adds", "added", "support", "supports", "allow", "allows",
    "service", "services", "screen", "page", "view", "shows", "show", "able", "used", "uses", "using",
}
SKIP_PATH = re.compile(
    r"(^|/)(vendor|node_modules|dist|build|__snapshots__|mocks?|fixtures?|testdata)/"
    r"|_test\.go$|\.test\.|\.spec\.|\.stories\.|\.lock$|package-lock\.json$|go\.sum$|\.pb\.go$"
    r"|\.(png|jpe?g|gif|svg|ico|woff2?|ttf|pdf|mp4)$",
    re.I,
)
CODE_EXT = (".go", ".py", ".js", ".jsx", ".ts", ".tsx", ".sql", ".proto", ".yaml", ".yml", ".json")


def _rules() -> str:
    try:
        text = RULES_FILE.read_text()
    except OSError:
        return FALLBACK_RULES
    if text.startswith("---"):
        text = text.split("---", 2)[-1]
    return text.strip() or FALLBACK_RULES


def support_email() -> str:
    from app.services.profile import load_profile

    return (load_profile().get("support_email") or "").strip()


def _cta_line(support: str) -> str:
    return f" For any issue related to the feature, raise it to {support}." if support else ""


def _example(support: str) -> dict:
    base = re.sub(r"\s*For any issue related to the feature, raise it to \S+\.$", "", EXAMPLE.get("cta") or "")
    return {**EXAMPLE, "cta": base + _cta_line(support)}


def note_prompt() -> str:
    support = support_email()
    cta_rule = (
        f"- cta ends with the {support} sentence exactly as shown."
        if support
        else "- cta is one sentence on the operational value. Do not invent a support contact."
    )
    return with_preamble(
        "You write one [[company]] release note for one shipped feature, in [[pm]]'s release-note format.\n"
        "The note goes into a Google Doc whose title line already carries the [[company]] logo and the\n"
        "Release Note / [[module]] dropdowns. You write the title text and everything below it.\n\n"
        "Style contract (follow it exactly):\n"
        f"{_rules()}\n\n"
        "Worked example. This is a published note the PM approved; match its depth, voice, structure,\n"
        "bullet length and precision. Its product facts belong to Campaign Schedule only:\n"
        f"{json.dumps(_example(support), ensure_ascii=False)}\n\n"
        + """Input payload:
- feature: name, what, why, modules, evidence from the release extraction.
- commits: subjects and bodies of the commits that built this feature.
- files: plan/handoff docs and source at the release head (models, services, handlers, UI).
- screenshots: real captures rendered from the shipped frontend: id, caption, shows. May be empty.

Return JSON with exactly the example's shape:
{"feature": "<feature name>",
 "module": "<product area the feature lives in, e.g. Campaigns, Analytics, Agents>",
 "title": "<feature name as operators know it, nothing appended>",
 "dek": "<1-2 sentences: what shipped, what it gives, where it lives>",
 "sections": [
   {"heading": "📌 <Noun heading>",
    "items": [{"lead": "<bold concept>", "text": "<1-2 sentences>"},
              {"lead": "Note", "text": "<one real exception>", "note": true}],
    "screenshot": {"id": "<id from screenshots>", "caption": "<one sentence on what the image shows>"},
    "figure": {"kind": "flow|comparison", "heading": "<short>", "caption": "Conceptual ...",
               "items": [{"lead": "<1-2 words>", "text": "<under 45 characters>"}]}}],
 "cta": "This feature is an effort towards <operational value>.__CTA__"}

Rules:
- Every behaviour, label, threshold and status must trace to the commits or files. Never invent UI
  labels or numbers. If the evidence does not say it, leave it out.
- First section is "📌 Navigation": one item without a lead saying where the feature is opened.
  It renders as a plain paragraph, so write it as one or two full sentences.
- 3 to 7 sections. Headings are nouns for the concept (Filters, Overall Metrics, Go-live), never "How to".
- Items: lead is the concept; text is 1-2 sentences. Items without a lead only in Navigation.
  At most one "note": true item per section, and only for a real exception.
- screenshot: optional per section; only ids from payload screenshots, each at most once, beside the
  section it explains. Rewrite its caption to state what the image shows in this note's words.
- figure: optional, at most 2 in the note, only for a relationship the UI does not show (a lifecycle,
  a sequence across time, a rule that behaves differently in two cases). flow = 2-4 items in order;
  comparison = exactly 2 items. Leads 1-3 words, texts under 45 characters. Captions start with
  "Conceptual workflow:" or "Conceptual comparison:".
- No engineering vocabulary (API, cron, worker, table names, flags, migrations, PR numbers).
__CTA_RULE__
""".replace("__CTA__", _cta_line(support)).replace("__CTA_RULE__", cta_rule)
    )


def _git_out(repo: Path, *args: str) -> str:
    proc = _git(repo, *args, timeout=90, exclusive=False)
    return proc.stdout if proc.returncode == 0 else ""


def _words(text: str) -> set[str]:
    spaced = re.sub(r"([a-z])([A-Z])", r"\1 \2", text or "")
    return {w for w in re.findall(r"[a-z][a-z0-9]+", spaced.lower()) if len(w) >= 4 and w not in STOP}


def _keywords(feature: dict) -> set[str]:
    parts = [feature.get(k) or "" for k in ("name", "what", "why", "evidence")]
    parts += [str(m) for m in feature.get("modules") or []]
    return _words(" ".join(parts))


def _commits(repo: Path, spec: str) -> list[dict]:
    raw = _git_out(repo, "log", spec, "--no-merges", "--format=%x1e%h%x1f%s%x1f%b%x1f", "--name-only", "-400")
    out = []
    for chunk in raw.split("\x1e")[1:]:
        parts = chunk.split("\x1f")
        if len(parts) < 4:
            continue
        files = [line.strip() for line in parts[3].splitlines() if line.strip()]
        out.append({"sha": parts[0].strip(), "subject": parts[1].strip(), "body": parts[2].strip(), "files": files})
    return out


def _score(commit: dict, keywords: set[str], phrase: str) -> int:
    subject = commit["subject"].lower()
    score = 10 if phrase and phrase in subject else 0
    score += 3 * len(_words(commit["subject"]) & keywords)
    score += min(6, len(_words(commit["body"][:3000]) & keywords))
    score += min(6, len(_words(" ".join(commit["files"])) & keywords))
    return score


def feature_evidence(base_sha: str, head_sha: str, feature: dict, budget: int = 60000) -> dict:
    """Commits, plan docs and head source for one feature, ranked by overlap with its extraction."""
    repo = codebase_root()
    if not base_sha or not head_sha:
        return {"commits": [], "files": []}
    spec = f"{base_sha}..{head_sha}"
    keywords = _keywords(feature)
    phrase = (feature.get("name") or "").strip().lower()
    scored = sorted(((_score(c, keywords, phrase), c) for c in _commits(repo, spec)), key=lambda pair: -pair[0])
    best = scored[0][0] if scored else 0
    picked = [c for s, c in scored if s >= max(3, best * 0.35)][:30] or [c for s, c in scored if s > 0][:10]
    counts: Counter[str] = Counter(path for c in picked for path in c["files"] if not SKIP_PATH.search(path))
    docs = [p for p, _ in counts.most_common() if p.lower().endswith(".md")]
    code = [p for p, _ in counts.most_common() if p.lower().endswith(CODE_EXT)]
    commits = [{"subject": c["subject"], "body": c["body"][:1500]} for c in picked[:25]]
    used = len(json.dumps(commits))
    files = []
    for path, limit in [*((p, 8000) for p in docs[:4]), *((p, 5000) for p in code[:14])]:
        if used >= budget:
            break
        source = _git_out(repo, "show", f"{head_sha}:{path}")
        if not source.strip():
            continue
        entry = {"path": path, "source": source[: min(limit, budget - used)]}
        if not path.lower().endswith(".md"):
            entry["diff"] = _git_out(repo, "diff", spec, "--", path)[:1500]
        used += len(entry["source"]) + len(entry.get("diff", ""))
        files.append(entry)
    return {"commits": commits, "files": files}


def curated_evidence(head_sha: str, commits: list[str], paths: list, budget: int = 75000) -> dict:
    """Evidence from hand-picked commits (oldest first) and files, for notes scoped by an operator.

    A path is a string (head source) or {"path", "limit", "commit", "lines"}; with "commit" the
    entry is that commit's diff of the file, and "lines" [start, end] keeps only that 1-based
    range of the head source, for large files where only part matters.
    """
    repo = codebase_root()
    out_commits = []
    for sha in commits:
        subject, _, body = _git_out(repo, "show", "-s", "--format=%s%x1f%b", sha).partition("\x1f")
        if subject.strip():
            out_commits.append({"subject": subject.strip(), "body": body.strip()[:1500]})
    used = len(json.dumps(out_commits))
    files = []
    for item in paths:
        spec = {"path": item} if isinstance(item, str) else dict(item)
        path, limit = spec["path"], int(spec.get("limit") or 8000)
        if used >= budget:
            break
        if spec.get("commit"):
            text = _git_out(repo, "show", "--format=", spec["commit"], "--", path)
            key = "diff"
        else:
            text = _git_out(repo, "show", f"{head_sha}:{path}")
            key = "source"
            if spec.get("lines"):
                start, end = spec["lines"]
                text = "\n".join(text.splitlines()[max(0, start - 1) : end])
        if not text.strip():
            continue
        entry = {"path": path, key: text[: min(limit, budget - used)]}
        if spec.get("lines"):
            entry["lines"] = spec["lines"]
        used += len(entry[key])
        files.append(entry)
    return {"commits": out_commits, "files": files}


SELECT_PROMPT = with_preamble(
    """You pick the source material a release-note writer needs for one [[product]] feature.
Input: the feature (name, description, modules), candidate docs (path, title), candidate code
files ranked by how often feature-related commits touched them, and those commit subjects.

Pick only material about THIS feature: its PRD/plan/design docs, the models and services that
implement its behaviour, the handlers that expose it, and the UI components an operator uses.
Skip generic infrastructure, other features and tests. Paths must be copied from the input.

Return JSON: {"docs": ["<path>", ...up to 5], "files": ["<path>", ...up to 12],
 "ui": ["<static/src component path from files that shows the feature>", ...up to 4],
 "found": true|false}
"found" is false when nothing in the input implements the feature.
"""
)
BULK_COMMIT_FILES = 80


def _scope() -> str:
    """The product's path scope as a git pathspec; "." is the whole repository."""
    return repos.scope_root() or "."


def ui_component(path: str) -> bool:
    root = (settings.repo_ui_path or "").strip().strip("/")
    return path.startswith(f"{root}/src/") if root else "/src/" in f"/{path}"


def activate_history(limit: int = 3000) -> list[dict]:
    """Recent product-scope commits with their files; load once per batch."""
    repo = codebase_root()
    raw = _git_out(repo, "log", "HEAD", f"-{limit}", "--no-merges", "--format=%x1e%h%x1f%s%x1f%b%x1f", "--name-only", "--", _scope())
    out = []
    for chunk in raw.split("\x1e")[1:]:
        parts = chunk.split("\x1f")
        if len(parts) < 4:
            continue
        files = [line.strip() for line in parts[3].splitlines() if line.strip()]
        if len(files) > BULK_COMMIT_FILES:
            continue
        out.append({"sha": parts[0].strip(), "subject": parts[1].strip(), "body": parts[2].strip(), "files": files})
    return out


def doc_catalog() -> list[dict]:
    """Markdown docs in the product scope (docs/, prd/, plans) with title and word set."""
    repo = codebase_root()
    out = []
    for path in _git_out(repo, "ls-files", "--", f"{_scope()}/*.md").splitlines():
        if SKIP_PATH.search(path) or "/node_modules/" in path:
            continue
        disk = repo / path
        try:
            text = disk.read_text(errors="ignore")
        except OSError:
            continue
        title = next((line.lstrip("# ").strip() for line in text.splitlines() if line.startswith("#")), "")
        out.append({"path": path, "title": title[:120], "words": _words(text[:20000]), "size": len(text)})
    return out


def _tracked_code() -> tuple[str, ...]:
    return _tracked_code_in(str(codebase_root()), _scope())


@lru_cache(maxsize=8)
def _tracked_code_in(root: str, scope: str) -> tuple[str, ...]:
    paths = _git_out(Path(root), "ls-files", "--", scope).splitlines()
    return tuple(p for p in paths if p.lower().endswith(CODE_EXT) and not SKIP_PATH.search(p))


def _name_matches(name: str, limit: int = 40) -> list[str]:
    """Code named after the feature, or mentioning it in snake/camel case, regardless of commit age."""
    words = _words(name)
    if not words:
        return []
    need = min(2, len(words))
    by_path = []
    for path in _tracked_code():
        hit = len(_words(" ".join(path.split("/")[-2:]).replace("_", " ")) & words)
        if hit >= need:
            by_path.append((-hit, path.endswith(".sql"), path))
    tokens = [t for t in re.findall(r"[a-z0-9]+", name.lower()) if t not in STOP][:3]
    variants = set()
    for n in range(len(tokens), 1, -1):
        part = tokens[:n]
        variants |= {"_".join(part), "".join(part), part[0] + "".join(t.title() for t in part[1:])}
    grep = []
    if variants:
        out = _git_out(codebase_root(), "grep", "-c", "-I", "-i", "-E", "|".join(sorted(variants)), "--", _scope())
        for line in out.splitlines():
            path, _, count = line.rpartition(":")
            if path.lower().endswith(CODE_EXT) and not SKIP_PATH.search(path) and count.isdigit():
                grep.append((-int(count), path))
    ordered = [p for *_, p in sorted(by_path)] + [p for _, p in sorted(grep)]
    return list(dict.fromkeys(ordered))[:limit]


def capability_evidence(feature: dict, history: list[dict], docs: list[dict], budget: int = 60000) -> dict:
    """Evidence for a feature as it exists today (no release diff): docs, code, commits, UI paths."""
    repo = codebase_root()
    keywords = _keywords(feature)
    phrase = (feature.get("name") or "").strip().lower()
    hinted = [p for item in feature.get("evidence_paths") or [] for p in ([item] if isinstance(item, str) else [])]

    def doc_score(doc: dict) -> int:
        score = 3 * len(_words(doc["path"]) & keywords) + 3 * len(_words(doc["title"]) & keywords)
        score += min(12, len(doc["words"] & keywords))
        return score + (8 if phrase and phrase in doc["title"].lower() else 0)

    ranked_docs = sorted(docs, key=lambda d: -doc_score(d))[:30]
    scored = sorted(((_score(c, keywords, phrase), c) for c in history), key=lambda pair: -pair[0])
    best = scored[0][0] if scored else 0
    top = [c for s, c in scored if s >= max(3, best * 0.4)][:60]
    counts: Counter[str] = Counter(p for c in top for p in c["files"] if p.lower().endswith(CODE_EXT) and not SKIP_PATH.search(p))
    named = _name_matches(feature.get("name") or "")
    candidates = list(dict.fromkeys([*hinted, *named, *(p for p, _ in counts.most_common(50))]))[:90]
    try:
        picked = chat_json(
            surface="release_evidence",
            system=SELECT_PROMPT,
            payload={
                "feature": {k: feature.get(k) for k in ("name", "what", "why", "modules")},
                "docs": [{"path": d["path"], "title": d["title"]} for d in ranked_docs],
                "files": candidates,
                "commits": [c["subject"] for c in top[:40]],
            },
            temperature=0.1,
            max_chars=40000,
            timeout=240,
        )
    except Exception:
        log.exception("evidence selection failed for %s", feature.get("name"))
        picked = {"docs": [d["path"] for d in ranked_docs[:3]], "files": candidates[:10], "ui": [], "found": bool(candidates)}
    known_docs = {d["path"] for d in ranked_docs}
    known_files = set(candidates)
    doc_paths = [p for p in picked.get("docs") or [] if p in known_docs][:5]
    file_paths = [p for p in picked.get("files") or [] if p in known_files][:12]
    ui_paths = [p for p in picked.get("ui") or [] if p in known_files and ui_component(p)][:4]
    chosen = set(file_paths) | set(doc_paths)
    commits = [c for c in top if chosen & set(c["files"])][:20] or top[:10]
    out_commits = [{"subject": c["subject"], "body": c["body"][:1500]} for c in commits]
    used = len(json.dumps(out_commits))
    files = []
    for path, limit in [*((p, 9000) for p in doc_paths), *((p, 5000) for p in file_paths)]:
        if used >= budget:
            break
        try:
            source = (repo / path).read_text(errors="ignore")
        except OSError:
            continue
        if not source.strip():
            continue
        entry = {"path": path, "source": source[: min(limit, budget - used)]}
        used += len(entry["source"])
        files.append(entry)
    return {
        "commits": out_commits,
        "files": files,
        "ui_paths": ui_paths,
        "found": bool(picked.get("found", True)) and bool(files),
    }


def _text(value, limit: int) -> str:
    return " ".join(str(value or "").split())[:limit]


def _items(raw, first: bool) -> list[dict]:
    items = []
    notes = 0
    for item in raw or []:
        if isinstance(item, str):
            item = {"text": item}
        if not isinstance(item, dict):
            continue
        lead = _text(item.get("lead"), 60).rstrip(":")
        text = _text(item.get("text"), 600)
        if not text:
            continue
        note = bool(item.get("note")) or lead.lower() == "note"
        if note:
            notes += 1
            if notes > 1:
                continue
            lead = "Note"
        if not lead and not first:
            continue
        row = {"lead": lead, "text": text} if lead else {"text": text}
        if note:
            row["note"] = True
        items.append(row)
    return items[:8]


def _figure(raw) -> dict | None:
    if not isinstance(raw, dict):
        return None
    kind = "comparison" if raw.get("kind") == "comparison" else "flow"
    items = [
        {"lead": _text(i.get("lead"), 28), "text": _text(i.get("text"), 60)}
        for i in raw.get("items") or []
        if isinstance(i, dict) and _text(i.get("lead"), 28)
    ]
    items = items[:2] if kind == "comparison" else items[:4]
    heading = _text(raw.get("heading"), 70)
    if len(items) < 2 or not heading:
        return None
    caption = _text(raw.get("caption"), 300) or f"Conceptual {'workflow' if kind == 'flow' else 'comparison'}: {heading}."
    return {"kind": kind, "heading": heading, "caption": caption, "items": items}


def clean_note(raw: dict, feature: dict, shots: list[dict]) -> dict:
    name = _text(feature.get("name"), 120) or _text((raw or {}).get("feature"), 120) or "Release"
    by_id = {str(s.get("id")): s for s in shots if s.get("id")}
    used: set[str] = set()
    figures = 0
    sections = []
    for index, section in enumerate(((raw or {}).get("sections") or [])[:MAX_SECTIONS]):
        if not isinstance(section, dict):
            continue
        heading = _text(section.get("heading"), 80).lstrip("📌").strip()
        items = _items(section.get("items"), first=not sections)
        if not heading or not items:
            continue
        out = {"heading": f"📌 {heading}", "items": items}
        shot = section.get("screenshot")
        shot_id = str(shot.get("id") if isinstance(shot, dict) else shot or "")
        if shot_id in by_id and shot_id not in used:
            used.add(shot_id)
            caption = _text(shot.get("caption") if isinstance(shot, dict) else "", 300)
            out["screenshot"] = {"id": shot_id, "caption": caption or _text(by_id[shot_id].get("caption"), 300)}
        figure = _figure(section.get("figure"))
        if figure and figures < MAX_FIGURES:
            figures += 1
            out["figure"] = figure
        sections.append(out)
    for shot_id, shot in by_id.items():
        if shot_id in used:
            continue
        spare = next((s for s in sections[1:] if "screenshot" not in s), None)
        if spare:
            spare["screenshot"] = {"id": shot_id, "caption": _text(shot.get("caption"), 300)}
    module = _text((raw or {}).get("module"), 60) or _text((feature.get("modules") or [""])[0], 60)
    title = _text((raw or {}).get("title"), 140) or name
    cta = _text((raw or {}).get("cta"), 600)
    support = support_email()
    if support and support not in cta:
        cta = (cta.rstrip(". ") + "." if cta else "") + _cta_line(support)
        cta = cta.strip()
    return {
        "feature": name,
        "module": module,
        "title": title,
        "dek": _text((raw or {}).get("dek"), 700) or _text(feature.get("what"), 400),
        "sections": sections,
        "cta": cta,
    }


def fallback_note(feature: dict) -> dict:
    """Extraction-only draft when the writer is unavailable; flagged for a rewrite in review."""
    items = [{"lead": "What changed", "text": _text(feature.get("what"), 400)}]
    if feature.get("why"):
        items.append({"lead": "Why it matters", "text": _text(feature.get("why"), 400)})
    raw = {"sections": [{"heading": "What shipped", "items": items}]}
    return clean_note(raw, feature, [])


def generate_note(feature: dict, evidence: dict, shots: list[dict]) -> tuple[dict, str]:
    """Returns (note, error). A failed writer returns the extraction-only fallback and the reason."""
    payload = {
        "feature": {k: feature.get(k) for k in ("name", "what", "why", "modules", "evidence")},
        "screenshots": [{k: s.get(k, "") for k in ("id", "caption", "shows")} for s in shots],
        **evidence,
    }
    try:
        raw = chat_json(
            surface="comms_doc",
            system=note_prompt(),
            payload=payload,
            temperature=0.3,
            max_chars=90000,
            timeout=420,
            reasoning_effort="high",
        )
    except LLMJsonError as exc:
        log.exception("release note writer failed for %s", feature.get("name"))
        return fallback_note(feature), f"Writer unavailable: {exc}"[:300]
    except Exception as exc:
        log.exception("release note writer failed for %s", feature.get("name"))
        return fallback_note(feature), str(exc)[:300]
    note = clean_note(raw, feature, shots)
    if len(note["sections"]) < 2:
        return fallback_note(feature), "Writer returned no usable sections."
    return note, ""


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (text or "note").lower()).strip("-")[:60] or "note"


def _sha(path: Path) -> str:
    return hashlib.sha1(path.read_bytes()).hexdigest()[:16]


def frame_shot(src: Path, out: Path) -> dict:
    """White padding plus the 1pt blue outline the reference doc puts on product screenshots."""
    out.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(src) as image:
        padded = ImageOps.expand(image.convert("RGB"), border=FRAME_PAD_PX * DEVICE_SCALE, fill="white")
        framed = ImageOps.expand(padded, border=FRAME_BORDER_PX * DEVICE_SCALE, fill="#" + LINK)
        framed.save(out)
        width, height = framed.size
    return {"width": width // DEVICE_SCALE, "height": height // DEVICE_SCALE}


def _render_figure(figure: dict, out: Path) -> dict:
    from app.services.marketing_manual import render_manual_figures

    work = out.parent / f".{out.stem}"
    work.mkdir(parents=True, exist_ok=True)
    try:
        render_manual_figures({"figures": [figure]}, work)
        shutil.move(str(work / "release_notes-figure-01.png"), out)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    with Image.open(out) as image:
        return {"width": image.width, "height": image.height}


def prepare_images(note: dict, shots: list[dict], folder: Path, previous: list[dict] | None = None) -> list[dict]:
    """Frame screenshots and render figures for one note. Keeps Drive URIs for unchanged files."""
    folder.mkdir(parents=True, exist_ok=True)
    by_id = {str(s.get("id")): s for s in shots}
    old = {item.get("key"): item for item in previous or [] if isinstance(item, dict)}
    images = []
    for index, section in enumerate(note.get("sections") or []):
        shot = section.get("screenshot")
        if shot and shot["id"] in by_id and by_id[shot["id"]].get("path"):
            src = from_stored(by_id[shot["id"]]["path"])
            key = f"shot:{shot['id']}"
            out = folder / f"{slug(shot['id'])}.png"
            try:
                size = frame_shot(src, out)
                images.append({"key": key, "section": index, "kind": "shot", "path": to_stored(out),
                               "caption": shot["caption"], **size, "sha": _sha(out)})
            except Exception:
                log.exception("could not frame %s", src)
        figure = section.get("figure")
        if figure:
            key = f"figure:{index}"
            out = folder / f"figure-{index + 1}.png"
            try:
                size = _render_figure(figure, out)
                images.append({"key": key, "section": index, "kind": "figure", "path": to_stored(out),
                               "caption": figure["caption"], **size, "sha": _sha(out)})
            except Exception:
                log.exception("figure %s does not fit; leaving it out", figure.get("heading"))
                section.pop("figure", None)
    for item in images:
        prior = old.get(item["key"])
        if prior and prior.get("sha") == item["sha"] and prior.get("uri"):
            item.update({k: prior[k] for k in ("uri", "drive_file_id") if prior.get(k)})
    return images


def image_size_pt(item: dict) -> tuple[float, float]:
    width_px = float(item.get("width") or 1)
    height_px = float(item.get("height") or 1)
    if item.get("kind") == "figure":
        return FIGURE_WIDTH_PT, FIGURE_WIDTH_PT * height_px / width_px
    width = min(CONTENT_WIDTH_PT, width_px * PX_TO_PT)
    height = width * height_px / width_px
    if height > MAX_SHOT_HEIGHT_PT:
        width, height = width * MAX_SHOT_HEIGHT_PT / height, MAX_SHOT_HEIGHT_PT
    return width, height


def note_markdown(note: dict) -> str:
    lines = [f"# {note.get('title') or note.get('feature')}", "", note.get("dek") or "", ""]
    for section in note.get("sections") or []:
        lines.append(f"## {section['heading']}")
        for item in section["items"]:
            lines.append(f"- {item['lead']}: {item['text']}" if item.get("lead") else f"- {item['text']}")
        lines.append("")
    lines += ["_" * 60, note.get("cta") or ""]
    return "\n".join(lines)


def write_note_pdf(note: dict, images: list[dict], dest: Path, *, branch: str, sha: str, date_str: str, version: str) -> Path:
    """Local preview PDF for review when Drive is off; the approved PDF is the Doc export."""
    sections = note.get("sections") or []
    placed = [
        {**item, "path": str(from_stored(item["path"])), "section": sections[item["section"]]["heading"]}
        for item in images
        if item.get("section", -1) < len(sections)
    ]
    return write_release_pdf(
        title=note.get("title") or note.get("feature") or "Release note",
        branch=branch,
        sha=sha,
        body="\n".join(note_markdown(note).splitlines()[1:]),
        dest=dest,
        date_str=date_str,
        audience="Clients",
        version=version,
        images=placed,
    )


def _run(b: DocBuilder, start: int, end: int, *, bold: bool = False, italic: bool = False, size: float | None = None,
         weight: int = 400, fg: str | None = None, link: str | None = None) -> None:
    if end <= start:
        return
    style: dict = {"weightedFontFamily": {"fontFamily": FONT, "weight": weight}, "bold": bold, "italic": italic}
    fields = ["weightedFontFamily", "bold", "italic"]
    if size:
        style["fontSize"] = pt(size)
        fields.append("fontSize")
    if fg:
        style["foregroundColor"] = rgb_color(fg)
        fields.append("foregroundColor")
    if link:
        style["link"] = {"url": link}
        fields.append("link")
    b.requests.append({"updateTextStyle": {"range": {"startIndex": start, "endIndex": end}, "textStyle": style, "fields": ",".join(fields)}})


def _para(b: DocBuilder, text: str, *, spacing: float = 8, named: str = "NORMAL_TEXT", **run) -> tuple[int, int]:
    s, e = b.line(text)
    b.clear_bullets(s, e + 1)
    b.para_style(s, e + 1, named=named, spacing=spacing, align="START")
    _run(b, s, e, **run)
    return s, e


def _bullets(b: DocBuilder, items: list[dict]) -> None:
    start = end = None
    for item in items:
        lead = (item.get("lead") or "").strip()
        text = (item.get("text") or "").strip()
        s, e = b.line(f"{lead}: {text}" if lead else text)
        b.para_style(s, e + 1, named="NORMAL_TEXT", spacing=4, align="START")
        if item.get("note"):
            _run(b, s, e, bold=True, italic=True)
        elif lead:
            colon = s + utf16_len(lead) + 1
            _run(b, s, colon, bold=True)
            _run(b, colon, e)
        else:
            _run(b, s, e)
        start = s if start is None else start
        end = e + 1
    if start is not None:
        b.bullet(start, end, "BULLET_DISC_CIRCLE_SQUARE")
    _para(b, "", spacing=0)


def _paragraphs(b: DocBuilder, items: list[dict]) -> None:
    for item in items:
        _para(b, item["text"], spacing=10)


def _keep_with_next(b: DocBuilder, start: int, end: int) -> None:
    b.requests.append({"updateParagraphStyle": {
        "range": {"startIndex": start, "endIndex": end},
        "paragraphStyle": {"keepWithNext": True},
        "fields": "keepWithNext",
    }})


def _image(b: DocBuilder, item: dict) -> tuple[int, int]:
    """Writes the image and its caption; returns the range covering both paragraphs."""
    width, height = image_size_pt(item)
    align = "CENTER" if item.get("kind") == "shot" else "START"
    img_s, _ = b.image(item["uri"], width, height)
    _, nl_e = b.text("\n")
    b.clear_bullets(img_s, nl_e)
    b.para_style(img_s, nl_e, named="NORMAL_TEXT", align=align, spacing=6)
    s, e = b.line(item.get("caption") or "")
    b.clear_bullets(s, e + 1)
    b.para_style(s, e + 1, named="NORMAL_TEXT", spacing=12, align=align)
    _run(b, s, e, size=9)
    return img_s, e + 1


def _title_paragraph(doc: dict) -> dict:
    for element in doc["body"]["content"]:
        if (element.get("paragraph") or {}).get("paragraphStyle", {}).get("namedStyleType") == "TITLE":
            return element
    raise RuntimeError("Template has no TITLE paragraph; the logo/chips layout changed.")


def reset_to_template_header(doc_id: str, title: str) -> int:
    """Swap the title text, drop everything after the title line, return the insertion index."""
    doc = _docs().documents().get(documentId=doc_id).execute()
    para = _title_paragraph(doc)
    first = para["paragraph"]["elements"][0]
    old = (first.get("textRun") or {}).get("content", "").split("\x0b")[0]
    if not old:
        raise RuntimeError("Template title line does not start with text.")
    start = int(first["startIndex"])
    body_end = int(doc["body"]["content"][-1]["endIndex"])
    requests = []
    if int(para["endIndex"]) < body_end - 1:
        requests.append({"deleteContentRange": {"range": {"startIndex": int(para["endIndex"]), "endIndex": body_end - 1}}})
    requests += [
        {"deleteContentRange": {"range": {"startIndex": start, "endIndex": start + utf16_len(old)}}},
        {"insertText": {"location": {"index": start}, "text": title}},
    ]
    _docs_batch(doc_id, requests)
    doc = _docs().documents().get(documentId=doc_id).execute()
    return int(_title_paragraph(doc)["endIndex"])


def write_body(doc_id: str, start: int, note: dict, images: list[dict]) -> None:
    b = DocBuilder(doc_id)
    b.index = start
    _para(b, note["dek"], spacing=10)
    tail = None
    for index, section in enumerate(note["sections"]):
        s, e = b.line(section["heading"])
        b.clear_bullets(s, e + 1)
        b.para_style(s, e + 1, named="HEADING_1", spacing=10, align="START")
        b.requests.append({"updateTextStyle": {
            "range": {"startIndex": s, "endIndex": e},
            "textStyle": {"weightedFontFamily": {"fontFamily": FONT, "weight": 400}},
            "fields": "weightedFontFamily,bold,italic,fontSize,foregroundColor",
        }})
        if any(item.get("lead") for item in section["items"]):
            _bullets(b, section["items"])
        else:
            _paragraphs(b, section["items"])
        tail = None
        for kind in ("shot", "figure"):
            for item in images:
                if item["section"] == index and item["kind"] == kind and item.get("uri"):
                    tail = _image(b, item)
    if tail:
        _keep_with_next(b, *tail)
    rule_s, rule_e = _para(b, "_" * 91, spacing=8)
    _keep_with_next(b, rule_s, rule_e + 1)
    cta = note["cta"]
    s, _ = _para(b, cta, spacing=8, italic=True, weight=300)
    support = support_email()
    if support and support in cta:
        at = s + utf16_len(cta.rsplit(support, 1)[0])
        _run(b, at, at + utf16_len(support), italic=True, weight=300, fg=LINK, link=f"mailto:{support}")
    b.commit()


def notes_folder(drive, feature: str) -> str:
    """Marketing root / <Feature> / Release notes, next to the feature's other artifacts."""
    from app.services.marketing import drive_root

    root = drive_root()
    if not root:
        raise RuntimeError("Set the Marketing Drive root in the Google connection before publishing release notes.")
    feature_folder = ensure_year_folder(drive, root, _text(feature, 100) or "Release")
    return ensure_year_folder(drive, feature_folder, "Release notes")


def _alive(drive, doc_id: str) -> bool:
    try:
        meta = drive.files().get(fileId=doc_id, fields="id, trashed", supportsAllDrives=True).execute()
    except Exception:
        return False
    return not meta.get("trashed")


def copy_template(drive, parent: str, name: str) -> str:
    template = (settings.release_note_template_doc_id or "").strip()
    if not template:
        raise RuntimeError("Set the release-note template Doc ID in the Google connection.")
    try:
        copied = drive.files().copy(
            fileId=template, body={"name": name, "parents": [parent]}, fields="id", supportsAllDrives=True
        ).execute()
    except Exception as exc:
        raise explain_drive_error(exc) from exc
    return copied["id"]


def publish_note(note: dict, images: list[dict], doc_id: str = "", *, folder: str = "", name: str = "") -> tuple[str, str]:
    """Write the note into its Doc. Reuses `doc_id` so the review link stays stable across regenerates."""
    drive = _drive()
    name = name or drive_doc_name(note["feature"])
    fresh = False
    if not doc_id or doc_id == "dryrun" or not _alive(drive, doc_id):
        doc_id = copy_template(drive, folder or notes_folder(drive, note["feature"]), name)
        fresh = True
    try:
        start = reset_to_template_header(doc_id, note["title"])
    except RuntimeError:
        if fresh:
            raise
        log.warning("release note %s lost its template header; recopying", doc_id)
        trash_file(doc_id)
        doc_id = copy_template(drive, folder or notes_folder(drive, note["feature"]), name)
        start = reset_to_template_header(doc_id, note["title"])
    write_body(doc_id, start, note, images)
    return doc_id, f"https://docs.google.com/document/d/{doc_id}/edit"


def verify_note(doc_id: str, note: dict, image_count: int) -> list[str]:
    """Problems found in the exported Doc: chips, header logo, copy, image count. Empty when clean."""
    import fitz

    drive = _drive()
    problems = []
    text = drive.files().export_media(fileId=doc_id, mimeType="text/plain").execute(num_retries=2).decode("utf-8")
    flat = " ".join(text.split())
    from app.services.profile import product_modules

    module = product_modules()[0]
    if "Release Note" not in flat or module not in flat:
        problems.append(f"Release Note / {module} chips are missing from the title line.")
    expected = [note["title"], note["dek"], note["cta"]]
    for section in note["sections"]:
        expected.append(section["heading"])
        expected += [f"{i['lead']}: {i['text']}" if i.get("lead") else i["text"] for i in section["items"]]
    missing = [part for part in expected if " ".join(part.split()) not in flat]
    if missing:
        problems.append("Missing copy: " + "; ".join(missing[:3]))
    doc = _docs().documents().get(documentId=doc_id).execute()
    if not any(el.get("inlineObjectElement") for h in doc.get("headers", {}).values()
               for c in h["content"] for el in (c.get("paragraph") or {}).get("elements", [])):
        problems.append("Header logo is missing.")
    pdf = drive.files().export_media(fileId=doc_id, mimeType="application/pdf").execute(num_retries=2)
    with fitz.open(stream=pdf, filetype="pdf") as document:
        found = {image[0] for page in document for image in page.get_images()}
    if len(found) < image_count + 1:
        problems.append(f"PDF export has {len(found)} images; expected {image_count} plus the logo.")
    return problems
