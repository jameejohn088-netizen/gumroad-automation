"""Dashboard aggregates — real numbers from the local DB, never mock data."""
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import get_db, resolve_accounts
from app.models.models import Customer, GumroadAccount, Product, Sale, Subscriber
from app.schemas.schemas import DashboardOut

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard", response_model=DashboardOut)
def dashboard(db: Session = Depends(get_db),
              accounts: list[GumroadAccount] = Depends(resolve_accounts)):
    ids = [a.id for a in accounts]
    if not ids:
        return DashboardOut(revenue_cents=0, sales_count=0, customers_count=0,
                            subscribers_count=0, products_count=0, recent_sales=[])
    revenue = db.scalar(select(func.coalesce(func.sum(Sale.price_cents), 0)).where(
        Sale.account_id.in_(ids), Sale.refunded.is_(False))) or 0
    sales_count = db.scalar(select(func.count(Sale.id)).where(Sale.account_id.in_(ids))) or 0
    customers_count = db.scalar(select(func.count(Customer.id)).where(
        Customer.account_id.in_(ids))) or 0
    subscribers_count = db.scalar(select(func.count(Subscriber.id)).where(
        Subscriber.account_id.in_(ids))) or 0
    products_count = db.scalar(select(func.count(Product.id)).where(
        Product.account_id.in_(ids), Product.deleted.is_(False))) or 0
    recent = db.scalars(select(Sale).where(Sale.account_id.in_(ids))
                        .order_by(Sale.created_at.desc()).limit(10)).all()
    recent_sales = [{
        "id": s.id, "account_id": s.account_id, "email": s.email,
        "price_cents": s.price_cents, "currency": s.currency,
        "refunded": s.refunded, "created_at": s.created_at.isoformat() if s.created_at else None,
    } for s in recent]
    return DashboardOut(
        revenue_cents=revenue, sales_count=sales_count, customers_count=customers_count,
        subscribers_count=subscribers_count, products_count=products_count,
        recent_sales=recent_sales,
    )
