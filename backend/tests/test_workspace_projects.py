from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base
from app.models import JiraIssue
from app.api.routers.issues import list_issues
from app.config import Settings


def test_custom_project_filter():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as db:
        db.add_all([JiraIssue(issue_key="SHOP-1", summary="Checkout", status="Open", issue_type="Task"),
                    JiraIssue(issue_key="OPS-1", summary="Operations", status="Open", issue_type="Task")])
        db.commit()
        result = list_issues(board="SHOP", compact=True, db=db)
        assert result["total"] == 1
        assert result["issues"][0]["issue_key"] == "SHOP-1"
    engine.dispose()


def test_no_personal_connection_defaults():
    # Inspect declared defaults, without reading the operator's environment.
    for name in ("jira_projects", "gdrive_domain", "marketing_sheet_id", "codebase_path"):
        assert Settings.model_fields[name].default == ""
