from app.db.base import Base
from app.models import Festival, HealthPing, SKU, Sales
from app.services.festival_seed import seed_festivals_if_empty


def init_db() -> None:
    from app.db.session import SessionLocal, engine

    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_festivals_if_empty(db)
