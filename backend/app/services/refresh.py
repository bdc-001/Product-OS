"""Refresh Jira, Cliq, and the indexed go_services branch in one pass."""

from __future__ import annotations

import logging
from collections.abc import Callable

from sqlalchemy.orm import Session

from app.services.codebase import (
    codebase_root,
    latest_snapshot,
    list_recent_branches,
    update_index,
)
from app.services.pipeline import run_pipeline
from app.services.roadmap import sync_roadmap_statuses

log = logging.getLogger(__name__)
StepFn = Callable[[str, dict], None]


def _step(ok: bool | None = None, **extra) -> dict:
    payload = dict(extra)
    if ok is not None:
        payload["ok"] = ok
    return payload


def refresh_platform(db: Session, set_step: StepFn | None = None) -> dict:
    steps: dict[str, dict] = {}

    def emit(name: str, payload: dict) -> None:
        steps[name] = payload
        if set_step:
            try:
                set_step(name, payload)
            except Exception:
                log.exception("job step update failed")

    emit("jira", _step(status="running"))
    emit("cliq", _step(status="running"))
    try:
        from app.services.workspace import apply_workspace

        apply_workspace()
    except Exception:
        log.exception("workspace overlay failed")
    try:
        run = run_pipeline(db, trigger="refresh", ingest=True)
        ok = run.status == "completed"
        cliq_error = ""
        if (run.error or "").lower().startswith("cliq:"):
            cliq_error = run.error.split(":", 1)[1].strip()
        jira_error = "" if ok else (run.error or "")
        emit(
            "jira",
            _step(
                ok,
                jira_count=run.jira_count,
                error=jira_error,
            ),
        )
        emit(
            "cliq",
            _step(
                ok and not cliq_error,
                cliq_count=run.cliq_count,
                error=cliq_error,
            ),
        )
        if not ok:
            log.warning("refresh pipeline failed: %s", run.error)
        elif cliq_error:
            log.warning("refresh cliq failed: %s", cliq_error)
        try:
            sync_roadmap_statuses(db, fetch_missing=True)
            emit("roadmap", _step(True))
        except Exception:
            log.exception("refresh roadmap statuses failed")
            emit("roadmap", _step(False, error="roadmap sync failed"))
    except Exception as exc:
        log.exception("refresh pipeline failed")
        emit("jira", _step(False, error=str(exc)))
        emit("cliq", _step(False, error=str(exc)))

    emit("codebase", _step(status="running"))
    try:
        root = codebase_root()
        snap = latest_snapshot(db)
        branch = (snap.branch or "").strip() if snap else ""
        if not root.is_dir():
            emit("codebase", _step(False, error=f"CODEBASE_PATH does not exist: {root}"))
        else:
            status = update_index(db, pull=True, branch=branch or None)
            pull_error = (status or {}).get("pull_error") or (status or {}).get("error") or ""
            pulled = bool((status or {}).get("pulled"))
            emit(
                "codebase",
                _step(
                    True,
                    branch=(status or {}).get("indexed_branch") or (status or {}).get("branch") or branch,
                    pulled=pulled,
                    already_up_to_date=bool((status or {}).get("already_up_to_date")),
                    stashed=bool((status or {}).get("stashed")),
                    error=pull_error,
                    remote_blocked=bool((status or {}).get("remote_blocked")),
                    clone_alert=(status or {}).get("clone_alert") or "",
                ),
            )
    except FileNotFoundError as exc:
        emit("codebase", _step(False, error=str(exc)))
    except Exception as exc:
        log.exception("refresh codebase failed")
        emit("codebase", _step(False, error=str(exc)))

    emit("branches", _step(status="running"))
    try:
        listed = list_recent_branches(fetch=True)
        error = listed.get("error") or ""
        emit(
            "branches",
            _step(
                not bool(error) or bool(listed.get("branches")),
                count=len(listed.get("branches") or []),
                error=error,
                remote_blocked=bool(listed.get("remote_blocked")),
            ),
        )
    except Exception as exc:
        log.exception("refresh branch list failed")
        emit("branches", _step(False, error=str(exc)))

    emit("releases", _step(status="running"))
    try:
        from app.services.release_worker import detect_and_enqueue

        queued = detect_and_enqueue(db, triggered_by="refresh")
        emit("releases", _step(True, count=len(queued)))
    except Exception as exc:
        log.exception("release detect failed")
        emit("releases", _step(False, error=str(exc)[:300]))

    emit("marketing", _step(status="running"))
    try:
        from app.services.marketing_manager import refresh_marketing
        emit("marketing", refresh_marketing(db, set_step=set_step))
    except Exception:
        db.rollback()
        log.exception("marketing release assessment failed")
        emit("marketing", _step(False, error="Marketing assessment needs a retry; saved work is preserved."))

    failed = [name for name, step in steps.items() if step.get("ok") is not True or step.get("error")]
    return {
        "ok": not failed,
        "error": "; ".join(f"{name}: {steps[name].get('error') or 'step failed'}" for name in failed),
        "steps": steps,
    }
