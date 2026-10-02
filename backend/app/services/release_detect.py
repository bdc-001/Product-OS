"""Detect release-branch merges into the repository's default branch after git fetch."""

from __future__ import annotations

import json
import logging
import re
import subprocess
from datetime import datetime
from pathlib import Path

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.models import ReleaseJob
from app.services import repos
from app.services.codebase import _git, codebase_root, detect_base_branch
from app.services.time_window import now_local
from app.storage import WorkspaceDir

log = logging.getLogger(__name__)

STATE = WorkspaceDir("release_detect.json")
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
STALE_DAYS = 21
FUTURE_DAYS = 2


def _repo() -> Path:
    return codebase_root()


def release_re() -> re.Pattern[str]:
    """The workspace's release-branch pattern, e.g. `release/YYYY-MM-DD`."""
    return repos.release_regex()


def _pattern_has_date() -> bool:
    return "YYYY" in (settings.repo_release_pattern or "release/YYYY-MM-DD")


def _release_glob() -> str:
    raw = (settings.repo_release_pattern or "release/YYYY-MM-DD").strip() or "release/YYYY-MM-DD"
    for token in ("YYYY", "MM", "DD"):
        raw = raw.replace(token, "*")
    return re.sub(r"\*+", "*", raw)


def _subject_re() -> re.Pattern[str]:
    # Bitbucket "Merged in release/…", GitHub "Merge pull request #42 from [owner/]release/…",
    # GitLab "Merge branch 'release/…' into 'main'".
    fragment = repos.release_fragment()
    return re.compile(rf"(?:^|\s)(?:Merged in|from|Merge branch)\s+'?(?:[^\s/']+/)?({fragment})(?![-\w])", re.I)


def _into_release(text: str) -> bool:
    """Feature branches merged *into* a release branch are not releases."""
    fragment = repos.release_fragment()
    if not re.search(rf"\binto\s+'?{fragment}(?![-\w])", text, re.I):
        return False
    return not re.search(rf"^Merged in {fragment}", text, re.I)


def base_ref(root: Path) -> str:
    return detect_base_branch(root) or repos.default_base_ref() or "origin/main"


def branch_from_subject(subject: str) -> str:
    text = (subject or "").strip()
    if _into_release(text):
        return ""
    match = _subject_re().search(text)
    if not match:
        return ""
    branch = match.group(1)
    return branch if release_re().match(branch) else ""


def _parse_iso(raw: str) -> datetime | None:
    text = (raw or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def date_window_ok(branch: str, merged_at: str) -> tuple[bool, str]:
    found = DATE_RE.search(branch.split("/", 1)[-1])
    if not found:
        return (False, "branch date is not YYYY-MM-DD") if _pattern_has_date() else (True, "")
    try:
        cut = datetime.strptime(found.group(0), "%Y-%m-%d").date()
    except ValueError:
        return False, "branch date is not YYYY-MM-DD"
    when = _parse_iso(merged_at)
    if not when:
        return True, ""
    merged = when.date()
    delta = (merged - cut).days
    if delta > STALE_DAYS:
        return False, f"stale: branch {cut} merged {merged} (>{STALE_DAYS} days later)"
    if delta < -FUTURE_DAYS:
        return False, f"merged {merged} is before branch date {cut}"
    if abs(delta) > 2:
        log.info("release %s merged %s days from cut date %s — still accepted", branch, delta, cut)
    return True, ""


def parse_merge_log(text: str) -> list[dict]:
    merges = []
    for line in (text or "").splitlines():
        parts = line.split("|", 3)
        if len(parts) != 4:
            continue
        sha, parents, date, subject = parts
        branch = branch_from_subject(subject)
        if not branch:
            continue
        ok, reason = date_window_ok(branch, date)
        if not ok:
            log.info("skip release merge %s %s: %s", branch, sha[:12], reason)
            continue
        parent_list = [p for p in (parents or "").split() if p]
        merges.append(
            {
                "sha": sha.strip(),
                "branch": branch,
                "merged_at": date.strip(),
                "base_sha": parent_list[0] if parent_list else "",
                "parents": parent_list,
            }
        )
    return merges


def detect_release_merges(repo: Path | None = None, lookback: int = 30, *, read_only: bool = False) -> list[dict] | None:
    root = Path(repo) if repo else _repo()
    if not root.is_dir():
        log.warning("release detect: codebase path missing")
        return None
    # Immutable git reads for the release view must not wait behind an indexing/LLM lock.
    def git_read(*args, timeout=60):
        if not read_only:
            return _git(root, *args, timeout=timeout)
        # Do not use _git's timeout cleanup: viewing history must never delete git locks.
        try:
            return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, timeout=min(timeout, 15))
        except subprocess.TimeoutExpired:
            return subprocess.CompletedProcess(args, 124, "", "Release history read timed out")

    base = base_ref(root)
    log_proc = git_read("log", base, "--merges", "--format=%H|%P|%cI|%s", f"-{lookback}")
    if log_proc.returncode != 0:
        log.warning("release detect: git log %s failed: %s", base, (log_proc.stderr or "")[:300])
        return None
    merges = parse_merge_log(log_proc.stdout)
    # Second-parent fallback when the subject does not name the release branch.
    seen = {m["sha"] for m in merges}
    extra = log_proc
    named_parents = {}
    refs = f"--refs=refs/remotes/origin/{_release_glob()}"
    release_pattern = release_re()
    if read_only:
        parents_to_name = []
        for line in extra.stdout.splitlines():
            parts = line.split("|", 3)
            if len(parts) == 4 and parts[0] not in seen and len(parts[1].split()) >= 2:
                parents_to_name.append(parts[1].split()[1])
        parents_to_name = list(dict.fromkeys(parents_to_name))
        if parents_to_name:
            names = git_read("name-rev", "--name-only", refs, *parents_to_name)
            if names.returncode == 0:
                named_parents = dict(zip(parents_to_name, names.stdout.splitlines()))
    for line in extra.stdout.splitlines():
        parts = line.split("|", 3)
        if len(parts) != 4:
            continue
        sha, parents, date, subject = parts
        if sha in seen:
            continue
        parent_list = [p for p in (parents or "").split() if p]
        if len(parent_list) < 2:
            continue
        if read_only:
            name = named_parents.get(parent_list[1], "").strip()
        else:
            named = git_read("name-rev", "--name-only", refs, parent_list[1])
            name = (named.stdout or "").strip()
        name = name.replace("remotes/origin/", "").replace("origin/", "").split("~")[0].split("^")[0]
        if not release_pattern.match(name):
            continue
        ok, reason = date_window_ok(name, date)
        if not ok:
            log.info("skip named release %s %s: %s", name, sha[:12], reason)
            continue
        merges.append(
            {
                "sha": sha.strip(),
                "branch": name,
                "merged_at": date.strip(),
                "base_sha": parent_list[0],
                "parents": parent_list,
            }
        )
        seen.add(sha)
    return merges


def _load_state() -> dict:
    if not STATE.is_file():
        return {}
    try:
        data = json.loads(STATE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def _save_state(seen: set[str]) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps({"seen_shas": sorted(seen)}), encoding="utf-8")


def new_release_merges(db: Session, repo: Path | None = None) -> list[dict]:
    """Diff against last-seen shas. First run (no state and no jobs) = baseline, no jobs."""
    merges = detect_release_merges(repo)
    if merges is None:
        return []
    state = _load_state()
    db_shas = {row.sha for row in db.query(ReleaseJob.sha).all()}
    if not state and not db_shas:
        _save_state({m["sha"] for m in merges})
        log.info("release detect: baseline %s merge shas, no jobs", len(merges))
        return []
    seen = set(state.get("seen_shas") or []) | db_shas
    fresh = [m for m in merges if m["sha"] not in seen]
    if fresh:
        _save_state(seen | {m["sha"] for m in fresh})
    elif seen - set(state.get("seen_shas") or []):
        _save_state(seen)
    return fresh


def enqueue_detected(db: Session, merges: list[dict], triggered_by: str = "auto") -> list[ReleaseJob]:
    created: list[ReleaseJob] = []
    for item in merges:
        row = ReleaseJob(
            branch=item["branch"],
            sha=item["sha"],
            base_sha=item.get("base_sha") or "",
            merged_at=item.get("merged_at") or "",
            status="detected",
            triggered_by=triggered_by,
            created_at=now_local().replace(tzinfo=None),
            updated_at=now_local().replace(tzinfo=None),
        )
        db.add(row)
        try:
            db.commit()
            db.refresh(row)
            created.append(row)
        except IntegrityError:
            db.rollback()
            log.info("release job already exists for %s %s", item.get("branch"), (item.get("sha") or "")[:12])
    return created
