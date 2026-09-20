"""Feature artifact list + create (PDF → Drive)."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session

from app.api.common import ArtifactBody
from app.database import get_db
from app.services.codebase import snapshot_out
from app.services.feature_artifacts import ARTIFACT_DIR, publish_feature_artifacts
from app.services.gdrive import drive_configured
from app.services.jobs import enqueue, job_out

router = APIRouter()


def _safe_name(name: str) -> str:
    raw = Path(name or "").name
    if not raw or raw.startswith(".") or "/" in raw or "\\" in raw:
        raise HTTPException(status_code=400, detail="Invalid filename")
    return raw


def list_artifact_rows() -> list[dict]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    for path in sorted(ARTIFACT_DIR.glob("*.pdf"), key=lambda p: p.stat().st_mtime, reverse=True):
        stem = path.stem
        fmt = "brief"
        feature = stem
        if stem.lower().endswith("_brief"):
            feature = stem[: -len("_Brief")] if stem.endswith("_Brief") else stem[: -len("_brief")]
            fmt = "brief"
        elif stem.lower().endswith("_deck"):
            feature = stem[: -len("_Deck")] if stem.endswith("_Deck") else stem[: -len("_deck")]
            fmt = "deck"
        meta = {}
        json_path = path.with_suffix(".json")
        if json_path.is_file():
            try:
                import json

                meta = json.loads(json_path.read_text(encoding="utf-8")) or {}
            except Exception:
                meta = {}
        rows.append(
            {
                "feature": str(meta.get("title") or feature).strip() or feature,
                "format": str(meta.get("format") or fmt),
                "filename": path.name,
                "pdf_path": str(path),
                "file_id": str(meta.get("file_id") or ""),
                "url": str(meta.get("url") or meta.get("drive_url") or ""),
                "branch": str(meta.get("branch") or ""),
                "created_at": None,
            }
        )
    return rows[:60]


@router.get("/artifacts")
def artifacts_list(db: Session = Depends(get_db)):
    return {
        "artifacts": list_artifact_rows(),
        "codebase": snapshot_out(db),
        "drive_configured": drive_configured(),
    }


@router.post("/artifacts")
def artifacts_create(body: ArtifactBody, db: Session = Depends(get_db)):
    feature = (body.feature or "").strip()
    if not feature:
        raise HTTPException(status_code=400, detail="Feature name is required.")
    notes = (body.notes or "").strip()
    fmt = "deck" if (body.format or "").strip().lower() == "deck" else "brief"
    snap = snapshot_out(db)
    branch = str(snap.get("indexed_branch") or snap.get("branch") or "").strip()

    def work(session, set_step):
        set_step("artifact", {"ok": True, "status": "running", "feature": feature, "format": fmt})
        published = publish_feature_artifacts(
            features_in_short=feature,
            branch=branch,
            items=[{"lead": feature}],
            notes=notes,
            formats=(fmt,),
        )
        # Stash drive ids onto companion json if present
        for row in published:
            pdf = Path(str(row.get("pdf_path") or ""))
            if pdf.is_file():
                json_path = pdf.with_suffix(".json")
                try:
                    import json

                    data = json.loads(json_path.read_text(encoding="utf-8")) if json_path.is_file() else {}
                    if not isinstance(data, dict):
                        data = {}
                    data["file_id"] = row.get("file_id") or data.get("file_id") or ""
                    data["url"] = row.get("url") or data.get("url") or ""
                    data["branch"] = branch
                    data["format"] = fmt
                    data["title"] = feature
                    json_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
                except Exception:
                    pass
        set_step("artifact", {"ok": True, "status": "done", "feature": feature, "count": len(published)})
        return {"ok": True, "artifacts": published, "drive_configured": drive_configured()}

    job = enqueue(db, "artifact", work)
    return JSONResponse(status_code=202, content=job_out(job))


@router.get("/artifacts/files/{filename}")
def artifact_file(filename: str):
    name = _safe_name(filename)
    path = ARTIFACT_DIR / name
    if not path.is_file() or path.suffix.lower() != ".pdf":
        raise HTTPException(status_code=404, detail="Artifact PDF not found")
    return FileResponse(path, media_type="application/pdf", filename=path.name)
