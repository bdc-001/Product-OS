from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Insight, PipelineRun

router = APIRouter()


@router.get("/insights")
def list_insights(db: Session = Depends(get_db)):
    latest_run = db.query(PipelineRun).order_by(PipelineRun.id.desc()).first()
    if not latest_run:
        return {"insights": []}
    insights = db.query(Insight).filter(Insight.run_id == latest_run.id).all()
    return {
        "insights": [
            {
                "id": i.id,
                "type": i.type,
                "title": i.title,
                "description": i.description,
                "action": i.action,
                "confidence": i.confidence,
                "issue_key": i.issue_key,
                "why": i.why,
                "sources": i.sources,
            }
            for i in insights
        ]
    }


@router.get("/runs")
def list_runs(db: Session = Depends(get_db)):
    runs = db.query(PipelineRun).order_by(PipelineRun.id.desc()).limit(20).all()
    return {
        "runs": [
            {
                "id": r.id,
                "status": r.status,
                "trigger": r.trigger,
                "jira_count": r.jira_count,
                "cliq_count": r.cliq_count,
                "relevant_cliq_count": r.relevant_cliq_count,
                "change_count": r.change_count,
                "insight_count": r.insight_count,
                "error": r.error,
                "started_at": r.started_at.isoformat() if r.started_at else None,
                "finished_at": r.finished_at.isoformat() if r.finished_at else None,
            }
            for r in runs
        ]
    }
