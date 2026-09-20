"""Publish Revamped WhatsApp Analytics_Release Note with Luna copy and How-to stills.

Does not send Cliq.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.clients.llm import model_for
from app.services.gdocs import (
    apply_doc_theme,
    create_release_doc,
    generate_doc_json,
    trash_file,
    upload_howto_screenshots,
    write_release_notes_doc,
)
from app.services.gdrive import drive_configured
from app.services.howto_stills import render_whatsapp_analytics_stills
from app.services.pdf_notes import drive_doc_name

PREVIOUS_DOC = "1VKlUTm269hBAyLiKDkBCeOa0pLlOqFvj_rZLp1nA6SI"
FEATURES = """
Revamped WhatsApp Analytics — see WhatsApp campaign delivery, reads, replies, and at-risk leads in Activate
Delivery funnel — Sent → Delivered → Read → Responded
Summary cards — total sent, delivery rate, read rate, response rate, with change versus the previous window
Date range — 24 hours, 7 days, 30 days, or a custom range
Template performance — sent, delivered, read, and responded for each template
Engagement health — Active, Degraded, Likely Blocked, Likely Spam
Blocked leads — search at-risk leads, see confidence, export CSV
Daily trend — sent, delivered, read, and responded over time
Multi-campaign — the same WhatsApp Analytics view across campaigns
""".strip()
NOTES = """
Client-facing Activate feature. Open Campaign Analytics or Analytics, then WhatsApp Analytics (collapsible; Template Analytics nested under it).
Customers use it to judge whether WhatsApp campaigns are reaching leads and where delivery or engagement drops.
Lead with the outcome: you can see delivery, reads, and at-risk leads in one place.
Do not mention APIs, Redis, Postgres, sync jobs, or engineering.
Audience is Clients. Teams are campaign managers and operations.
""".strip()


def main() -> int:
    if not drive_configured():
        print("Drive is not configured.")
        return 1
    print("model", model_for("comms_doc"))
    stills = render_whatsapp_analytics_stills()
    screenshots = upload_howto_screenshots(stills, "release/2026-09-03")
    print("uploaded stills", list(screenshots))
    doc = generate_doc_json(
        title="Revamped WhatsApp Analytics",
        features_in_short=FEATURES,
        branch="release/2026-09-03",
        notes=NOTES,
        screenshot_names=["8.1", "8.2", "8.3", "8.4"],
    )
    Path("/tmp/whatsapp_analytics_doc.json").write_text(json.dumps(doc, indent=2), encoding="utf-8")
    name = drive_doc_name(str((doc.get("meta") or {}).get("feature_name") or doc.get("title") or "Revamped WhatsApp Analytics"))
    print("drive name", name)
    print("title", doc.get("title"), "audience", (doc.get("meta") or {}).get("audience"))
    if PREVIOUS_DOC:
        trash_file(PREVIOUS_DOC)
    doc_id, url = create_release_doc(name, "2026-09")
    apply_doc_theme(doc_id)
    write_release_notes_doc(doc_id, doc, screenshots)
    print("Open:", url)
    print("doc_id:", doc_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
