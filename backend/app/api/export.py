"""CSV export of the user's own sales data."""
import csv
import io

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_db, resolve_accounts
from app.models.models import GumroadAccount, Sale

router = APIRouter(tags=["export"])


@router.get("/export/sales.csv")
def export_sales_csv(db: Session = Depends(get_db),
                     accounts: list[GumroadAccount] = Depends(resolve_accounts)):
    ids = [a.id for a in accounts]
    rows = db.scalars(select(Sale).where(Sale.account_id.in_(ids))
                      .order_by(Sale.created_at.desc())).all() if ids else []
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
