"""Competitor radar, parity, pricing, and market sensing APIs."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Competitor, ParityCapability
from app.services import competitive as svc
from app.services.jobs import enqueue, job_out

router = APIRouter(tags=["competitors"])


class CompetitorBody(BaseModel):
    name: str = ""
    slug: str = ""
    aliases: list[str] = Field(default_factory=list)
    website: str = ""
    changelog_url: str = ""
    blog_url: str = ""
    pricing_url: str = ""
    g2_url: str = ""
    notes: str = ""
    active: bool | None = None


class AffectsBody(BaseModel):
    affects_roadmap: str = "watch"


class ParityCellBody(BaseModel):
    competitor_slug: str
    level: str = "unknown"


class CapabilityBody(BaseModel):
    name: str
    epic_key: str = ""
    notes: str = ""


@router.get("/competitors")
def competitors_home(db: Session = Depends(get_db)):
    svc.ensure_seeded(db)
    rivals = [svc.competitor_out(c) for c in db.query(Competitor).order_by(Competitor.name.asc()).all()]
    digest = svc.digest(db)
    return {
        "competitors": rivals,
        "digest": digest,
        "counts": {
            "rivals": len(rivals),
            "shipped": len(digest.get("shipped") or []),
            "pricing": len(digest.get("pricing") or []),
            "ask_eng": len(digest.get("ask_eng") or []),
        },
    }


@router.post("/competitors")
def competitors_create(body: CompetitorBody, db: Session = Depends(get_db)):
    try:
        row = svc.upsert_competitor(db, body.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return svc.competitor_out(row)


@router.patch("/competitors/{competitor_id}")
def competitors_update(competitor_id: int, body: CompetitorBody, db: Session = Depends(get_db)):
    try:
        row = svc.upsert_competitor(db, body.model_dump(exclude_unset=True), competitor_id=competitor_id)
    except ValueError as exc:
        raise HTTPException(status_code=404 if "not found" in str(exc) else 400, detail=str(exc)) from exc
    return svc.competitor_out(row)


@router.delete("/competitors/{competitor_id}")
def competitors_delete(competitor_id: int, db: Session = Depends(get_db)):
    row = db.query(Competitor).filter(Competitor.id == competitor_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="competitor not found")
    row.active = False
    db.commit()
    return {"ok": True, "id": competitor_id}


@router.get("/competitors/digest")
def competitors_digest(db: Session = Depends(get_db)):
    return svc.digest(db)


@router.get("/competitors/parity")
def competitors_parity(db: Session = Depends(get_db)):
    return svc.parity_matrix(db)


@router.post("/competitors/parity/capabilities")
def competitors_add_capability(body: CapabilityBody, db: Session = Depends(get_db)):
    name = (body.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name is required")
    svc.ensure_seeded(db)
    existing = db.query(ParityCapability).filter(ParityCapability.name == name).first()
    if existing:
        raise HTTPException(status_code=400, detail="capability already exists")
    row = ParityCapability(
        name=name[:256],
        source="manual",
        epic_key=(body.epic_key or "")[:32],
        notes=(body.notes or "")[:2000],
        coverage={},
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id, "name": row.name, "epic_key": row.epic_key, "coverage": row.coverage or {}}


@router.post("/competitors/parity/{capability_id}")
def competitors_parity_cell(capability_id: int, body: ParityCellBody, db: Session = Depends(get_db)):
    try:
        row = svc.set_parity_cell(db, capability_id, body.competitor_slug, body.level)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"id": row.id, "name": row.name, "coverage": row.coverage or {}}


@router.get("/competitors/pricing")
def competitors_pricing(db: Session = Depends(get_db)):
    return svc.pricing_history(db)


@router.get("/competitors/market")
def competitors_market(category: str | None = None, db: Session = Depends(get_db)):
    if category and category not in {"industry", "compliance", "integration"}:
        raise HTTPException(status_code=400, detail="category must be industry|compliance|integration")
    return svc.market_overview(db, category=category)


@router.post("/competitors/market/{signal_id}/affects")
def competitors_market_affects(signal_id: int, body: AffectsBody, db: Session = Depends(get_db)):
    try:
        row = svc.set_market_affects(db, signal_id, body.affects_roadmap)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return svc.market_signal_out(row)


@router.post("/competitors/refresh")
def competitors_refresh(db: Session = Depends(get_db)):
    def work(session, set_step):
        set_step("competitive", {"ok": True, "status": "running"})
        result = svc.refresh_all(session)
        set_step(
            "competitive",
            {
                "ok": True,
                "status": "done",
                "competitors": len(result.get("competitors") or []),
                "market": len(result.get("market") or []),
            },
        )
        return result

    job = enqueue(db, "competitive_refresh", work)
    return JSONResponse(status_code=202, content=job_out(job))


@router.get("/competitors/signals")
def competitors_signals(view: str = "news", q: str = "", rival: int = 0, focus: str = "all", snapshots: bool = False, tag: str = "all", offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)):
    if view not in {"news", "features", "ai"}: raise HTTPException(400, "Unknown view")
    return svc.signal_feed(db, view, q, rival, focus, offset, limit, snapshots, tag)


@router.post("/competitors/signals/{signal_id}/ticket")
def news_ticket(signal_id: int, db: Session = Depends(get_db)):
    from app.services.news_ticket import prepare_ticket
    try: return prepare_ticket(db, signal_id)
    except ValueError as exc: raise HTTPException(404, str(exc)) from exc


@router.post("/competitors/ai/refresh")
def refresh_ai(db: Session = Depends(get_db)):
    from app.models import MarketWatch
    def work(session, set_step):
        svc.ensure_seeded(session)
        results = []
        for watch in session.query(MarketWatch).filter(MarketWatch.category == "ai", MarketWatch.active.is_(True)):
            set_step("ai", {"status": "running", "source": watch.name})
            results.append(svc._fetch_watch(session, watch))
        failed = [r for r in results if r.get("error")]
        created = sum(int(r.get("signals_created") or 0) for r in results)
        # One flaky feed must not fail the whole Refresh AI job.
        ok = len(failed) < len(results)
        error = ""
        if failed and ok:
            names = ", ".join(r.get("watch") or "source" for r in failed[:4])
            error = f"Refreshed {created} items; {len(failed)} source(s) unavailable ({names})."
        elif failed and not ok:
            error = "All AI news sources failed. Retry in a minute."
        set_step("ai", {"status": "done", "ok": ok, "created": created, "failed": len(failed)})
        return {"ok": ok, "sources": results, "created": created, "failed": len(failed), "error": error}
    return JSONResponse(status_code=202, content=job_out(enqueue(db, "ai-news", work)))
