"""The pipeline catalog: what each pipeline needs, how it runs, and where its output lives."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models import Connection, PipelineConfig, Repository, Run

REPOSITORY = "repository"


@dataclass(frozen=True)
class SettingField:
    key: str
    label: str
    kind: str = "text"  # text | number | bool | select | textarea
    default: Any = ""
    help: str = ""
    options: tuple[str, ...] = ()


@dataclass(frozen=True)
class Pipeline:
    id: str
    name: str
    category: str  # product | marketing | knowledge | system
    description: str
    output: str
    requires: tuple[str, ...] = ()
    optional: tuple[str, ...] = ()
    task: str = ""
    schedule: str = ""
    settings: tuple[SettingField, ...] = ()
    steps: tuple[str, ...] = ()
    icon: str = "bolt"
    interactive: bool = False
    chain: tuple[str, ...] = field(default=())

    @property
    def runnable(self) -> bool:
        return bool(self.task)


CATALOG: tuple[Pipeline, ...] = (
    Pipeline(
        id="daily-sync",
        name="Daily sync",
        category="system",
        description="Runs every connected source in order: Jira, Cliq, roadmap, repositories, releases, market watch and feature discovery.",
        output="/week",
        optional=("jira", "cliq", "llm", REPOSITORY, "google"),
        task="refresh",
        schedule="0 8 * * *",
        steps=("jira", "cliq", "roadmap", "codebase", "branches", "releases", "competitors", "marketing"),
        icon="sync",
        chain=("jira-sync", "cliq-sync", "roadmap", "codebase", "release-notes", "market-watch", "feature-discovery"),
    ),
    Pipeline(
        id="jira-sync",
        name="Jira sync",
        category="product",
        description="Pull tickets, epics and changelogs for your projects into the board.",
        output="/jira",
        requires=("jira",),
        task="refresh-jira",
        steps=("jira",),
        icon="jira",
    ),
    Pipeline(
        id="cliq-sync",
        name="Cliq sync",
        category="product",
        description="Read recent chats you are in and link messages to tickets.",
        output="/cliq",
        requires=("cliq",),
        task="refresh-cliq",
        steps=("cliq",),
        icon="chat",
    ),
    Pipeline(
        id="briefing",
        name="Weekly briefing",
        category="product",
        description="Turn this week's tickets and chats into a prioritised briefing with actions.",
        output="/week",
        requires=("jira",),
        optional=("cliq", "llm"),
        task="briefing",
        schedule="0 9 * * 1-5",
        settings=(
            SettingField("deliver_to_cliq", "Post to Cliq after a scheduled run", "bool", False),
            SettingField("email_briefing", "Email it after a scheduled run", "bool", False, help="Sent to the release-notes address on the SMTP connection."),
            SettingField("ingest", "Ingest Jira and Cliq first", "bool", True),
        ),
        steps=("briefing",),
        icon="briefing",
    ),
    Pipeline(
        id="roadmap",
        name="Roadmap",
        category="product",
        description="Keep the quarterly roadmap in step with Jira epic and ticket statuses.",
        output="/roadmap",
        requires=("jira",),
        optional=("llm",),
        task="refresh-roadmap",
        steps=("roadmap",),
        icon="roadmap",
    ),
    Pipeline(
        id="codebase",
        name="Codebase sync and index",
        category="product",
        description="Fetch the repository mirror, check out the product branch and map its modules for search and Q&A.",
        output="/codebase",
        requires=(REPOSITORY,),
        optional=("llm",),
        task="index",
        settings=(SettingField("pull", "Fetch from the remote first", "bool", True),),
        steps=("fetch", "index", "source-index"),
        icon="code",
    ),
    Pipeline(
        id="release-notes",
        name="Release notes",
        category="product",
        description="Detect merged release branches, extract features, capture screenshots and draft notes for approval.",
        output="/releases",
        requires=(REPOSITORY,),
        optional=("llm", "google", "smtp"),
        task="release-detect",
        schedule="0 10 * * *",
        steps=("detect",),
        icon="release",
    ),
    Pipeline(
        id="prd",
        name="PRD",
        category="product",
        description="Draft product requirement documents grounded in tickets and the codebase.",
        output="/prd",
        requires=("llm",),
        optional=("jira", REPOSITORY),
        interactive=True,
        icon="doc",
    ),
    Pipeline(
        id="prototypes",
        name="Prototypes",
        category="product",
        description="Chat a clickable prototype into existence on your workspace's UI kit.",
        output="/prototype",
        requires=("llm",),
        interactive=True,
        icon="prototype",
    ),
    Pipeline(
        id="copilot",
        name="Copilot",
        category="product",
        description="Plan Jira changes in plain language. Nothing is written until you approve.",
        output="/jira",
        requires=("jira", "llm"),
        interactive=True,
        icon="copilot",
    ),
    Pipeline(
        id="feature-discovery",
        name="Feature discovery",
        category="marketing",
        description="Find shipped, buyer-facing features and add them to the marketing mastersheet and Sheet.",
        output="/marketing",
        requires=("llm", REPOSITORY),
        optional=("google",),
        task="marketing-discovery",
        steps=("marketing",),
        icon="discover",
    ),
    Pipeline(
        id="campaigns",
        name="Campaign production",
        category="marketing",
        description="Produce posts, articles, one-pagers and films for each feature you start.",
        output="/marketing",
        requires=("llm",),
        optional=("google", "cartesia"),
        task="marketing",
        steps=("marketing",),
        icon="campaign",
    ),
    Pipeline(
        id="launch-films",
        name="Launch films",
        category="marketing",
        description="Rendered product films with narration, built from a campaign.",
        output="/marketing",
        requires=("llm", "cartesia"),
        interactive=True,
        icon="film",
    ),
    Pipeline(
        id="avatar-videos",
        name="Avatar videos",
        category="marketing",
        description="Presenter videos from your own photo avatar and cloned voice.",
        output="/avatar",
        requires=("heygen",),
        optional=("cartesia", "elevenlabs", "llm"),
        interactive=True,
        icon="avatar",
    ),
    Pipeline(
        id="artifacts",
        name="Artifacts",
        category="marketing",
        description="One-pagers, battlecards and how-to PDFs for a feature.",
        output="/artifacts",
        requires=("llm",),
        optional=("google",),
        interactive=True,
        icon="artifact",
    ),
    Pipeline(
        id="comms",
        name="Comms",
        category="marketing",
        description="Internal updates, client release notes and newsletters from a release.",
        output="/comms",
        requires=("llm",),
        optional=("smtp", "google"),
        interactive=True,
        icon="comms",
    ),
    Pipeline(
        id="market-watch",
        name="Competitor and market watch",
        category="marketing",
        description="Track competitor changelogs, blogs, pricing pages and industry news.",
        output="/competitors",
        optional=("llm",),
        task="competitive_refresh",
        steps=("competitors",),
        icon="radar",
    ),
    Pipeline(
        id="notes",
        name="Notes",
        category="knowledge",
        description="Daily notes and learnings, exportable as PDF.",
        output="/notes",
        interactive=True,
        icon="notes",
    ),
    Pipeline(
        id="library",
        name="Library",
        category="knowledge",
        description="Upload PDFs and documents, then search and annotate them.",
        output="/lms",
        interactive=True,
        icon="library",
    ),
)

BY_ID: dict[str, Pipeline] = {p.id: p for p in CATALOG}
TASK_PIPELINE: dict[str, str] = {p.task: p.id for p in CATALOG if p.task}
CATEGORY_LABELS = {"system": "Automation", "product": "Product", "marketing": "Marketing", "knowledge": "Knowledge"}


def get_pipeline(pipeline_id: str) -> Pipeline:
    pipeline = BY_ID.get(pipeline_id)
    if pipeline is None:
        raise KeyError(pipeline_id)
    return pipeline


def default_settings(pipeline: Pipeline) -> dict:
    return {f.key: f.default for f in pipeline.settings}


def seed_pipeline_configs(db: Session, *, enable_schedules: tuple[str, ...] = ()) -> None:
    existing = {row.pipeline_id for row in db.query(PipelineConfig).all()}
    for pipeline in CATALOG:
        if pipeline.id in existing:
            continue
        db.add(
            PipelineConfig(
                pipeline_id=pipeline.id,
                enabled=True,
                schedule=pipeline.schedule,
                schedule_enabled=pipeline.id in enable_schedules,
                settings=default_settings(pipeline),
            )
        )
    db.flush()


def config_for(db: Session, pipeline: Pipeline) -> PipelineConfig:
    row = db.query(PipelineConfig).filter(PipelineConfig.pipeline_id == pipeline.id).one_or_none()
    if row is None:
        row = PipelineConfig(pipeline_id=pipeline.id, enabled=True, schedule=pipeline.schedule, schedule_enabled=False, settings=default_settings(pipeline))
        db.add(row)
        db.flush()
    return row


def connection_states(db: Session) -> dict[str, str]:
    states = {
        row.provider: row.status
        for row in db.query(Connection).filter(Connection.name == "default").all()
        if row.status != "incomplete"
    }
    if db.query(Repository.id).first():
        states[REPOSITORY] = "connected"
    return states


def readiness(pipeline: Pipeline, states: dict[str, str]) -> dict:
    missing = [req for req in pipeline.requires if req not in states]
    failing = [req for req in pipeline.requires if states.get(req) == "error"]
    optional_missing = [opt for opt in pipeline.optional if opt not in states]
    if missing:
        status = "needs_connection"
    elif failing:
        status = "connection_error"
    else:
        status = "ready"
    return {"status": status, "missing": missing, "failing": failing, "optional_missing": optional_missing}


def _run_brief(run: Run | None) -> dict | None:
    if run is None:
        return None
    return {
        "id": run.id,
        "status": run.status,
        "trigger": run.trigger,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "error": (run.error or "")[:300],
    }


def catalog(db: Session) -> list[dict]:
    states = connection_states(db)
    configs = {row.pipeline_id: row for row in db.query(PipelineConfig).all()}
    out = []
    for pipeline in CATALOG:
        latest = (
            db.query(Run).filter(Run.pipeline_id == pipeline.id).order_by(Run.id.desc()).first()
            if pipeline.task
            else None
        )
        ready = readiness(pipeline, states)
        status = ready["status"]
        if latest and latest.status in {"queued", "running"} and status == "ready":
            status = latest.status
        config = configs.get(pipeline.id)
        out.append(
            {
                "id": pipeline.id,
                "name": pipeline.name,
                "category": pipeline.category,
                "category_label": CATEGORY_LABELS[pipeline.category],
                "description": pipeline.description,
                "output": pipeline.output,
                "icon": pipeline.icon,
                "requires": list(pipeline.requires),
                "optional": list(pipeline.optional),
                "runnable": pipeline.runnable,
                "interactive": pipeline.interactive,
                "status": status,
                "readiness": ready,
                "steps": list(pipeline.steps),
                "chain": list(pipeline.chain),
                "settings_schema": [f.__dict__ | {"options": list(f.options)} for f in pipeline.settings],
                "settings": {**default_settings(pipeline), **((config.settings if config else {}) or {})},
                "enabled": bool(config.enabled) if config else True,
                "schedule": (config.schedule if config else pipeline.schedule) or "",
                "default_schedule": pipeline.schedule,
                "schedule_enabled": bool(config.schedule_enabled) if config else False,
                "last_fired_at": config.last_fired_at.isoformat() if config and config.last_fired_at else None,
                "last_run": _run_brief(latest),
            }
        )
    return out


def touch_config(row: PipelineConfig) -> None:
    row.updated_at = datetime.utcnow()


class PipelineNotReady(Exception):
    def __init__(self, message: str, readiness: dict | None = None) -> None:
        super().__init__(message)
        self.readiness = readiness or {}


def start_pipeline(
    db: Session,
    pipeline_id: str,
    *,
    trigger: str = "manual",
    params: dict | None = None,
    started_by: str = "",
    inline: bool = False,
) -> Run:
    """Queue a run for the worker, or with `inline` lease it to this process and start it now."""
    from app.pipelines.tasks import TASKS
    from app.services.jobs import enqueue

    pipeline = get_pipeline(pipeline_id)
    if not pipeline.task:
        raise PipelineNotReady(f"{pipeline.name} runs from its page.")
    ready = readiness(pipeline, connection_states(db))
    if ready["status"] == "needs_connection":
        raise PipelineNotReady("Connect " + ", ".join(ready["missing"]) + " first.", ready)
    config = config_for(db, pipeline)
    if not config.enabled:
        raise PipelineNotReady(f"{pipeline.name} is turned off for this workspace.", ready)
    merged = {**default_settings(pipeline), **(config.settings or {}), **(params or {})}
    work = None
    if inline:
        fn, run_params = TASKS[pipeline.task], {**merged, "trigger": trigger}
        work = lambda session, set_step: fn(session, set_step, run_params)  # noqa: E731
    return enqueue(
        db,
        pipeline.task,
        work,
        task=pipeline.task,
        params=merged,
        pipeline_id=pipeline.id,
        trigger=trigger,
        started_by=started_by,
        max_attempts=3 if trigger == "schedule" and not inline else 1,
    )
