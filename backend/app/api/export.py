"""CSV export of the user's own sales/product/customer data."""
import csv
import io
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_db, resolve_accounts
from app.models.models import Customer, GumroadAccount, Product, Sale

router = APIRouter(tags=["export"])


def _date_bounds(preset: str, start_date: str | None, end_date: str | None):
    now = datetime.now(timezone.utc)
    start = end = None
    if start_date and end_date:
        try:
            start = datetime.fromisoformat(start_date).replace(tzinfo=timezone.utc)
            end = datetime.fromisoformat(end_date).replace(tzinfo=timezone.utc) + timedelta(days=1)
        except ValueError:
            pass
    if start is None:
        if preset == "week":
            start = now - timedelta(days=7)
        elif preset == "month":
            start = now - timedelta(days=30)
        elif preset == "year":
            start = now - timedelta(days=365)
    return start, end


@router.get("/export/sales.csv")
def export_sales_csv(db: Session = Depends(get_db),
                     accounts: list[GumroadAccount] = Depends(resolve_accounts),
                     preset: str = Query(default="all", pattern="^(week|month|year|all)$"),
                     start_date: str | None = Query(default=None),
                     end_date: str | None = Query(default=None)):
    ids = [a.id for a in accounts]
    start, end = _date_bounds(preset, start_date, end_date)
    q = select(Sale).where(Sale.account_id.in_(ids)) if ids else select(Sale).where(False)
    if start:
        q = q.where(Sale.created_at >= start)
    if end:
        q = q.where(Sale.created_at < end)
    rows = db.scalars(q.order_by(Sale.created_at.desc())).all()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["sale_id", "account_id", "email", "price_cents", "currency",
                "refunded", "disputed", "is_subscription", "gumroad_created_at"])
    for s in rows:
        w.writerow([s.gumroad_id, s.account_id, s.email, s.price_cents, s.currency,
                    s.refunded, s.disputed, s.is_subscription, s.gumroad_created_at])
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=sales.csv"},
    )


@router.get("/export/products.csv")
def export_products_csv(db: Session = Depends(get_db),
                        accounts: list[GumroadAccount] = Depends(resolve_accounts)):
    from sqlalchemy import func
    ids = [a.id for a in accounts]
    products = db.scalars(select(Product).where(
        Product.account_id.in_(ids), Product.deleted.is_(False))).all() if ids else []
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["product_id", "account_id", "name", "price_cents", "currency",
                "permalink", "published", "sales_count", "gross_cents"])
    for p in products:
        agg = db.execute(select(func.coalesce(func.sum(Sale.price_cents), 0),
                                func.count(Sale.id)).where(
            Sale.product_id == p.id)).one()
        w.writerow([p.id, p.account_id, p.name, p.price_cents, p.currency,
                    p.permalink, p.published, agg[1] or 0, agg[0] or 0])
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=products.csv"},
    )


@router.get("/export/customers.csv")
def export_customers_csv(db: Session = Depends(get_db),
                         accounts: list[GumroadAccount] = Depends(resolve_accounts)):
    ids = [a.id for a in accounts]
    rows = db.scalars(select(Customer).where(
        Customer.account_id.in_(ids)).order_by(Customer.created_at.desc())).all() if ids else []
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["customer_id", "account_id", "email", "name", "created_at"])
    for c in rows:
        w.writerow([c.id, c.account_id, c.email, c.name, c.created_at])
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=customers.csv"},
    )
