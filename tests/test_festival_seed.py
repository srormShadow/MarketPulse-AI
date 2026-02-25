from sqlalchemy import func, select

from app.models.festival import Festival
from app.services.festival_seed import seed_festivals_if_empty


def test_festival_seed_inserts_when_empty(db_session):
    seed_festivals_if_empty(db_session)

    count = db_session.scalar(select(func.count()).select_from(Festival))
    assert count == 3


def test_festival_seed_is_idempotent(db_session):
    seed_festivals_if_empty(db_session)
    seed_festivals_if_empty(db_session)

    rows = db_session.scalars(select(Festival)).all()
    names = sorted(row.festival_name for row in rows)
    assert len(rows) == 3
    assert names == ["Christmas", "Diwali", "Pongal"]
