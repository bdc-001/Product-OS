from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class MarketingFeature(Base):
    __tablename__ = "marketing_features"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(180))
    identity: Mapped[str] = mapped_column(String(180), unique=True)
    description: Mapped[str] = mapped_column(Text, default="")
    summary: Mapped[str] = mapped_column(String(280), default="")
    audience: Mapped[str] = mapped_column(String(500), default="")
    benefit: Mapped[str] = mapped_column(Text, default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="draft")
    source: Mapped[str] = mapped_column(String(32), default="manual")
    evidence: Mapped[list] = mapped_column(JSON, default=list)
    decision: Mapped[dict] = mapped_column(JSON, default=dict)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    # Video roadmap / mastersheet columns (editable in UI)
    module: Mapped[str] = mapped_column(String(120), default="")
    priority: Mapped[str] = mapped_column(String(16), default="")
    hook: Mapped[str] = mapped_column(Text, default="")
    start_date: Mapped[str] = mapped_column(String(32), default="")
    end_date: Mapped[str] = mapped_column(String(32), default="")
    sheet_status: Mapped[str] = mapped_column(String(64), default="Not started")
    script: Mapped[str] = mapped_column(Text, default="")
    video: Mapped[str] = mapped_column(Text, default="")
    tag: Mapped[str] = mapped_column(String(64), default="New")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class MarketingScan(Base):
    __tablename__ = "marketing_scans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    fingerprint: Mapped[str] = mapped_column(String(64), unique=True)
    branch: Mapped[str] = mapped_column(String(128), default="")
    source_sha: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class MarketingCampaign(Base):
    __tablename__ = "marketing_campaigns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_key: Mapped[str | None] = mapped_column(String(200), unique=True, nullable=True)
    feature_id: Mapped[int] = mapped_column(Integer, index=True)
    feature_revision: Mapped[int] = mapped_column(Integer)
    feature_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(32), default="generating")
    content: Mapped[dict] = mapped_column(JSON, default=dict)
    assets: Mapped[list] = mapped_column(JSON, default=list)
    drive_folder_id: Mapped[str] = mapped_column(String(160), default="")
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class JiraIssue(Base):
    __tablename__ = "jira_issues"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    issue_key: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    jira_id: Mapped[str] = mapped_column(String(32), default="")
    summary: Mapped[str] = mapped_column(String(512), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(64), default="")
    status_category: Mapped[str] = mapped_column(String(32), default="")
    priority: Mapped[str] = mapped_column(String(32), default="")
    issue_type: Mapped[str] = mapped_column(String(64), default="")
    assignee: Mapped[str] = mapped_column(String(128), default="")
    assignee_id: Mapped[str] = mapped_column(String(64), default="")
    creator: Mapped[str] = mapped_column(String(128), default="")
    labels: Mapped[str] = mapped_column(String(512), default="")
    created_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    due_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    comments_json: Mapped[list] = mapped_column(JSON, default=list)
    changelog_json: Mapped[list] = mapped_column(JSON, default=list)
    extra_json: Mapped[dict] = mapped_column(JSON, default=dict)
    url: Mapped[str] = mapped_column(String(512), default="")
    ingested_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)


class CliqChat(Base):
    __tablename__ = "cliq_chats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chat_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(256), default="")
    chat_type: Mapped[str] = mapped_column(String(64), default="")
    last_modified: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    raw: Mapped[dict] = mapped_column(JSON, default=dict)


class CliqMessage(Base):
    __tablename__ = "cliq_messages"
    __table_args__ = (UniqueConstraint("chat_id", "message_id", name="uq_cliq_msg"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chat_id: Mapped[str] = mapped_column(String(128), index=True)
    chat_name: Mapped[str] = mapped_column(String(256), default="")
    message_id: Mapped[str] = mapped_column(String(128), default="")
    thread_id: Mapped[str] = mapped_column(String(128), default="")
    sender: Mapped[str] = mapped_column(String(128), default="")
    sender_id: Mapped[str] = mapped_column(String(128), default="")
    message: Mapped[str] = mapped_column(Text, default="")
    timestamp: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    relevant: Mapped[bool] = mapped_column(Boolean, default=False)
    relevance_reasons: Mapped[list] = mapped_column(JSON, default=list)
    ticket_keys: Mapped[list] = mapped_column(JSON, default=list)


class IssueChange(Base):
    __tablename__ = "issue_changes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    issue_key: Mapped[str] = mapped_column(String(32), index=True)
    change_type: Mapped[str] = mapped_column(String(64))
    field: Mapped[str] = mapped_column(String(64), default="")
    from_value: Mapped[str] = mapped_column(Text, default="")
    to_value: Mapped[str] = mapped_column(Text, default="")
    author: Mapped[str] = mapped_column(String(128), default="")
    changed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    noisy: Mapped[bool] = mapped_column(Boolean, default=False)
    impact: Mapped[str] = mapped_column(String(16), default="medium")


class Correlation(Base):
    __tablename__ = "correlations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    issue_key: Mapped[str] = mapped_column(String(32), index=True)
    message_id: Mapped[int] = mapped_column(Integer)
    level: Mapped[int] = mapped_column(Integer, default=1)
    confidence: Mapped[str] = mapped_column(String(16), default="HIGH")
    match_reason: Mapped[str] = mapped_column(String(256), default="")


class Insight(Base):
    __tablename__ = "pm_insights"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(Integer, index=True)
    type: Mapped[str] = mapped_column(String(32), index=True)
    title: Mapped[str] = mapped_column(String(256))
    description: Mapped[str] = mapped_column(Text, default="")
    action: Mapped[str] = mapped_column(Text, default="")
    action_type: Mapped[str] = mapped_column(String(32), default="")
    confidence: Mapped[str] = mapped_column(String(16), default="MEDIUM")
    issue_key: Mapped[str] = mapped_column(String(32), default="")
    sources: Mapped[list] = mapped_column(JSON, default=list)
    why: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Standup(Base):
    __tablename__ = "standups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(Integer, index=True)
    window_start: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    window_end: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    needs_attention: Mapped[list] = mapped_column(JSON, default=list)
    at_risk: Mapped[list] = mapped_column(JSON, default=list)
    completed: Mapped[list] = mapped_column(JSON, default=list)
    team_signals: Mapped[list] = mapped_column(JSON, default=list)
    todays_actions: Mapped[list] = mapped_column(JSON, default=list)
    bugs: Mapped[list] = mapped_column(JSON, default=list)
    tasks: Mapped[list] = mapped_column(JSON, default=list)
    wallet_requests: Mapped[list] = mapped_column(JSON, default=list)
    long_pending: Mapped[list] = mapped_column(JSON, default=list)
    week_actions: Mapped[list] = mapped_column(JSON, default=list)
    this_week: Mapped[list] = mapped_column(JSON, default=list)
    other_actions: Mapped[list] = mapped_column(JSON, default=list)
    cliq_briefing: Mapped[dict] = mapped_column(JSON, default=dict)
    dev_load: Mapped[list] = mapped_column(JSON, default=list)
    monday_plan: Mapped[dict] = mapped_column(JSON, default=dict)
    raw_markdown: Mapped[str] = mapped_column(Text, default="")
    llm_used: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    delivery_status: Mapped[str] = mapped_column(String(32), default="pending")


class Evaluation(Base):
    __tablename__ = "evaluations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    standup_id: Mapped[int] = mapped_column(Integer, index=True)
    overall: Mapped[float] = mapped_column(Float, default=0)
    signal_detection: Mapped[float] = mapped_column(Float, default=0)
    prioritization: Mapped[float] = mapped_column(Float, default=0)
    grounding: Mapped[float] = mapped_column(Float, default=0)
    actionability: Mapped[float] = mapped_column(Float, default=0)
    completeness: Mapped[float] = mapped_column(Float, default=0)
    noise: Mapped[float] = mapped_column(Float, default=0)
    hallucination: Mapped[float] = mapped_column(Float, default=0)
    notes: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class HiddenCard(Base):
    __tablename__ = "hidden_cards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    card_key: Mapped[str] = mapped_column(String(256), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(256), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CodebaseSnapshot(Base):
    __tablename__ = "codebase_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    path: Mapped[str] = mapped_column(String(512), default="")
    branch: Mapped[str] = mapped_column(String(128), default="")
    commit_sha: Mapped[str] = mapped_column(String(64), default="")
    commit_at: Mapped[str] = mapped_column(String(64), default="")
    commit_message: Mapped[str] = mapped_column(String(512), default="")
    ahead: Mapped[int] = mapped_column(Integer, default=0)
    behind: Mapped[int] = mapped_column(Integer, default=0)
    module_count: Mapped[int] = mapped_column(Integer, default=0)
    pulled: Mapped[bool] = mapped_column(Boolean, default=False)
    pull_error: Mapped[str] = mapped_column(Text, default="")
    llm_used: Mapped[bool] = mapped_column(Boolean, default=False)
    recent_commits: Mapped[list] = mapped_column(JSON, default=list)
    live_base: Mapped[str] = mapped_column(String(128), default="")
    live_summary: Mapped[str] = mapped_column(Text, default="")
    live_commits: Mapped[list] = mapped_column(JSON, default=list)
    live_files: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CodebaseModule(Base):
    __tablename__ = "codebase_modules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    snapshot_id: Mapped[int] = mapped_column(Integer, index=True)
    name: Mapped[str] = mapped_column(String(128), index=True)
    kind: Mapped[str] = mapped_column(String(32), default="service")
    summary: Mapped[str] = mapped_column(Text, default="")
    docs_excerpt: Mapped[str] = mapped_column(Text, default="")
    tree: Mapped[str] = mapped_column(Text, default="")
    doc_paths: Mapped[list] = mapped_column(JSON, default=list)
    capabilities: Mapped[list] = mapped_column(JSON, default=list)


class CodebaseAsk(Base):
    __tablename__ = "codebase_asks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    question: Mapped[str] = mapped_column(Text, default="")
    answer: Mapped[str] = mapped_column(Text, default="")
    citations: Mapped[list] = mapped_column(JSON, default=list)
    snapshot_id: Mapped[int] = mapped_column(Integer, default=0)
    branch: Mapped[str] = mapped_column(String(128), default="")
    commit_sha: Mapped[str] = mapped_column(String(64), default="")
    llm_used: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ReleasePack(Base):
    __tablename__ = "release_packs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(256), default="")
    kind: Mapped[str] = mapped_column(String(32), default="pack")
    angle: Mapped[str] = mapped_column(Text, default="")
    internal_update: Mapped[str] = mapped_column(Text, default="")
    release_notes: Mapped[str] = mapped_column(Text, default="")
    newsletter: Mapped[list] = mapped_column(JSON, default=list)
    artifacts: Mapped[list] = mapped_column(JSON, default=list)
    snapshot_id: Mapped[int] = mapped_column(Integer, default=0)
    branch: Mapped[str] = mapped_column(String(128), default="")
    commit_sha: Mapped[str] = mapped_column(String(64), default="")
    llm_used: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ReleaseNotesJob(Base):
    __tablename__ = "release_notes_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    branch: Mapped[str] = mapped_column(String(128), default="")
    commit_sha: Mapped[str] = mapped_column(String(64), default="", index=True)
    pack_id: Mapped[int] = mapped_column(Integer, default=0)
    pdf_path: Mapped[str] = mapped_column(String(512), default="")
    emailed_to: Mapped[str] = mapped_column(String(256), default="")
    status: Mapped[str] = mapped_column(String(32), default="")
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ReleaseJob(Base):
    __tablename__ = "release_jobs"
    __table_args__ = (UniqueConstraint("branch", "sha", name="uq_release_branch_sha"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    branch: Mapped[str] = mapped_column(String(128), default="")
    sha: Mapped[str] = mapped_column(String(64), default="")
    base_sha: Mapped[str] = mapped_column(String(64), default="")
    merged_at: Mapped[str] = mapped_column(String(64), default="")
    snapshot_id: Mapped[int] = mapped_column(Integer, default=0)
    pack_id: Mapped[int] = mapped_column(Integer, default=0)
    pdf_path: Mapped[str] = mapped_column(String(512), default="")
    drive_file_id: Mapped[str] = mapped_column(String(128), default="")
    drive_link: Mapped[str] = mapped_column(String(512), default="")
    extraction: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(64), default="detected")
    error_detail: Mapped[str] = mapped_column(Text, default="")
    triggered_by: Mapped[str] = mapped_column(String(32), default="auto")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Prd(Base):
    __tablename__ = "prds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(256), default="")
    problem: Mapped[str] = mapped_column(Text, default="")
    service: Mapped[str] = mapped_column(String(128), default="")
    issue_key: Mapped[str] = mapped_column(String(32), default="")
    issue_keys: Mapped[list] = mapped_column(JSON, default=list)
    markdown: Mapped[str] = mapped_column(Text, default="")
    sources: Mapped[list] = mapped_column(JSON, default=list)
    snapshot_id: Mapped[int] = mapped_column(Integer, default=0)
    branch: Mapped[str] = mapped_column(String(128), default="")
    commit_sha: Mapped[str] = mapped_column(String(64), default="")
    llm_used: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Roadmap(Base):
    __tablename__ = "roadmaps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    year: Mapped[int] = mapped_column(Integer, default=0)
    quarter: Mapped[int] = mapped_column(Integer, default=0)
    label: Mapped[str] = mapped_column(String(32), default="")
    months: Mapped[list] = mapped_column(JSON, default=list)
    month_labels: Mapped[list] = mapped_column(JSON, default=list)
    epics: Mapped[list] = mapped_column(JSON, default=list)
    notes: Mapped[str] = mapped_column(Text, default="")
    llm_used: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CopilotThread(Base):
    __tablename__ = "copilot_threads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    turns: Mapped[list] = mapped_column(JSON, default=list)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CopilotPlan(Base):
    __tablename__ = "copilot_plans"

    parent_plan_id: Mapped[int] = mapped_column(Integer, default=0)
    context_json: Mapped[dict] = mapped_column(JSON, default=dict)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    thread_id: Mapped[int] = mapped_column(Integer, default=0)
    prompt: Mapped[str] = mapped_column(Text, default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    branch: Mapped[str] = mapped_column(String(128), default="")
    ticket_keys: Mapped[list] = mapped_column(JSON, default=list)
    people: Mapped[list] = mapped_column(JSON, default=list)
    image_ids: Mapped[list] = mapped_column(JSON, default=list)
    answer: Mapped[str] = mapped_column(Text, default="")
    actions: Mapped[list] = mapped_column(JSON, default=list)
    questions: Mapped[list] = mapped_column(JSON, default=list)
    epics: Mapped[list] = mapped_column(JSON, default=list)
    citations: Mapped[list] = mapped_column(JSON, default=list)
    needs_confirm: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(32), default="preview")
    results: Mapped[list] = mapped_column(JSON, default=list)
    llm_used: Mapped[bool] = mapped_column(Boolean, default=False)
    plan_hash: Mapped[str] = mapped_column(String(64), default="")
    fingerprint: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    ran_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    status: Mapped[str] = mapped_column(String(32), default="running")
    trigger: Mapped[str] = mapped_column(String(32), default="manual")
    window_start: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    window_end: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    jira_count: Mapped[int] = mapped_column(Integer, default=0)
    cliq_count: Mapped[int] = mapped_column(Integer, default=0)
    relevant_cliq_count: Mapped[int] = mapped_column(Integer, default=0)
    change_count: Mapped[int] = mapped_column(Integer, default=0)
    insight_count: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str] = mapped_column(Text, default="")
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    attempt: Mapped[int] = mapped_column(Integer, default=1)
    dead_letter: Mapped[bool] = mapped_column(Boolean, default=False)


class CopilotAudit(Base):
    __tablename__ = "copilot_audit"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plan_id: Mapped[int] = mapped_column(Integer, index=True, default=0)
    actor: Mapped[str] = mapped_column(String(128), default="")
    plan_hash: Mapped[str] = mapped_column(String(64), default="")
    plan_json: Mapped[dict] = mapped_column(JSON, default=dict)
    results_json: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(32), default="")
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class BackgroundJob(Base):
    __tablename__ = "background_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(32), default="", index=True)
    status: Mapped[str] = mapped_column(String(32), default="queued")
    steps: Mapped[dict] = mapped_column(JSON, default=dict)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str] = mapped_column(Text, default="")
    worker_pid: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class GitStash(Base):
    __tablename__ = "git_stashes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    branch: Mapped[str] = mapped_column(String(128), default="")
    label: Mapped[str] = mapped_column(String(512), default="")
    message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    restored_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class LlmUsage(Base):
    __tablename__ = "llm_usage"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    surface: Mapped[str] = mapped_column(String(64), default="", index=True)
    model: Mapped[str] = mapped_column(String(128), default="")
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class DailyNote(Base):
    __tablename__ = "daily_notes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    day: Mapped[str] = mapped_column(String(10), index=True)
    title: Mapped[str] = mapped_column(String(256), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    learning: Mapped[str] = mapped_column(Text, default="")
    kind: Mapped[str] = mapped_column(String(32), default="daily", index=True)
    blocks: Mapped[list] = mapped_column(JSON, default=list)
    tags: Mapped[list] = mapped_column(JSON, default=list)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class LibraryDocument(Base):
    __tablename__ = "library_documents"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(256), default="")
    filename: Mapped[str] = mapped_column(String(256), default="")
    file_id: Mapped[str] = mapped_column(String(64), unique=True)
    media_type: Mapped[str] = mapped_column(String(128), default="")
    size: Mapped[int] = mapped_column(Integer, default=0)
    text: Mapped[str] = mapped_column(Text, default="")
    pages: Mapped[list] = mapped_column(JSON, default=list)
    tags: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(32), default="to_read")
    extraction_note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Competitor(Base):
    __tablename__ = "competitors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128), default="")
    aliases: Mapped[list] = mapped_column(JSON, default=list)
    website: Mapped[str] = mapped_column(String(512), default="")
    changelog_url: Mapped[str] = mapped_column(String(512), default="")
    blog_url: Mapped[str] = mapped_column(String(512), default="")
    pricing_url: Mapped[str] = mapped_column(String(512), default="")
    g2_url: Mapped[str] = mapped_column(String(512), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_fetched_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CompetitorSignal(Base):
    __tablename__ = "competitor_signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    competitor_id: Mapped[int] = mapped_column(Integer, index=True, default=0)
    competitor_name: Mapped[str] = mapped_column(String(128), default="")
    source: Mapped[str] = mapped_column(String(64), default="")  # changelog|blog|pricing|g2|news|manual
    title: Mapped[str] = mapped_column(String(512), default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    url: Mapped[str] = mapped_column(String(512), default="")
    tag: Mapped[str] = mapped_column(String(64), default="")  # feature_parity|pricing|positioning|shipping
    ask_eng: Mapped[str] = mapped_column(Text, default="")
    content_hash: Mapped[str] = mapped_column(String(64), default="", index=True)
    seen_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    raw_excerpt: Mapped[str] = mapped_column(Text, default="")


class PricingSnapshot(Base):
    __tablename__ = "pricing_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    competitor_id: Mapped[int] = mapped_column(Integer, index=True)
    competitor_name: Mapped[str] = mapped_column(String(128), default="")
    url: Mapped[str] = mapped_column(String(512), default="")
    content_hash: Mapped[str] = mapped_column(String(64), default="")
    excerpt: Mapped[str] = mapped_column(Text, default="")
    changed: Mapped[bool] = mapped_column(Boolean, default=False)
    change_note: Mapped[str] = mapped_column(Text, default="")
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class MarketWatch(Base):
    """Industry / compliance / integration sensing sources."""

    __tablename__ = "market_watches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    category: Mapped[str] = mapped_column(String(32), index=True)  # industry|compliance|integration
    name: Mapped[str] = mapped_column(String(128), default="")
    url: Mapped[str] = mapped_column(String(512), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_fetched_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class MarketSignal(Base):
    __tablename__ = "market_signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    watch_id: Mapped[int] = mapped_column(Integer, index=True, default=0)
    category: Mapped[str] = mapped_column(String(32), index=True)
    source_name: Mapped[str] = mapped_column(String(128), default="")
    title: Mapped[str] = mapped_column(String(512), default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    url: Mapped[str] = mapped_column(String(512), default="")
    affects_roadmap: Mapped[str] = mapped_column(String(16), default="watch")  # yes|no|watch
    content_hash: Mapped[str] = mapped_column(String(64), default="", index=True)
    seen_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    raw_excerpt: Mapped[str] = mapped_column(Text, default="")


class ParityCapability(Base):
    __tablename__ = "parity_capabilities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(256), unique=True)
    source: Mapped[str] = mapped_column(String(64), default="seed")  # seed|roadmap|manual
    epic_key: Mapped[str] = mapped_column(String(32), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    # {competitor_slug: "strong"|"partial"|"gap"|"unknown"}
    coverage: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Prototype(Base):
    __tablename__ = "prototypes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(180), default="Untitled prototype")
    status: Mapped[str] = mapped_column(String(32), default="draft")
    error: Mapped[str] = mapped_column(Text, default="")
    llm_used: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PrototypeFile(Base):
    __tablename__ = "prototype_files"
    __table_args__ = (UniqueConstraint("prototype_id", "path", name="uq_prototype_path"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    prototype_id: Mapped[int] = mapped_column(Integer, index=True)
    path: Mapped[str] = mapped_column(String(256))
    content: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PrototypeMessage(Base):
    __tablename__ = "prototype_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    prototype_id: Mapped[int] = mapped_column(Integer, index=True)
    role: Mapped[str] = mapped_column(String(16), default="user")
    body: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
