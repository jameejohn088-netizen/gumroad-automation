"""Automation rule builder API. Triggers/actions outside what the Gumroad API
supports are rejected with an honest message — never faked."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.automation.engine import (
    CONDITION_FIELDS,
    SUPPORTED_ACTIONS,
    SUPPORTED_TRIGGERS,
    UNSUPPORTED,
)
from app.core.deps import get_current_user, get_db
from app.models.models import (
    AutomationAction,
    AutomationCondition,
    AutomationExecution,
    AutomationRule,
    User,
)
from app.schemas.schemas import AutomationRuleCreate, AutomationRuleOut, AutomationRuleUpdate
from app.services import account_service
from app.services.notify_service import log_activity

router = APIRouter(prefix="/automation-rules", tags=["automation"])


def _check_account(db: Session, user: User, account_id: str | None) -> None:
    if account_id and not account_service._get_account(db, user.id, account_id):
        raise HTTPException(status_code=404, detail="Account not found")


def _validate(body_trigger, conditions, actions) -> None:
    if body_trigger not in SUPPORTED_TRIGGERS:
        reason = UNSUPPORTED.get(body_trigger, "unsupported trigger")
        raise HTTPException(status_code=400, detail=f"{reason}")
    for c in conditions or []:
        if c.field not in CONDITION_FIELDS:
            raise HTTPException(status_code=400, detail=f"Unsupported condition: {c.field}")
    for a in actions or []:
        if a.action_type in UNSUPPORTED:
            raise HTTPException(status_code=400,
                                detail=f"{UNSUPPORTED[a.action_type]}")
        if a.action_type not in SUPPORTED_ACTIONS:
            raise HTTPException(status_code=400, detail=f"Unsupported action: {a.action_type}")


def _out(rule: AutomationRule) -> AutomationRuleOut:
    return AutomationRuleOut(
        id=rule.id, name=rule.name, account_id=rule.account_id, trigger=rule.trigger,
        enabled=rule.enabled, dry_run=rule.dry_run,
        max_actions_per_hour=rule.max_actions_per_hour,
        conditions=[{"field": c.field, "operator": c.operator, "value": c.value}
                    for c in rule.conditions],
        actions=[{"action_type": a.action_type, "params": a.params or {}, "order": a.order}
                 for a in sorted(rule.actions, key=lambda x: x.order)],
    )


@router.get("", response_model=list[AutomationRuleOut])
def list_rules(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rules = db.scalars(select(AutomationRule).where(AutomationRule.user_id == user.id)
                       .order_by(AutomationRule.created_at)).all()
    return [_out(r) for r in rules]


@router.post("", response_model=AutomationRuleOut, status_code=201)
def create_rule(body: AutomationRuleCreate, db: Session = Depends(get_db),
                user: User = Depends(get_current_user)):
    _validate(body.trigger, body.conditions, body.actions)
    _check_account(db, user, body.account_id)
    rule = AutomationRule(
        user_id=user.id, account_id=body.account_id, name=body.name,
        trigger=body.trigger, enabled=body.enabled, dry_run=body.dry_run,
        max_actions_per_hour=body.max_actions_per_hour,
    )
    db.add(rule)
    db.flush()
    for c in body.conditions:
        db.add(AutomationCondition(rule_id=rule.id, field=c.field,
                                  operator=c.operator, value=c.value))
    for a in body.actions:
        db.add(AutomationAction(rule_id=rule.id, action_type=a.action_type,
                                params=a.params or {}, order=a.order))
    db.commit()
    db.refresh(rule)
    log_activity(db, "automation.rule_created", user_id=user.id, detail={"name": body.name})
    return _out(rule)


@router.get("/{rule_id}", response_model=AutomationRuleOut)
def get_rule(rule_id: str, db: Session = Depends(get_db),
             user: User = Depends(get_current_user)):
    rule = db.get(AutomationRule, rule_id)
    if not rule or rule.user_id != user.id:
        raise HTTPException(status_code=404, detail="Rule not found")
    return _out(rule)


@router.patch("/{rule_id}", response_model=AutomationRuleOut)
def update_rule(rule_id: str, body: AutomationRuleUpdate, db: Session = Depends(get_db),
                user: User = Depends(get_current_user)):
    rule = db.get(AutomationRule, rule_id)
    if not rule or rule.user_id != user.id:
        raise HTTPException(status_code=404, detail="Rule not found")
    if body.trigger is not None:
        _validate(body.trigger, body.conditions or [], body.actions or [])
        rule.trigger = body.trigger
    if body.account_id is not None:
        _check_account(db, user, body.account_id)
        rule.account_id = body.account_id
    for attr in ("name", "enabled", "dry_run", "max_actions_per_hour"):
        val = getattr(body, attr)
        if val is not None:
            setattr(rule, attr, val)
    if body.conditions is not None:
        _validate(rule.trigger, body.conditions, [])
        for c in rule.conditions:
            db.delete(c)
        for c in body.conditions:
            db.add(AutomationCondition(rule_id=rule.id, field=c.field,
                                      operator=c.operator, value=c.value))
    if body.actions is not None:
        _validate(rule.trigger, [], body.actions)
        for a in rule.actions:
            db.delete(a)
        for a in body.actions:
            db.add(AutomationAction(rule_id=rule.id, action_type=a.action_type,
                                   params=a.params or {}, order=a.order))
    db.commit()
    db.refresh(rule)
    log_activity(db, "automation.rule_updated", user_id=user.id, detail={"rule_id": rule.id})
    return _out(rule)


@router.delete("/{rule_id}")
def delete_rule(rule_id: str, db: Session = Depends(get_db),
                user: User = Depends(get_current_user)):
    rule = db.get(AutomationRule, rule_id)
    if not rule or rule.user_id != user.id:
        raise HTTPException(status_code=404, detail="Rule not found")
    db.delete(rule)
    db.commit()
    return {"ok": True}


@router.get("/{rule_id}/executions")
def rule_executions(rule_id: str, db: Session = Depends(get_db),
                     user: User = Depends(get_current_user),
                     limit: int = 50):
    rule = db.get(AutomationRule, rule_id)
    if not rule or rule.user_id != user.id:
        raise HTTPException(status_code=404, detail="Rule not found")
    rows = db.scalars(select(AutomationExecution).where(
        AutomationExecution.rule_id == rule.id)
        .order_by(AutomationExecution.created_at.desc()).limit(limit)).all()
    return [{"id": e.id, "event_type": e.event_type, "status": e.status,
             "steps": e.steps, "created_at": e.created_at.isoformat() if e.created_at else None}
            for e in rows]
