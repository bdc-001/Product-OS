from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import JiraIssue
from app.services.standup import answer_command


def test_search_returns_why_and_count():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine, future=True)()
    db.add(
        JiraIssue(
            issue_key="AC-42",
            summary="Checkout retry banner",
            status="Staging",
            assignee="Lovelesh",
            extra_json={},
            comments_json=[],
            changelog_json=[],
        )
    )
    db.commit()
    result = answer_command(None, "checkout banner", db)
    assert result["searched"] == 1
    assert result["items"]
    assert any("AC-42" in (item.get("issue_key") or "") for item in result["items"])
    assert any(item.get("why") for item in result["items"])
