"""Named tasks a worker can run. Each takes (session, set_step, params) and returns a result dict.

Tasks run inside the run's workspace context, so `settings`, file paths and queries already point
at that workspace.
"""

from __future__ import annotations

from typing import Any, Callable

from sqlalchemy.orm import Session

StepFn = Callable[[str, dict], None]
TaskFn = Callable[[Session, StepFn, dict], Any]

TASKS: dict[str, TaskFn] = {}


def task(name: str) -> Callable[[TaskFn], TaskFn]:
    def register(fn: TaskFn) -> TaskFn:
        TASKS[name] = fn
        return fn

    return register


@task("refresh")
def daily_sync(db: Session, set_step: StepFn, params: dict) -> dict:
    from app.services.refresh import refresh_platform

    return refresh_platform(db, set_step=set_step)


def refresh_section(db: Session, set_step: StepFn, section: str) -> dict:
    from app.services.ingest import ingest_cliq, ingest_jira
    from app.services.time_window import briefing_window

    set_step(section, {"status": "running"})
    start, end = briefing_window().as_naive()
    result: dict = {"ok": True}
    if section == "jira":
        result["jira_count"] = ingest_jira(db, start)
        db.commit()
    elif section == "cliq":
        count, _relevant, error = ingest_cliq(db, start, end)
        db.commit()
        result.update(ok=not bool(error), cliq_count=count, error=error)
    elif section == "roadmap":
        from app.services.roadmap import sync_roadmap_statuses

        sync_roadmap_statuses(db, fetch_missing=True)
    elif section == "codebase":
        from app.services.codebase import git_status, latest_snapshot
        from app.services.profile import load_profile
        from app.services.source_index import build

        snapshot = latest_snapshot(db)
        branch = load_profile().get("data_branch") or (snapshot.branch if snapshot else "") or git_status().get("branch")
        result.update(build(branch))
    elif section == "competitors":
        from app.services.competitive import refresh_all

        news = refresh_all(db, include_ai=False)
        created = int(news.get("created") or 0)
        result.update(ok=True, count=created, created=created)
    else:
        from app.services.pipeline import run_pipeline

        run = run_pipeline(db, trigger="overview", ingest=False)
        result.update(ok=run.status == "completed", error=run.error)
    set_step(section, {**result, "status": "done"})
    return {"ok": result["ok"], "error": result.get("error", ""), "steps": {section: result}}


SECTIONS = ("jira", "cliq", "roadmap", "codebase", "overview", "competitors")
for _section in SECTIONS:
    TASKS[f"refresh-{_section}"] = (lambda name: lambda db, set_step, params: refresh_section(db, set_step, name))(_section)


@task("briefing")
def briefing(db: Session, set_step: StepFn, params: dict) -> dict:
    from app.services.pipeline import deliver_standup, email_standup, run_pipeline

    trigger = params.get("trigger") or "manual"
    set_step("briefing", {"status": "running"})
    run = run_pipeline(db, trigger="schedule" if trigger == "schedule" else "manual", ingest=bool(params.get("ingest", True)))
    ok = run.status == "completed"
    delivered: dict | None = None
    emailed: dict | None = None
    if ok and trigger == "schedule" and params.get("deliver_to_cliq"):
        delivered = deliver_standup(db)
    if ok and trigger == "schedule" and params.get("email_briefing"):
        emailed = email_standup(db)
    set_step("briefing", {"ok": ok, "status": "done", "run_id": run.id, "delivered": bool(delivered and delivered.get("ok")), "emailed": bool(emailed and emailed.get("ok"))})
    if not ok:
        raise RuntimeError(run.error or f"Briefing ended with status {run.status}")
    return {"ok": True, "run_id": run.id, "delivered": delivered, "emailed": emailed}


@task("index")
def codebase_index(db: Session, set_step: StepFn, params: dict) -> dict:
    from app.services.codebase import update_index

    branch = (params.get("branch") or "").strip() or None
    set_step("index", {"ok": True, "status": "running", "branch": branch or ""})
    result = update_index(db, pull=bool(params.get("pull", True)), branch=branch)
    set_step("index", {"ok": True, "status": "done", "branch": (result or {}).get("indexed_branch") or branch or ""})
    return {"ok": True, **(result or {})}


@task("source-index")
def source_index(db: Session, set_step: StepFn, params: dict) -> dict:
    from app.services.source_index import build

    branch = params.get("branch") or ""
    set_step("source", {"status": "running", "branch": branch})
    result = build(branch)
    set_step("source", {"ok": True, "status": "done", "count": result.get("file_count")})
    return {"ok": True, **result}


@task("release-detect")
def release_detect(db: Session, set_step: StepFn, params: dict) -> dict:
    from app.services.release_worker import detect_and_enqueue

    set_step("detect", {"status": "running"})
    jobs = detect_and_enqueue(db, triggered_by=params.get("trigger") or "manual")
    set_step("detect", {"ok": True, "status": "done", "count": len(jobs)})
    return {"ok": True, "queued": len(jobs), "jobs": jobs}


@task("release-job")
def release_job(db: Session, set_step: StepFn, params: dict) -> dict:
    from app.services.release_worker import run_job

    run_job(int(params["job_id"]), from_stage=params.get("from_stage") or None)
    return {"ok": True, "job_id": params["job_id"]}


@task("release-shots")
def release_shots(db: Session, set_step: StepFn, params: dict) -> dict:
    from app.services.release_worker import recapture_shots

    recapture_shots(int(params["job_id"]), params.get("checked"))
    return {"ok": True, "job_id": params["job_id"]}


@task("marketing-discovery")
def marketing_discovery(db: Session, set_step: StepFn, params: dict) -> dict:
    from app.services.marketing_manager import sync_released_features

    return sync_released_features(db, set_step)


@task("marketing")
def marketing_production(db: Session, set_step: StepFn, params: dict) -> dict:
    from app.services.marketing_manager import drain_queue

    return drain_queue(db, set_step)


@task("competitive_refresh")
def competitive_refresh(db: Session, set_step: StepFn, params: dict) -> dict:
    from app.services import competitive

    set_step("competitive", {"ok": True, "status": "running"})
    result = competitive.refresh_all(db, include_ai=False)
    created = int(result.get("created") or 0)
    set_step(
        "competitive",
        {
            "ok": True,
            "status": "done",
            "competitors": len(result.get("competitors") or []),
            "market": len(result.get("market") or []),
            "count": created,
            "created": created,
        },
    )
    return result


@task("repo-sync")
def repo_sync(db: Session, set_step: StepFn, params: dict) -> dict:
    from app.models import Repository
    from app.services import repos

    repo = db.get(Repository, int(params.get("repository_id") or 0)) if params.get("repository_id") else repos.current(db)
    if repo is None:
        return {"ok": False, "error": "Add a repository first."}
    set_step("fetch", {"status": "running", "repository": repo.name})
    fetched = repos.fetch(db, repo)
    set_step("fetch", {**{k: v for k, v in fetched.items() if k != "checkout"}, "status": "done"})
    checkout = fetched.get("checkout") or {}
    if checkout:
        set_step("checkout", {**checkout, "status": "done"})
    branches = repos.refresh_branch_cache(db, repo) if repos.git_dir(repo) else []
    set_step("branches", {"ok": True, "status": "done", "count": len(branches)})
    pruned = repos.prune_stale_worktrees(repo)
    return {
        "ok": bool(fetched.get("ok")),
        "error": fetched.get("error") or checkout.get("error") or "",
        "status": fetched.get("status"),
        "remote_blocked": bool(fetched.get("remote_blocked")),
        "branches": len(branches),
        "pruned_worktrees": pruned,
    }


@task("source-index-evict")
def source_index_evict(db: Session, set_step: StepFn, params: dict) -> dict:
    from app.services.source_index import evict

    return {"ok": True, **evict()}
