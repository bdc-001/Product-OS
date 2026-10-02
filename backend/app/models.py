from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.tenancy import WorkspaceScoped


# Platform tables (not workspace-scoped)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    clerk_user_id: Mapped[str | None] = mapped_column(String(128), unique=True, nullable=True)
    email: Mapped[str] = mapped_column(String(320), default="", index=True)
    name: Mapped[str] = mapped_column(String(200), default="")
    avatar_url: Mapped[str] = mapped_column(String(1024), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True)
    name: Mapped[str] = mapped_column(String(200), default="")
    kind: Mapped[str] = mapped_column(String(32), default="organization")
    clerk_org_id: Mapped[str | None] = mapped_column(String(128), unique=True, nullable=True)
    personal_user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True, unique=True)
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Kolkata")
    profile: Mapped[dict] = mapped_column(JSON, default=dict)
    data_key: Mapped[str] = mapped_column(Text, default="")
    config_version: Mapped[int] = mapped_column(Integer, default=1)
    onboarded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Membership(Base):
    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("user_id", "workspace_id", name="uq_membership"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    workspace_id: Mapped[int] = mapped_column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(16), default="member")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# Workspace configuration


class AuditEvent(WorkspaceScoped, Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor: Mapped[str] = mapped_column(String(320), default="")
    action: Mapped[str] = mapped_column(String(64), index=True)
    target: Mapped[str] = mapped_column(String(256), default="")
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class Connection(WorkspaceScoped, Base):
    __tablename__ = "connections"
    __table_args__ = (UniqueConstraint("workspace_id", "provider", "name", name="uq_connection"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider: Mapped[str] = mapped_column(String(48), index=True)
    name: Mapped[str] = mapped_column(String(80), default="default")
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    secrets: Mapped[str] = mapped_column(Text, default="")
    secret_hints: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(24), default="untested")
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[str] = mapped_column(Text, default="")
    updated_by: Mapped[str] = mapped_column(String(320), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Repository(WorkspaceScoped, Base):
    __tablename__ = "repositories"
    __table_args__ = (UniqueConstraint("workspace_id", "name", name="uq_repository_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    provider: Mapped[str] = mapped_column(String(24), default="bitbucket")
    remote_url: Mapped[str] = mapped_column(String(1024), default="")
    connection_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mode: Mapped[str] = mapped_column(String(16), default="managed")
    local_path: Mapped[str] = mapped_column(String(1024), default="")
    default_branch: Mapped[str] = mapped_column(String(200), default="main")
    product_branch: Mapped[str] = mapped_column(String(200), default="")
    release_pattern: Mapped[str] = mapped_column(String(200), default="release/YYYY-MM-DD")
    merge_format: Mapped[str] = mapped_column(String(24), default="any")
    path_scopes: Mapped[list] = mapped_column(JSON, default=list)
    ui_path: Mapped[str] = mapped_column(String(512), default="")
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    last_fetch_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_fetch_status: Mapped[str] = mapped_column(String(24), default="never")
    last_fetch_error: Mapped[str] = mapped_column(Text, default="")
    branches_cache: Mapped[list] = mapped_column(JSON, default=list)
    indexed_branches: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Person(WorkspaceScoped, Base):
    __tablename__ = "people"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    short: Mapped[str] = mapped_column(String(80), default="")
    email: Mapped[str] = mapped_column(String(320), default="")
    jira_account_id: Mapped[str] = mapped_column(String(128), default="")
    cliq_user_id: Mapped[str] = mapped_column(String(128), default="")
    cliq_chat_id: Mapped[str] = mapped_column(String(128), default="")
    # dev | qa | pm | notes_pm | other
    role: Mapped[str] = mapped_column(String(24), default="dev")
    team: Mapped[str] = mapped_column(String(80), default="")
    aliases: Mapped[list] = mapped_column(JSON, default=list)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PipelineConfig(WorkspaceScoped, Base):
    __tablename__ = "pipeline_configs"
    __table_args__ = (UniqueConstraint("workspace_id", "pipeline_id", name="uq_pipeline_config"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pipeline_id: Mapped[str] = mapped_column(String(64))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    schedule: Mapped[str] = mapped_column(String(120), default="")
    schedule_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    settings: Mapped[dict] = mapped_column(JSON, default=dict)
    last_fired_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# Domain tables


class MarketingFeature(WorkspaceScoped, Base):
    __tablename__ = "marketing_features"
    __table_args__ = (UniqueConstraint("workspace_id", "identity", name="uq_marketing_feature_identity"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(180))
    identity: Mapped[str] = mapped_column(String(180))
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


class MarketingScan(WorkspaceScoped, Base):
    __tablename__ = "marketing_scans"
    __table_args__ = (UniqueConstraint("workspace_id", "fingerprint", name="uq_marketing_scan_fingerprint"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    fingerprint: Mapped[str] = mapped_column(String(64))
    branch: Mapped[str] = mapped_column(String(128), default="")
    source_sha: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class MarketingCampaign(WorkspaceScoped, Base):
    __tablename__ = "marketing_campaigns"
    __table_args__ = (UniqueConstraint("workspace_id", "run_key", name="uq_marketing_campaign_run_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_key: Mapped[str | None] = mapped_column(String(200), nullable=True)
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


class AvatarVideo(WorkspaceScoped, Base):
    """HeyGen presenter video. Independent of MarketingCampaign and the Remotion film pipeline."""

    __tablename__ = "avatar_videos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(180), default="")
    feature_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    script: Mapped[str] = mapped_column(Text, default="")
    avatar_id: Mapped[str] = mapped_column(String(120), default="")
    avatar_name: Mapped[str] = mapped_column(String(180), default="")
    avatar_type: Mapped[str] = mapped_column(String(32), default="")
    avatar_preview_url: Mapped[str] = mapped_column(Text, default="")
    voice_id: Mapped[str] = mapped_column(String(120), default="")
    voice_name: Mapped[str] = mapped_column(String(180), default="")
    options: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(32), default="draft", index=True)
    heygen_video_id: Mapped[str] = mapped_column(String(120), default="", index=True)
    attempt: Mapped[int] = mapped_column(Integer, default=0)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    assets: Mapped[list] = mapped_column(JSON, default=list)
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    checked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class JiraIssue(WorkspaceScoped, Base):
    __tablename__ = "jira_issues"
    __table_args__ = (UniqueConstraint("workspace_id", "issue_key", name="uq_jira_issue_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    issue_key: Mapped[str] = mapped_column(String(32), index=True)
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
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    due_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    comments_json: Mapped[list] = mapped_column(JSON, default=list)
    changelog_json: Mapped[list] = mapped_column(JSON, default=list)
    extra_json: Mapped[dict] = mapped_column(JSON, default=dict)
    url: Mapped[str] = mapped_column(String(512), default="")
    ingested_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)


class CliqChat(WorkspaceScoped, Base):
    __tablename__ = "cliq_chats"
    __table_args__ = (UniqueConstraint("workspace_id", "chat_id", name="uq_cliq_chat"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chat_id: Mapped[str] = mapped_column(String(128), index=True)
    name: Mapped[str] = mapped_column(String(256), default="")
    chat_type: Mapped[str] = mapped_column(String(64), default="")
    last_modified: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    raw: Mapped[dict] = mapped_column(JSON, default=dict)


class CliqMessage(WorkspaceScoped, Base):
    __tablename__ = "cliq_messages"
    __table_args__ = (UniqueConstraint("workspace_id", "chat_id", "message_id", name="uq_cliq_msg"),)

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


class IssueChange(WorkspaceScoped, Base):
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


class Correlation(WorkspaceScoped, Base):
    __tablename__ = "correlations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    issue_key: Mapped[str] = mapped_column(String(32), index=True)
    message_id: Mapped[int] = mapped_column(Integer)
    level: Mapped[int] = mapped_column(Integer, default=1)
    confidence: Mapped[str] = mapped_column(String(16), default="HIGH")
    match_reason: Mapped[str] = mapped_column(String(256), default="")


class Insight(WorkspaceScoped, Base):
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


class Standup(WorkspaceScoped, Base):
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


class Evaluation(WorkspaceScoped, Base):
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


class HiddenCard(WorkspaceScoped, Base):
    __tablename__ = "hidden_cards"
    __table_args__ = (UniqueConstraint("workspace_id", "card_key", name="uq_hidden_card_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    card_key: Mapped[str] = mapped_column(String(256), index=True)
    title: Mapped[str] = mapped_column(String(256), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CodebaseSnapshot(WorkspaceScoped, Base):
    __tablename__ = "codebase_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    repository_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
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


class CodebaseModule(WorkspaceScoped, Base):
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


class CodebaseAsk(WorkspaceScoped, Base):
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


class ReleasePack(WorkspaceScoped, Base):
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


class ReleaseNotesJob(WorkspaceScoped, Base):
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


class ReleaseJob(WorkspaceScoped, Base):
    __tablename__ = "release_jobs"
    __table_args__ = (UniqueConstraint("workspace_id", "branch", "sha", name="uq_release_branch_sha"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    repository_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
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


class Prd(WorkspaceScoped, Base):
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


class Roadmap(WorkspaceScoped, Base):
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


class CopilotThread(WorkspaceScoped, Base):
    __tablename__ = "copilot_threads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    turns: Mapped[list] = mapped_column(JSON, default=list)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CopilotPlan(WorkspaceScoped, Base):
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


class PipelineRun(WorkspaceScoped, Base):
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


class CopilotAudit(WorkspaceScoped, Base):
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


class Run(WorkspaceScoped, Base):
    """One execution of a pipeline or background task. Replaces PID-owned background jobs."""

    __tablename__ = "runs"
    __table_args__ = (Index("ix_runs_claim", "status", "lease_expires_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(64), default="", index=True)
    pipeline_id: Mapped[str] = mapped_column(String(64), default="", index=True)
    task: Mapped[str] = mapped_column(String(64), default="")
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    trigger: Mapped[str] = mapped_column(String(32), default="manual")
    started_by: Mapped[str] = mapped_column(String(256), default="")
    parent_run_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    steps: Mapped[dict] = mapped_column(JSON, default=dict)
    logs: Mapped[list] = mapped_column(JSON, default=list)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    cost: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str] = mapped_column(Text, default="")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=1)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    lease_owner: Mapped[str] = mapped_column(String(128), default="")
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    worker_pid: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


BackgroundJob = Run


class GitStash(WorkspaceScoped, Base):
    __tablename__ = "git_stashes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    branch: Mapped[str] = mapped_column(String(128), default="")
    label: Mapped[str] = mapped_column(String(512), default="")
    message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    restored_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class LlmUsage(WorkspaceScoped, Base):
    __tablename__ = "llm_usage"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    surface: Mapped[str] = mapped_column(String(64), default="", index=True)
    model: Mapped[str] = mapped_column(String(128), default="")
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    run_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class DailyNote(WorkspaceScoped, Base):
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


class LibraryDocument(WorkspaceScoped, Base):
    __tablename__ = "library_documents"
    __table_args__ = (UniqueConstraint("workspace_id", "file_id", name="uq_library_file"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(256), default="")
    filename: Mapped[str] = mapped_column(String(256), default="")
    file_id: Mapped[str] = mapped_column(String(64))
    media_type: Mapped[str] = mapped_column(String(128), default="")
    size: Mapped[int] = mapped_column(Integer, default=0)
    text: Mapped[str] = mapped_column(Text, default="")
    pages: Mapped[list] = mapped_column(JSON, default=list)
    tags: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(32), default="to_read")
    extraction_note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Competitor(WorkspaceScoped, Base):
    __tablename__ = "competitors"
    __table_args__ = (UniqueConstraint("workspace_id", "slug", name="uq_competitor_slug"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), index=True)
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


class CompetitorSignal(WorkspaceScoped, Base):
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
    starred: Mapped[bool] = mapped_column(Boolean, default=False, index=True)


class PricingSnapshot(WorkspaceScoped, Base):
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


class MarketWatch(WorkspaceScoped, Base):
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


class MarketSignal(WorkspaceScoped, Base):
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
    starred: Mapped[bool] = mapped_column(Boolean, default=False, index=True)


class ParityCapability(WorkspaceScoped, Base):
    __tablename__ = "parity_capabilities"
    __table_args__ = (UniqueConstraint("workspace_id", "name", name="uq_parity_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(256))
    source: Mapped[str] = mapped_column(String(64), default="seed")  # seed|roadmap|manual
    epic_key: Mapped[str] = mapped_column(String(32), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    # {competitor_slug: "strong"|"partial"|"gap"|"unknown"}
    coverage: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Prototype(WorkspaceScoped, Base):
    __tablename__ = "prototypes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(180), default="Untitled prototype")
    status: Mapped[str] = mapped_column(String(32), default="draft")
    error: Mapped[str] = mapped_column(Text, default="")
    llm_used: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PrototypeFile(WorkspaceScoped, Base):
    __tablename__ = "prototype_files"
    __table_args__ = (UniqueConstraint("prototype_id", "path", name="uq_prototype_path"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    prototype_id: Mapped[int] = mapped_column(Integer, index=True)
    path: Mapped[str] = mapped_column(String(256))
    content: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PrototypeMessage(WorkspaceScoped, Base):
    __tablename__ = "prototype_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    prototype_id: Mapped[int] = mapped_column(Integer, index=True)
    role: Mapped[str] = mapped_column(String(16), default="user")
    body: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
