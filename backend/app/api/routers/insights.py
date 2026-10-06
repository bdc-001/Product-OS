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

