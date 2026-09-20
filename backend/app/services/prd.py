"""Generate a PRD grounded in the go_services product map and optional Jira ticket."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.clients.llm import LLMClient
from app.models import JiraIssue, Prd
from app.services.codebase import grep_codebase, latest_snapshot, retrieve_modules
from app.services.filter import extract_ticket_keys
from app.services.prompts import with_preamble
from app.services.time_window import now_local

PRD_PROMPT = with_preamble(
    """You are Arsalaan's PM writing a Product Requirements Document for Convin Sense / Activate.
Ground every technical claim in the provided product map, docs excerpts, git hits, tagged Jira tickets, and attached Sense prototype files.
Do not invent APIs, tables, owners, or services that are not in the evidence.
If a Sense prototype is attached, treat those files and prompt history as the proposed product UI. Name real prototype paths under Services and files.
If several tickets are tagged, write ONE PRD that covers them together.
Name every tagged key exactly once in Current behavior or Problem.
If the payload contains no tagged Jira tickets, say so explicitly under Open questions instead of implying ticket coverage.
If the codebase does not show current behavior, say so under Open questions.

Approx word budget:
Problem 80-120, Goals 60-80, Non-goals 40-60, Current behavior 80-120,
Proposed behavior 150-250, Services and files 60-100, APIs and data 80-120,
Analytics 40-60, Rollout 60-100, Open questions 40-80.

Return JSON:
{
  "title": "short PRD title",
  "markdown": "full PRD in markdown",
  "not_enough_evidence": ""
}

Markdown MUST use these headings:
# <title>
## Problem
## Goals
## Non-goals
## Current behavior
## Proposed behavior
## Services and files
## APIs and data
## Analytics and success
## Rollout and risks
## Open questions

In Services and files, name real go_services modules from the payload, and prototype paths when a Sense prototype is attached.
"""
)


def _jira_context(db: Session, issue_key: str) -> dict | None:
    key = (issue_key or "").strip().upper()
    if not key:
        return None
    issue = db.query(JiraIssue).filter(JiraIssue.issue_key == key).one_or_none()
    if not issue:
        return {"issue_key": key, "found": False}
    extras = issue.extra_json or {}
    return {
        "issue_key": issue.issue_key,
        "found": True,
        "summary": issue.summary,
        "status": issue.status,
        "priority": issue.priority,
        "issue_type": issue.issue_type,
        "assignee": issue.assignee,
        "description": (issue.description or "")[:2500],
        "product_area": extras.get("product_area") or "",
        "product_manager": extras.get("product_manager") or "",
        "url": issue.url,
    }


def _normalize_keys(*parts: str, keys: list[str] | None = None) -> list[str]:
    found: list[str] = []
    for key in keys or []:
        found.extend(extract_ticket_keys(key) or [key.strip().upper()])
    blob = " ".join(part for part in parts if part)
    found.extend(extract_ticket_keys(blob))
    out = []
    for key in found:
        key = (key or "").strip().upper()
        if key and key not in out:
            out.append(key)
    return out[:12]


def _heuristic_prd(title: str, problem: str, modules: list, hits: list, jira: dict | None, prototype: dict | None = None) -> str:
    lines = [f"# {title or 'PRD'}", "", "## Problem", problem or "Not specified.", "", "## Goals", "- Ship the change described above without breaking existing tenants.", "", "## Non-goals", "- Unrelated refactors.", "", "## Current behavior"]
    if modules:
        for module in modules[:5]:
            lines.append(f"- **{module['name']}**: {module.get('summary') or ''}")
    elif prototype:
        lines.append(f"- Sense prototype **{prototype.get('title') or 'Untitled'}** is the proposed UI. Production current behavior is not indexed here.")
    else:
        lines.append("Codebase is not indexed yet. Open Codebase, pick a branch, and index it.")
    lines += ["", "## Proposed behavior", problem or "Describe the desired change after indexing.", "", "## Services and files"]
    if prototype:
        for item in (prototype.get("files") or [])[:8]:
            lines.append(f"- Prototype `{item.get('path')}`")
        tree = (prototype.get("tree") or "").strip()
        if tree:
            lines.append("- File tree: " + ", ".join(tree.split("\n")[:12]))
    for module in modules[:6]:
        docs = ", ".join((module.get("doc_paths") or [])[:4])
        lines.append(f"- `{module['name']}`" + (f" — {docs}" if docs else ""))
    if hits:
        lines.append("")
        for hit in hits[:8]:
            lines.append(f"- `{hit['path']}:{hit['line']}` {hit['text']}")
    lines += ["", "## APIs and data", "Confirm against the files above. Do not assume new endpoints.", "", "## Analytics and success", "- Define the metric after engineering review.", "", "## Rollout and risks", "- Ship behind the existing tenant/feature flags where those services already use them.", "", "## Open questions"]
    if jira and not jira.get("found"):
        lines.append(f"- Jira {jira.get('issue_key')} was not in the local board snapshot.")
    if not modules and not prototype:
        lines.append("- Index a branch in Codebase so this PRD can cite go_services.")
    return "\n".join(lines)


def generate_prd(db: Session, *, title: str, problem: str, service: str = "", issue_key: str = "", issue_keys: list[str] | None = None, prototype_id: int = 0) -> dict:
    snapshot = latest_snapshot(db)
    prototype = None
    if prototype_id:
        from app.services.prototype import prototype_pack
        try:
            prototype = prototype_pack(db, int(prototype_id), prompt=" ".join(part for part in (title, problem) if part))
        except LookupError as exc:
            raise RuntimeError(str(exc)) from exc
    if not snapshot and not prototype:
        raise RuntimeError("Index go_services first, or attach a Sense prototype.")
    keys = _normalize_keys(title, problem, issue_key, keys=issue_keys)
    tickets = [ctx for ctx in (_jira_context(db, key) for key in keys) if ctx]
    query = " ".join(part for part in (title, problem, service, " ".join(keys), (prototype or {}).get("title") or "") if part)
    modules = retrieve_modules(db, query, service=service) if snapshot else []
    module_payload = [
        {
            "name": row.name,
            "kind": row.kind,
            "summary": row.summary,
            "capabilities": row.capabilities or [],
            "doc_paths": row.doc_paths or [],
            "docs_excerpt": (row.docs_excerpt or "")[:2200],
            "tree": (row.tree or "")[:800],
        }
        for row in modules
    ]
    hits = grep_codebase(query) if snapshot else []
    primary = next((row for row in tickets if row.get("found")), tickets[0] if tickets else None)
    if not title.strip() and primary and primary.get("summary"):
        title = primary["summary"]
    if not title.strip() and prototype:
        title = f"{prototype.get('title') or 'Sense prototype'} PRD"
    payload = {
        "title": title,
        "problem": problem,
        "focus_service": service,
        "jira_tickets": tickets,
        "jira": primary,
        "indexed_branch": snapshot.branch if snapshot else "",
        "indexed_sha": snapshot.commit_sha if snapshot else "",
        "recent_commits": ((snapshot.recent_commits or [])[:12] if snapshot else []),
        "modules": module_payload,
        "code_hits": hits,
        "prototype": prototype,
    }
    llm = LLMClient()
    llm_used = False
    markdown = ""
    resolved_title = title.strip() or "Untitled PRD"
    if llm.configured:
        try:
            generated = llm.complete_json(payload, system_prompt=PRD_PROMPT, max_chars=22000, surface="prd")
            markdown = str(generated.get("markdown") or "").strip()
            resolved_title = str(generated.get("title") or resolved_title).strip()[:256]
            llm_used = bool(markdown)
            missing_keys = [key for key in keys if key and key not in markdown.upper()]
            if not keys:
                if "open questions" in markdown.lower() and "no tagged" not in markdown.lower():
                    markdown = markdown.rstrip() + "\n\nNo tagged Jira tickets were provided for this PRD."
            elif missing_keys:
                markdown = markdown.rstrip() + "\n\nTagged tickets not named above: " + ", ".join(missing_keys)
        except Exception:
            llm_used = False
    if not markdown:
        markdown = _heuristic_prd(resolved_title, problem, module_payload, hits, primary, prototype)
        if tickets:
            markdown += "\n\nTagged tickets: " + ", ".join(row["issue_key"] for row in tickets)
    sources = [
        *([{"type": "codebase", "ref": f"{snapshot.branch}@{snapshot.commit_sha}"}] if snapshot else []),
        *[{"type": "module", "ref": row["name"]} for row in module_payload[:8]],
        *[{"type": "jira", "ref": row["issue_key"]} for row in tickets],
        *([{"type": "prototype", "ref": str(prototype["id"]), "title": prototype.get("title") or ""}] if prototype else []),
    ]
    prd = Prd(
        title=resolved_title,
        problem=problem,
        service=service,
        issue_key=keys[0] if keys else "",
        issue_keys=keys,
        markdown=markdown,
        sources=sources,
        snapshot_id=snapshot.id if snapshot else 0,
        branch=snapshot.branch if snapshot else (f"prototype/{prototype['id']}" if prototype else ""),
        commit_sha=snapshot.commit_sha if snapshot else "",
        llm_used=llm_used,
        created_at=now_local().replace(tzinfo=None),
    )
    db.add(prd)
    db.commit()
    db.refresh(prd)
    return prd_out(prd)


def prd_out(prd: Prd) -> dict:
    keys = list(prd.issue_keys or [])
    if prd.issue_key and prd.issue_key not in keys:
        keys = [prd.issue_key, *keys]
    return {
        "id": prd.id,
        "title": prd.title,
        "problem": prd.problem,
        "service": prd.service,
        "issue_key": keys[0] if keys else prd.issue_key,
        "issue_keys": keys,
        "markdown": prd.markdown,
        "sources": prd.sources or [],
        "snapshot_id": prd.snapshot_id,
        "branch": prd.branch,
        "commit_sha": prd.commit_sha,
        "llm_used": prd.llm_used,
        "created_at": prd.created_at.isoformat() if prd.created_at else None,
    }


def list_prds(db: Session, limit: int = 30) -> list[dict]:
    rows = db.query(Prd).order_by(Prd.id.desc()).limit(limit).all()
    return [prd_out(row) for row in rows]


def get_prd(db: Session, prd_id: int) -> dict | None:
    row = db.query(Prd).filter(Prd.id == prd_id).one_or_none()
    return prd_out(row) if row else None
