from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.release_view import release_workspace

router = APIRouter()


@router.get("/releases")
def releases(db: Session = Depends(get_db)):
    return release_workspace(db)
