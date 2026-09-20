"""Release writing grounded in the indexed go_services branch."""

from __future__ import annotations

from collections import defaultdict

from sqlalchemy.orm import Session

from app.clients.llm import LLMClient, model_for
from app.models import CodebaseSnapshot, ReleasePack
from app.services.codebase import latest_snapshot
from app.services.prompts import strip_example_leaks, with_preamble
from app.services.time_window import now_local, period_for

KINDS = ("whatsapp", "release_notes", "newsletter")

WHATSAPP_EXAMPLE = """Good morning @all

*[FEATURE A] Updates:*

We've added new capabilities to [FEATURE A] so you can [OUTCOME] without [OLD PAIN].

*In [SURFACE B]:*

- See [KPI B] as a new Overview card
- Use [FILTER C] so you can focus instead of checking each item separately
- Track [METRIC D] through a new table called [TABLE C]

*In the individual view (for [AUDIENCE]):*

- Filter [METRIC E] by [DIMENSION] for more precise analysis.

⚙️ We are now configuring [COMING SOON]. Will share an update soon.
"""

RELEASE_NOTES_EXAMPLE = """Feature Title
[FEATURE A] — [SURFACE B]
Release Note [MONTH]

Field | Content
Feature Name | [FEATURE A]
Module Concerned | [MODULE]
Audience | Clients
Teams Concerned | Campaign managers, operations
Summary | [ONE SENTENCE OUTCOME].

📌 Background
Business problem it solves: [OLD PAIN].
Who benefits: [AUDIENCE].
What changes for the user after adopting it: [WHAT THEY SEE].

📌 Functional Overview
[FEATURE A] now works as [ROLE]. The user can [ACTION 1], [ACTION 2], and [ACTION 3].
What the user can create / configure / view: [LIST].
What the system does automatically: [LIST].
What outputs / reports / results the user sees: [LIST].
Do not explain how it works under the hood.

📌 Navigation
1. Open [FEATURE A]
2. Choose [SURFACE B]
3. Apply [FILTER C] as needed
Add screenshot placeholders only in How to Use (8.x), immediately after the step they illustrate. Never in Background or FAQs.

📌 Key Concepts (Glossary)
Term | Meaning (functional) | Example
[TERM] | [MEANING] | [EXAMPLE]

📌 Prerequisites / Setup Checklist
Before using the feature, ensure:
- Access / permission available
- Required parent config completed
- Related modules enabled

📌 How to Use (Step by Step)

8.1 Create / Configure
1. Open [SURFACE B].
2. You can see [KPI B] on Overview.
[Screenshot: [SURFACE B] — [KPI B]]
Expected result: [RESULT].

8.2 Enable / Attach / Activate
1. Apply [FILTER C].
2. Open [TABLE C].
[Screenshot: [TABLE C]]
Expected result: metrics follow the selection.

8.3 Day-to-Day Usage
1. Check [TABLE D].
[Screenshot: [TABLE D]]
Expected result: trends are scoped.

8.4 Review Outcomes
1. Note outliers.
[Screenshot: [OUTCOME VIEW]]
Expected result: one analysis pass covers the set.

📌 Configuration Options
Setting | What it controls | Recommended use | Impact if changed
[FILTER C] | Which items feed KPIs | Narrow to the accounts you own | Clearing restores the full set

📌 Outcome Analysis
Output | Meaning | Where seen | How to use it
[KPI B] | [MEANING] | Overview | Baseline before reading usage

📌 Common Workflows (Use Cases)
Use Case 1: [GOAL]
Steps: [SURFACE B] → [TABLE C].
Outcome: A short list to inspect.

📌 FAQs
Q: Why am I not seeing [KPI B]?
A: You may be in the wrong view. Switch to [SURFACE B].
"""

NEWSLETTER_EXAMPLE = """Hey Everyone,

Ashish here from Convin. Here's a roundup of the latest updates we have shipped for Sense over the last fortnight.

[FEATURE A]

[Paragraph 1: what the customer can now do, benefit-led.]

[Paragraph 2: how it simplifies their work and the outcome.]

Try it now!

[FEATURE B]

[Paragraph 1.]

[Paragraph 2.]

Try it now!
"""


WHATSAPP_PROMPT = with_preamble(f"""You write Convin internal WhatsApp / Cliq release blasts for Arsalaan.
Match the STYLE of the example: greeting, *asterisks* for bold, plain "- " bullets, no markdown headers, no links unless in the payload.
Max ~1200 characters. WhatsApp truncates preview walls.
The STYLE EXAMPLE uses placeholders. BEFORE returning, verify: every product/feature name in your output appears in the payload (indexed summary, commits, features_in_short, or user angle). If a name is not in the payload, remove it.
Write only what the indexed branch, commits, files, live summary, and optional user angle support.
If the evidence does not mention unfinished work, omit the ⚙️ line.
Open with Good morning @all (Good afternoon @all after 12:00 IST if the payload has period afternoon/evening).

STYLE EXAMPLE (copy this shape; placeholders are not product facts):
{WHATSAPP_EXAMPLE}

Return JSON:
{{
  "title": "short feature title",
  "whatsapp": "full message ready to paste into WhatsApp",
  "not_enough_evidence": ""
}}
""")

RELEASE_NOTES_PROMPT = with_preamble(f"""You write Convin CLIENT-FACING release-note documents for customers.
Lead with the outcome, then the action. Write to the customer as "you". Prefer "you can …" and "so you can …".
No under-the-hood implementation, no engineering, no CSM training voice, no internal-only steps.
Never write "confirm in product", "confirm in UAT", "under the hood", APIs, git, or tenant flags.
Screenshot placeholders: [Screenshot: ...]. Exactly one screenshot placeholder per major How-to sub-section (8.x), placed immediately after the step it illustrates. Never in Background or FAQs.
Audience is Clients. Teams Concerned are the customer roles who use it (for example Campaign managers, operations, supervisors).
Internal Cliq / WhatsApp releases are a different format — do not write those here.
The payload `features_in_short` (also in `angle`) is the PM's list of what shipped. Those items ARE the document.
BEFORE returning, verify: every product/feature name in your output appears in the payload. If a name is not in the payload, remove it.

STYLE EXAMPLE (copy this shape; placeholders are not product facts):
{RELEASE_NOTES_EXAMPLE}

Return JSON:
{{
  "title": "Feature Name",
  "release_notes": "full markdown document following the example outline",
  "not_enough_evidence": ""
}}
""")

NEWSLETTER_PROMPT = with_preamble(f"""You write Convin customer newsletters in Ashish's voice.
Each feature block under 120 words. 2-4 features. If the payload supports fewer than 2, return a single-feature issue.
Each block: FEATURE NAME IN CAPITALS, paragraph 1 = what the customer can now do (benefit-led), paragraph 2 = how it simplifies their work and the outcome, then "Try it now!".
No internals, no git, no CSM-only dashboards, no coming-soon engineering. Skip chores. Sense vs Activate from the payload product.
Do not include an unsubscribe footer.
BEFORE returning, verify: every product/feature name in your output appears in the payload. If a name is not in the payload, remove it.

STYLE EXAMPLE (copy this shape; placeholders are not product facts):
{NEWSLETTER_EXAMPLE}

Return JSON:
{{
  "title": "short roundup title",
  "intro": "Hey Everyone,\\n\\nAshish here from Convin. Here's a roundup ...",
  "features": [
    {{"feature": "FEATURE NAME", "headline": "paragraph 1", "body": "paragraph 2", "cta": "Try it now!"}}
  ],
  "not_enough_evidence": ""
}}
""")

PROMPTS = {
    "whatsapp": WHATSAPP_PROMPT,
    "release_notes": RELEASE_NOTES_PROMPT,
    "newsletter": NEWSLETTER_PROMPT,
}


def normalize_kind(kind: str) -> str:
    raw = (kind or "").strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "whatsapp_release": "whatsapp",
        "internal": "whatsapp",
        "internal_update": "whatsapp",
        "notes": "release_notes",
        "release": "release_notes",
        "news": "newsletter",
    }
    raw = aliases.get(raw, raw)
    if raw not in KINDS:
        raise RuntimeError("Pick WhatsApp release, release notes, or newsletter.")
    return raw


def _features_from_files(files: list[dict]) -> list[str]:
    counts: dict[str, int] = defaultdict(int)
    for row in files or []:
        top = (row.get("path") or "").split("/", 1)[0]
        if top:
            counts[top] += 1
    ranked = sorted(counts.items(), key=lambda item: item[1], reverse=True)
    return [name for name, _ in ranked if name not in {".github", "hack", "vendor"}][:10]


def _product_label(snapshot) -> str:
    branch = (snapshot.branch or "").lower()
    if "activate" in branch:
        return "Activate"
    return "Sense"


def _commit_bullets(snapshot, limit: int = 8) -> list[str]:
    bullets = [f"- {row.get('message')}" for row in (snapshot.live_commits or [])[:limit] if row.get("message")]
    return bullets or ["- Confirm the indexed branch has unique commits versus live."]


def _heuristic_whatsapp(title: str, angle: str, snapshot) -> str:
    heading = title.strip() or snapshot.branch or "Product update"
    intro = angle.strip() or (snapshot.live_summary or "We shipped updates on the indexed branch. Confirm the user-facing surfaces before sending.")
    first = intro.split("\n")[0].strip()
    lines = [
        "Good morning @all",
        "",
        f"*{heading}:*",
        "",
        first,
        "",
        "*What's new:*",
        *_commit_bullets(snapshot),
        "",
        "⚙️ Flag anything still behind a tenant flag before calling it live.",
    ]
    return "\n".join(lines)


def _heuristic_release_notes(title: str, angle: str, snapshot) -> str:
    heading = title.strip() or "Feature"
    summary = angle.strip() or (snapshot.live_summary or "You can use this release on the indexed branch.")
    bullets = _commit_bullets(snapshot, 10)
    first = summary.splitlines()[0][:240]
    return "\n".join(
        [
            f"Feature Title\n{heading}",
            "",
            "Field | Content",
            f"Feature Name | {heading}",
            f"Module Concerned | {_product_label(snapshot)}",
            "Audience | Clients",
            "Teams Concerned | Campaign managers, operations",
            f"Summary | {first}",
            "",
            "📌 Background",
            summary,
            "Who benefits (roles): Campaign managers and operations.",
            "What changes for the user after adopting it: You can complete the day-to-day path in one place.",
            "",
            "📌 Functional Overview",
            f"You can use {heading} so you can get this outcome without extra hops.",
            "What the user can create / configure / view:",
            *bullets,
            "What the system does automatically: Metrics update for the selection you choose.",
            "What outputs / reports / results the user sees: The shipped cards, tables, and trends.",
            "",
            "📌 Navigation",
            f"1. Open {heading}",
            f"2. Choose {_product_label(snapshot)}",
            "3. Apply filters as needed",
            "",
            "📌 Key Concepts (Glossary)",
            "Term | Meaning (functional) | Example",
            f"{heading} | The shipped surface | Open it from {_product_label(snapshot)}",
            "",
            "📌 Prerequisites / Setup Checklist",
            "- Access / permission available",
            "- Required parent config completed",
            "- Related modules enabled",
            "",
            "📌 How to Use (Step by Step)",
            "8.1 Create / Configure",
            "1. Open the surface above.",
            "Expected result: you can see the new fields.",
            "",
            "8.2 Enable / Attach / Activate",
            "1. Apply filters as needed.",
            "Expected result: metrics follow the selection.",
            "",
            "8.3 Day-to-Day Usage",
            "1. Use the feature on a live account.",
            "Expected result: trends stay scoped to your selection.",
            "",
            "8.4 Review Outcomes",
            "1. Check the visible result.",
            "Expected result: one pass covers the set.",
            "",
            "📌 Configuration Options",
            "Setting | What it controls | Recommended use | Impact if changed",
            "Filters | Which items feed the view | Narrow to the accounts you own | Clearing restores the full set",
            "",
            "📌 Outcome Analysis",
            "Output | Meaning | Where seen | How to use it",
            f"{heading} | Shipped result | Overview | Baseline before deeper analysis",
            "",
            "📌 Common Workflows (Use Cases)",
            f"Use Case 1: Complete the day-to-day path in {heading}.",
            "Steps: Follow 8.1–8.4.",
            "Outcome: A short list to act on.",
            "",
            "📌 FAQs",
            f"Q: Why am I not seeing {heading}?",
            "A: Open the shipped surface so you can see it once access is enabled.",
        ]
    )


def _heuristic_newsletter(title: str, angle: str, snapshot, features: list[str]) -> dict:
    product = _product_label(snapshot)
    summary = (angle.strip() or snapshot.live_summary or "").strip()
    intro = (
        f"Hey Everyone,\n\nAshish here from Convin. Here's a roundup of the latest updates we have shipped for {product} over the last fortnight."
    )
    blocks = []
    names = [title.strip()] if title.strip() else features[:3] or [product]
    for name in names[:3]:
        label = name.replace("_", " ").replace("-", " ").upper()
        blocks.append(
            {
                "feature": label,
                "headline": f"Get more from {product} with {name}.",
                "body": (summary or f"This update is on `{snapshot.branch}`. Confirm the customer-facing story before sending.")[:800],
                "cta": "Try it now!",
            }
        )
    return {"intro": intro, "features": blocks, "closer": ""}


def _clean_features(raw) -> list[dict]:
    cleaned = []
    rows = raw if isinstance(raw, list) else []
    for item in rows[:4]:
        if not isinstance(item, dict):
            continue
        feature = str(item.get("feature") or "").strip()
        headline = str(item.get("headline") or "").strip()
        body = str(item.get("body") or "").strip()
        if not feature and not headline and not body:
            continue
        words = (headline + " " + body).split()
        if len(words) > 120:
            body = " ".join(body.split()[: max(0, 120 - len(headline.split()))])
        cleaned.append(
            {
                "feature": (feature or "Feature")[:80],
                "headline": headline[:500],
                "body": body[:800],
                "cta": str(item.get("cta") or "Try it now!").strip()[:40] or "Try it now!",
            }
        )
    return cleaned[:4]


def _newsletter_store(raw) -> dict:
    if isinstance(raw, dict):
        intro = str(raw.get("intro") or "").strip()
        closer = str(raw.get("closer") or "").strip()
        features = _clean_features(raw.get("features"))
        return {"intro": intro[:1500], "closer": closer[:400], "features": features}
    if isinstance(raw, list):
        return {"intro": "", "closer": "", "features": _clean_features(raw)}
    return {"intro": "", "closer": "", "features": []}


def newsletter_markdown(payload: dict) -> str:
    data = _newsletter_store(payload)
    parts = []
    if data.get("intro"):
        parts.append(data["intro"].strip())
    for item in data.get("features") or []:
        name = (item.get("feature") or "").strip().upper()
        block = [name] if name else []
        if item.get("headline"):
            block.append(item["headline"].strip())
        if item.get("body"):
            block.append(item["body"].strip())
        if item.get("cta"):
            block.append(item["cta"].strip())
        if block:
            parts.append("\n\n".join(block))
    if data.get("closer"):
        parts.append(data["closer"].strip())
    return "\n\n".join(parts).strip()


def pack_out(row: ReleasePack) -> dict:
    news = _newsletter_store(row.newsletter)
    kind = (row.kind or "").strip() or "pack"
    return {
        "id": row.id,
        "kind": kind,
        "title": row.title,
        "angle": row.angle,
        "internal_update": row.internal_update,
        "whatsapp": row.internal_update,
        "release_notes": row.release_notes,
        "newsletter": news.get("features") or [],
        "newsletter_intro": news.get("intro") or "",
        "newsletter_closer": news.get("closer") or "",
        "newsletter_markdown": newsletter_markdown(news),
        "snapshot_id": row.snapshot_id,
        "branch": row.branch,
        "commit_sha": row.commit_sha,
        "llm_used": row.llm_used,
        "artifacts": row.artifacts if isinstance(getattr(row, "artifacts", None), list) else [],
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def list_packs(db: Session, limit: int = 30) -> list[dict]:
    rows = db.query(ReleasePack).order_by(ReleasePack.id.desc()).limit(limit).all()
    return [pack_out(row) for row in rows]


def get_pack(db: Session, pack_id: int) -> dict | None:
    row = db.query(ReleasePack).filter(ReleasePack.id == pack_id).one_or_none()
    return pack_out(row) if row else None


def _evidence(title: str, angle: str, snapshot, features: list[str]) -> dict:
    return {
        "feature_title": title,
        "features_in_short": angle,
        "angle": angle,
        "product": _product_label(snapshot),
        "indexed_branch": snapshot.branch,
        "indexed_sha": snapshot.commit_sha,
        "compared_to": snapshot.live_base,
        "live_summary": snapshot.live_summary,
        "commits": (snapshot.live_commits or [])[:25],
        "files": (snapshot.live_files or [])[:40],
        "services": features,
        "period": period_for(),
    }


def _scrub_screenshots(notes: str) -> str:
    import re

    text = notes or ""
    parts = re.split(r"(?=📌 )", text)
    out = []
    for part in parts:
        head = part[:80].lower()
        if "background" in head or "faq" in head:
            part = re.sub(r"^\[Screenshot:.*?\]\s*$", "", part, flags=re.I | re.M)
        out.append(part)
    return "".join(out)


def generate_pack(
    db: Session,
    *,
    title: str = "",
    angle: str = "",
    kind: str = "release_notes",
    snapshot_id: int | None = None,
    create_artifacts: bool = False,
) -> dict:
    snapshot = None
    if snapshot_id:
        snapshot = db.query(CodebaseSnapshot).filter(CodebaseSnapshot.id == snapshot_id).one_or_none()
    snapshot = snapshot or latest_snapshot(db)
    if not snapshot:
        raise RuntimeError("Index a branch in Codebase first. PRD and Comms both write against that index.")
    chosen = normalize_kind(kind)
    features = _features_from_files(snapshot.live_files or [])
    heading = title.strip() or (angle.strip().splitlines()[0].strip()[:80] if angle.strip() else f"{_product_label(snapshot)} update")
    whatsapp = _heuristic_whatsapp(heading, angle, snapshot) if chosen == "whatsapp" else ""
    notes = _heuristic_release_notes(heading, angle, snapshot) if chosen == "release_notes" else ""
    news = _heuristic_newsletter(heading, angle, snapshot, features) if chosen == "newsletter" else {"intro": "", "features": [], "closer": ""}
    llm_used = False
    surface = "comms_doc" if chosen in {"release_notes", "newsletter"} else "comms"
    llm = LLMClient(model=model_for(surface))
    if not llm.configured:
        llm = LLMClient()
    if llm.configured:
        cap = 28000 if chosen == "release_notes" else 16000
        evidence = _evidence(title, angle, snapshot, features)
        try:
            generated = llm.complete_json(evidence, system_prompt=PROMPTS[chosen], max_chars=cap, surface=surface, timeout=180)
            if generated.get("title"):
                heading = str(generated["title"]).strip()[:256] or heading
            if chosen == "whatsapp" and generated.get("whatsapp"):
                whatsapp = strip_example_leaks(str(generated["whatsapp"]).strip(), evidence)[:1200]
            elif chosen == "whatsapp" and generated.get("internal_update"):
                whatsapp = strip_example_leaks(str(generated["internal_update"]).strip(), evidence)[:1200]
            if chosen == "release_notes" and generated.get("release_notes"):
                notes = _scrub_screenshots(strip_example_leaks(str(generated["release_notes"]).strip()[:24000], evidence))
            if chosen == "newsletter":
                if generated.get("intro") or generated.get("features"):
                    news = _newsletter_store(generated)
                elif isinstance(generated.get("newsletter"), list):
                    news = _newsletter_store({"intro": generated.get("intro") or "", "features": generated.get("newsletter")})
                news["intro"] = strip_example_leaks(news.get("intro") or "", evidence)
                for block in news.get("features") or []:
                    block["headline"] = strip_example_leaks(block.get("headline") or "", evidence)
                    block["body"] = strip_example_leaks(block.get("body") or "", evidence)
                    block["feature"] = strip_example_leaks(block.get("feature") or "", evidence)
            llm_used = True
        except Exception:
            llm_used = False
    row = ReleasePack(
        title=heading[:256],
        kind=chosen,
        angle=angle.strip()[:8000],
        internal_update=whatsapp,
        release_notes=notes,
        newsletter=news if chosen == "newsletter" else [],
        snapshot_id=snapshot.id,
        branch=snapshot.branch,
        commit_sha=snapshot.commit_sha,
        llm_used=llm_used,
        created_at=now_local().replace(tzinfo=None),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    if create_artifacts and chosen == "release_notes":
        from app.services.feature_artifacts import publish_feature_artifacts

        published = publish_feature_artifacts(
            features_in_short=angle,
            branch=snapshot.branch,
            notes=notes,
        )
        row.artifacts = published
        db.commit()
        db.refresh(row)
    return pack_out(row)
