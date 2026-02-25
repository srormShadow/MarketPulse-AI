"""Data consistency tests around duplicate uploads and integrity guarantees."""

from datetime import date

from sqlalchemy import func, select

from app.models.sales import Sales
from app.models.sku import SKU


def test_sales_row_count_stable_after_duplicate_upload(client, db_session):
    sku_payload = (
        "sku_id,product_name,category,mrp,cost,current_inventory\n"
        "SKU_CONS,Consistency Item,Grocery,100,70,20\n"
    ).encode("utf-8")
    sales_payload = (
        "date,sku_id,units_sold\n"
        "2026-02-20,SKU_CONS,4\n"
    ).encode("utf-8")

    client.post("/upload_csv", files={"file": ("sku_cons.csv", sku_payload, "text/csv")})
    first = client.post("/upload_csv", files={"file": ("sales_cons.csv", sales_payload, "text/csv")})
    before = db_session.scalar(select(func.count()).select_from(Sales))
    second = client.post("/upload_csv", files={"file": ("sales_cons.csv", sales_payload, "text/csv")})
    after = db_session.scalar(select(func.count()).select_from(Sales))

    assert first.status_code == 200
    assert second.status_code == 200
    assert before == 1
    assert after == 1


def test_referential_integrity_remains_intact_for_all_sales(db_session):
    sku = SKU(
        sku_id="SKU_REF",
        product_name="Ref Item",
        category="General",
        mrp=100.0,
        cost=70.0,
        current_inventory=10,
    )
    db_session.add(sku)
    db_session.commit()

    db_session.add(Sales(date=date(2026, 2, 20), sku_id="SKU_REF", units_sold=3))
    db_session.commit()

    total_sales = db_session.scalar(select(func.count()).select_from(Sales))
    matched = db_session.scalar(
        select(func.count())
        .select_from(Sales)
        .join(SKU, Sales.sku_id == SKU.sku_id)
    )

    assert total_sales == matched


def test_no_orphaned_sales_after_sku_delete(db_session):
    sku = SKU(
        sku_id="SKU_ORPHAN",
        product_name="Orphan Check",
        category="General",
        mrp=90.0,
        cost=50.0,
        current_inventory=10,
    )
    db_session.add(sku)
    db_session.commit()

    db_session.add(Sales(date=date(2026, 2, 21), sku_id="SKU_ORPHAN", units_sold=5))
    db_session.commit()

    db_session.delete(sku)
    db_session.commit()

    remaining_sales = db_session.scalar(select(func.count()).select_from(Sales))
    assert remaining_sales == 0
