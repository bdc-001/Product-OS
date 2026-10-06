"""Create a one-off styled Google Doc in the shared folder.

Run from backend/:
  .venv/bin/python scripts/test_gdocs.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.gdocs import apply_doc_theme, create_release_doc, heuristic_doc_json, write_release_notes_doc
from app.services.gdrive import drive_configured


def main() -> int:
    if not drive_configured():
        print("Drive is not configured. Set GDRIVE_KEY_FILE and GDRIVE_FOLDER_ID.")
        return 1
    try:
        doc_id, url = create_release_doc("TEST — Entity Dashboard format", "_test")
        apply_doc_theme(doc_id)
        write_release_notes_doc(
            doc_id,
            heuristic_doc_json(
                "Entity Dashboard",
                "Entity Dashboard — inspect conversation entities\nRelated records stay in context",
                "release/2026-09-03",
            ),
            screenshots={},
        )
    except Exception as exc:
        print(exc)
        return 1
    print("Open:", url)
    print("doc_id:", doc_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
