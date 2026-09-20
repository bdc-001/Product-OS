from datetime import timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import CliqMessage
from app.services.cliq_briefing import heuristic_cliq_briefing
from app.services.time_window import briefing_window


def test_heuristic_cliq_briefing_does_not_scan_old_messages():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine, future=True)()
    start, end = briefing_window().as_naive()
    db.add(CliqMessage(chat_id="old", chat_name="Sense", message_id="1", sender="A", message="ancient ping", timestamp=start - timedelta(days=40)))
    db.add(CliqMessage(chat_id="now", chat_name="Sense", message_id="2", sender="A", sender_id="60031811823", message="today in the window", timestamp=start + timedelta(minutes=5)))
    db.commit()
    payload = heuristic_cliq_briefing(db, start, end)
    blob = str(payload)
    assert "ancient ping" not in blob
    db.close()
    engine.dispose()
