from __future__ import annotations
import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..db import get_db
from ..dependencies import get_organization_membership
from ..models import Membership, Request, RequestPriority, RequestStatus, SLANotification
from ..schemas import SLAAnalyticsRead, NotificationRead

router = APIRouter(prefix="/organizations/{organization_id}", tags=["analytics"])

def _range(start: datetime | None, end: datetime | None):
    if start is None and end is None:
        return None, None
    now=datetime.now(timezone.utc)
    return start or now-timedelta(days=30), end or now

@router.get("/analytics", response_model=SLAAnalyticsRead)
def analytics(
    organization_id: uuid.UUID,
    membership: Annotated[Membership, Depends(get_organization_membership)],
    session: Annotated[Session, Depends(get_db)],
    start: datetime | None = None,
    end: datetime | None = None,
):
    start,end=_range(start,end)
    filters=[Request.organization_id==organization_id]
    if start: filters.append(Request.created_at>=start)
    if end: filters.append(Request.created_at<=end)
    requests=list(session.scalars(select(Request).where(*filters)))
    counts={s.value:0 for s in RequestStatus}; priorities={p.value:0 for p in RequestPriority}; workload={}
    healthy=warning=breached=0
    for r in requests:
        counts[r.status.value]+=1; priorities[r.priority.value]+=1
        workload[str(r.assignee_id) if r.assignee_id else "unassigned"]=workload.get(str(r.assignee_id) if r.assignee_id else "unassigned",0)+1
        state=r.sla_state
        if state=="warning": warning+=1
        elif state=="breached": breached+=1
        else: healthy+=1
    total=healthy+warning+breached
    names={m.user_id:m.user.full_name for m in session.scalars(select(Membership).where(Membership.organization_id==organization_id))}
    assignees=[{"assignee_id":k,"name":names.get(uuid.UUID(k),"Unassigned") if k!="unassigned" else "Unassigned","count":v} for k,v in workload.items()]
    return SLAAnalyticsRead(open_requests=sum(counts[s] for s in ("open","in_progress","waiting")),healthy_requests=healthy,warning_requests=warning,breached_requests=breached,breach_rate_pct=round(breached/total*100,2) if total else 0.0,by_status=counts,by_priority=priorities,by_assignee=assignees,period_start=start,period_end=end)

@router.get("/notifications", response_model=list[NotificationRead])
def notifications(
    organization_id: uuid.UUID,
    membership: Annotated[Membership, Depends(get_organization_membership)],
    session: Annotated[Session, Depends(get_db)],
):
    rows=session.execute(select(SLANotification,Request.title).join(Request,Request.id==SLANotification.request_id).where(SLANotification.organization_id==organization_id).order_by(SLANotification.created_at.desc()).limit(50))
    return [NotificationRead.model_validate(n,from_attributes=True).model_copy(update={"title":title,"message":f"{n.stage.replace('_',' ').title()} SLA {n.kind}"}) for n,title in rows]
