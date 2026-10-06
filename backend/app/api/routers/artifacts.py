"""Feature artifact list + create (PDF → Drive)."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
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


def _sidecar(pdf: Path) -> dict:
    try:
        meta = json.loads(pdf.with_suffix(".json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return meta if isinstance(meta, dict) else {}


def _drive_url(meta: dict) -> str:
    url = str(meta.get("url") or meta.get("drive_url") or "").strip()
    return url if url.startswith("https://") else ""


def list_artifact_rows() -> list[dict]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    # A PDF whose local copy was removed stays listed while its sidecar keeps the Drive link.
    entries = {path.stem: path for path in ARTIFACT_DIR.glob("*.json") if not path.name.endswith(".opus.json")}
    entries.update({path.stem: path for path in ARTIFACT_DIR.glob("*.pdf")})
    rows: list[dict] = []
    for stem, path in sorted(entries.items(), key=lambda item: item[1].stat().st_mtime, reverse=True):
        local = path.suffix == ".pdf"
        meta = _sidecar(path)
        url = _drive_url(meta)
        if not local and not url:
            continue
        fmt = "brief"
        feature = stem
        if stem.lower().endswith("_brief"):
            feature = stem[: -len("_Brief")] if stem.endswith("_Brief") else stem[: -len("_brief")]
            fmt = "brief"
        elif stem.lower().endswith("_deck"):
            feature = stem[: -len("_Deck")] if stem.endswith("_Deck") else stem[: -len("_deck")]
            fmt = "deck"
        rows.append(
            {
                "feature": str(meta.get("title") or feature).strip() or feature,
                "format": str(meta.get("format") or fmt),
                "filename": f"{stem}.pdf",
                "pdf_path": str(path) if local else "",
                "local": local,
                "file_id": str(meta.get("file_id") or ""),
                "url": url,
                "branch": str(meta.get("branch") or ""),
                "created_at": None,
            }
        )
    return rows[:60]


@router.get("/artifacts")
def artifacts_list(db: Session = Depends(get_db)):
    return {
        "artifacts": list_artifact_rows(),
        "codebase": snapshot_out(db, live=False, include_modules=False),
        "drive_configured": drive_configured(),
    }


@router.post("/artifacts")
def artifacts_create(body: ArtifactBody, db: Session = Depends(get_db)):
    feature = (body.feature or "").strip()
    if not feature:
        raise HTTPException(status_code=400, detail="Feature name is required.")
    notes = (body.notes or "").strip()
    fmt = "deck" if (body.format or "").strip().lower() == "deck" else "brief"
    snap = snapshot_out(db, live=False, include_modules=False)
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
    if path.suffix.lower() != ".pdf":
        raise HTTPException(status_code=404, detail="Artifact PDF not found")
    if path.is_file():
        return FileResponse(path, media_type="application/pdf", filename=path.name)
    url = _drive_url(_sidecar(path))
    if url:
        return RedirectResponse(url, status_code=307)
    raise HTTPException(status_code=404, detail="Artifact PDF not found")
