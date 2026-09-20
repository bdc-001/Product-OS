"""Detect release/YYYY-MM-DD merges into origin/main after git fetch."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from pathlib import Path

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import ROOT
from app.models import ReleaseJob
from app.services.codebase import _git, codebase_root
from app.services.time_window import now_local

log = logging.getLogger(__name__)

STATE = ROOT / "data" / "release_detect.json"
RELEASE_RE = re.compile(r"^release/\d{4}-\d{2}-\d{2}$")
# Bitbucket: "Merged in release/2026-07-29 (pull request #2631)"
# GitHub:    "Merge pull request #42 from release/2026-09-23"
BRANCH_IN_SUBJECT = re.compile(r"(?:^|\s)(?:Merged in|from)\s+(release/\d{4}-\d{2}-\d{2})(?![-\w])", re.I)
INTO_RELEASE = re.compile(r"\binto\s+release/\d{4}-\d{2}-\d{2}\b", re.I)
STALE_DAYS = 21
FUTURE_DAYS = 2


def _repo() -> Path:
    return codebase_root()


def branch_from_subject(subject: str) -> str:
    text = (subject or "").strip()
    if INTO_RELEASE.search(text) and not re.search(r"^Merged in release/", text, re.I):
        return ""
    match = BRANCH_IN_SUBJECT.search(text)
    if not match:
        return ""
    branch = match.group(1)
    return branch if RELEASE_RE.match(branch) else ""


def _parse_iso(raw: str) -> datetime | None:
    text = (raw or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def date_window_ok(branch: str, merged_at: str) -> tuple[bool, str]:
    day = branch.split("/", 1)[-1]
    try:
        cut = datetime.strptime(day, "%Y-%m-%d").date()
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
        if INTO_RELEASE.search(subject) and not re.search(r"^Merged in release/", subject, re.I):
            continue
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


def detect_release_merges(repo: Path | None = None, lookback: int = 30) -> list[dict] | None:
    root = Path(repo) if repo else _repo()
    if not root.is_dir():
        log.warning("release detect: codebase path missing")
        return None
    log_proc = _git(root, "log", "origin/main", "--merges", "--format=%H|%P|%cI|%s", f"-{lookback}", timeout=60)
    if log_proc.returncode != 0:
        log.warning("release detect: git log origin/main failed: %s", (log_proc.stderr or "")[:300])
        return None
    merges = parse_merge_log(log_proc.stdout)
    # Bitbucket second-parent fallback when subject is not "Merged in release/…"
    seen = {m["sha"] for m in merges}
    extra = _git(root, "log", "origin/main", "--merges", "--format=%H|%P|%cI|%s", f"-{lookback}", timeout=60)
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
        named = _git(root, "name-rev", "--name-only", "--refs=refs/remotes/origin/release/*", parent_list[1])
        name = (named.stdout or "").strip()
        name = name.replace("origin/", "").split("~")[0].split("^")[0]
        if not RELEASE_RE.match(name):
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
