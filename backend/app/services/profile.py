"""The active workspace's product profile (PM identity, product name, data branch)."""

from __future__ import annotations

from app import context
from app.config import settings


def load_profile() -> dict:
    ctx = context.current()
    stored = dict(ctx.profile) if ctx is not None else {}
    profile = {
        "pm_display_name": stored.get("pm_display_name") or settings.pm_display_name or "",
        "pm_cliq_user_id": stored.get("pm_cliq_user_id") or settings.pm_cliq_user_id or "",
        "pm_cliq_mentions": stored.get("pm_cliq_mentions") or settings.pm_cliq_mentions or "",
        "pm_personas": stored.get("pm_personas") or "",
        "product_name": stored.get("product_name") or settings.product_name or "",
        "company_name": stored.get("company_name") or settings.company_name or "",
        "product_description": stored.get("product_description") or "",
        "competitor_focus": stored.get("competitor_focus") or "",
        "competitor_pack": stored.get("competitor_pack") or "",
        "support_email": stored.get("support_email") or settings.support_email or "",
        "newsletter_sender": stored.get("newsletter_sender") or "",
        "jira_scope_rules": stored.get("jira_scope_rules") or "",
        "product_modules": stored.get("product_modules") or "",
        "product_module_keywords": stored.get("product_module_keywords") if isinstance(stored.get("product_module_keywords"), dict) else {},
        "brand_rules": stored.get("brand_rules") or "",
        "brand": stored.get("brand") if isinstance(stored.get("brand"), dict) else {},
        "tone": stored.get("tone") or "",
        "timezone": (ctx.timezone if ctx is not None else "") or settings.timezone or "Asia/Kolkata",
        "data_branch": stored.get("data_branch") or "",
        "app_name": settings.app_name,
        "workspace": ctx.name if ctx is not None else "",
    }
    mention = str(profile.get("pm_cliq_mentions") or "")
    uid = str(profile.get("pm_cliq_user_id") or "").strip()
    if uid:
        tagged = "{@" + uid + "}"
        if tagged not in mention:
            profile["pm_cliq_mentions"] = ",".join([part for part in mention.split(",") if part.strip()] + [tagged])
    return profile


def product_modules() -> list[str]:
    """Customer-facing module names, main one first (e.g. "Core,Analytics"); defaults to the product name."""
    profile = load_profile()
    names = [part.strip() for part in str(profile.get("product_modules") or "").split(",") if part.strip()]
    return names or [profile.get("product_name") or profile.get("workspace") or "Product"]


def module_for(text: str) -> str:
    """The module a piece of copy is about: a secondary module named (or keyworded) in it, else the main one."""
    names = product_modules()
    lowered = (text or "").lower()
    keywords = load_profile().get("product_module_keywords") or {}
    for name in names[1:]:
        hints = [name, *(keywords.get(name) or [])] if isinstance(keywords, dict) else [name]
        if any(str(hint).lower() in lowered for hint in hints if hint):
            return name
    return names[0]


def save_profile(updates: dict) -> dict:
    from app.database import SessionLocal
    from app.workspaces import save_profile as save_workspace_profile

    db = SessionLocal()
    try:
        save_workspace_profile(db, updates or {})
    finally:
        db.close()
    return load_profile()
