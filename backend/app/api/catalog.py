"""Catalog browsing: products, sales, customers, subscribers, licenses,
memberships (derived). All queries scoped to the user's own accounts."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.deps import get_db, pagination, resolve_accounts
from app.models.models import (
    Customer,
    GumroadAccount,
    License,
    Product,
    Sale,
    Subscriber,
)
from app.schemas.schemas import PageOut

router = APIRouter(tags=["catalog"])


def _page(query, db: Session, page: int, per_page: int, model) -> PageOut:
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.scalars(query.offset((page - 1) * per_page).limit(per_page)).all()
    items = []
    for r in rows:
        d = {c.key: getattr(r, c.key) for c in model.__table__.columns
             if c.key != "raw"}
        for k, v in list(d.items()):
            if hasattr(v, "isoformat"):
                d[k] = v.isoformat()
        items.append(d)
    return PageOut(items=items, total=total, page=page, per_page=per_page)


@router.get("/products")
def list_products(q: str | None = Query(default=None),
                  db: Session = Depends(get_db),
                  accounts: list[GumroadAccount] = Depends(resolve_accounts),
                  pg: tuple[int, int] = Depends(pagination)):
    page, per_page = pg
    ids = [a.id for a in accounts]
    query = select(Product).where(Product.account_id.in_(ids))
    if q:
        query = query.where(or_(Product.name.ilike(f"%{q}%"),
                                Product.gumroad_id.ilike(f"%{q}%")))
    query = query.order_by(Product.created_at.desc())
    return _page(query, db, page, per_page, Product)


@router.get("/sales")
def list_sales(q: str | None = Query(default=None),
               db: Session = Depends(get_db),
               accounts: list[GumroadAccount] = Depends(resolve_accounts),
               pg: tuple[int, int] = Depends(pagination)):
    page, per_page = pg
    ids = [a.id for a in accounts]
    query = select(Sale).where(Sale.account_id.in_(ids))
    if q:
        query = query.where(or_(Sale.email.ilike(f"%{q}%"),
                                Sale.gumroad_id.ilike(f"%{q}%")))
    query = query.order_by(Sale.created_at.desc())
    return _page(query, db, page, per_page, Sale)


@router.get("/customers")
def list_customers(q: str | None = Query(default=None),
                   db: Session = Depends(get_db),
                   accounts: list[GumroadAccount] = Depends(resolve_accounts),
                   pg: tuple[int, int] = Depends(pagination)):
    page, per_page = pg
    ids = [a.id for a in accounts]
    query = select(Customer).where(Customer.account_id.in_(ids))
    if q:
        query = query.where(Customer.email.ilike(f"%{q}%"))
    query = query.order_by(Customer.total_spent_cents.desc())
    return _page(query, db, page, per_page, Customer)


@router.get("/subscribers")
def list_subscribers(q: str | None = Query(default=None),
                     db: Session = Depends(get_db),
                     accounts: list[GumroadAccount] = Depends(resolve_accounts),
                     pg: tuple[int, int] = Depends(pagination)):
    page, per_page = pg
    ids = [a.id for a in accounts]
    query = select(Subscriber).where(Subscriber.account_id.in_(ids))
    if q:
        query = query.where(Subscriber.email.ilike(f"%{q}%"))
    query = query.order_by(Subscriber.created_at.desc())
    return _page(query, db, page, per_page, Subscriber)


@router.get("/licenses")
def list_licenses(q: str | None = Query(default=None),
                  db: Session = Depends(get_db),
                  accounts: list[GumroadAccount] = Depends(resolve_accounts),
                  pg: tuple[int, int] = Depends(pagination)):
    page, per_page = pg
    ids = [a.id for a in accounts]
    query = select(License).where(License.account_id.in_(ids))
    if q:
        query = query.where(or_(License.key.ilike(f"%{q}%"),
                                License.email.ilike(f"%{q}%")))
    query = query.order_by(License.created_at.desc())
    return _page(query, db, page, per_page, License)


@router.get("/memberships")
def list_memberships(db: Session = Depends(get_db),
                     accounts: list[GumroadAccount] = Depends(resolve_accounts),
                     pg: tuple[int, int] = Depends(pagination)):
    """DERIVED: subscribers joined to subscription products.

    The Gumroad API has no memberships endpoint — this is computed from
    subscription products + subscribers (documented limitation)."""
    page, per_page = pg
    ids = [a.id for a in accounts]
    sub_products = db.scalars(select(Product).where(
        Product.account_id.in_(ids), Product.is_subscription.is_(True))).all()
    prod_ids = [p.id for p in sub_products]
    prod_by_id = {p.id: p for p in sub_products}
    query = select(Subscriber).where(Subscriber.account_id.in_(ids))
    if prod_ids:
        query = query.where(Subscriber.product_id.in_(prod_ids))
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.scalars(query.order_by(Subscriber.created_at.desc())
                      .offset((page - 1) * per_page).limit(per_page)).all()
    items = []
    for s in rows:
        p = prod_by_id.get(s.product_id) if s.product_id else None
        items.append({
            "id": s.id, "account_id": s.account_id, "email": s.email,
            "status": s.status,
            "product_id": s.product_id,
            "product_name": p.name if p else None,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        })
    return PageOut(items=items, total=total, page=page, per_page=per_page)
