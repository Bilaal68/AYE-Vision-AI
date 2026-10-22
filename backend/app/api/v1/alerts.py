"""
Alert management API endpoints.

Provides alert listing with advanced filtering, statistics, lifecycle
management (acknowledge, resolve, false-positive, escalate), and
a recent-alerts feed for real-time dashboards.
"""

from __future__ import annotations

import math
import uuid
from datetime import datetime, date, timedelta, timezone
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, or_, select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db_session
from app.exceptions import (
    AuthorizationError,
    NotFoundError,
    ValidationError,
)
from app.middleware.auth import JWTBearer, TokenPayload
from app.models.alert import Alert, AlertEscalation, AlertStatus
from app.models.camera import Camera
from app.models.rule import RuleSeverity, RuleType
from app.models.user import User, UserRole
from app.schemas.common import ErrorResponse, SuccessResponse

logger = structlog.stdlib.get_logger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class AlertResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    camera_id: uuid.UUID
    camera_name: str = "Camera"
    zone_id: uuid.UUID | None = None
    rule_id: uuid.UUID
    rule_name: str | None = None
    alert_type: str
    type: str = ""
    severity: str
    title: str
    description: str | None = None
    message: str = ""
    snapshot_path: str | None = None
    snapshot_url: str | None = None
    thumbnail_url: str | None = None
    video_clip_path: str | None = None
    video_clip_url: str | None = None
    metadata_json: dict | None = None
    details: dict | None = None
    metadata: dict | None = None
    status: str
    acknowledged_by: uuid.UUID | None = None
    acknowledged_at: datetime | None = None
    resolved_by: uuid.UUID | None = None
    resolved_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AlertCreateRequest(BaseModel):
    camera_id: uuid.UUID
    rule_id: uuid.UUID | None = None
    zone_id: uuid.UUID | None = None
    alert_type: str = Field(default="intrusion_detection")
    severity: str = Field(default="critical")
    title: str = Field(..., min_length=1, max_length=512)
    description: str | None = None
    snapshot_path: str | None = None
    metadata_json: dict | None = None


class SimulateAlertRequest(BaseModel):
    camera_id: uuid.UUID | None = None
    rule_type: str = Field(default="intrusion_detection")
    severity: str = Field(default="critical")
    title: str | None = None
    description: str | None = None


class ResolveRequest(BaseModel):
    notes: str | None = Field(default=None, max_length=2000, description="Resolution notes")


class EscalateRequest(BaseModel):
    escalated_to: uuid.UUID = Field(..., description="User ID to escalate to")
    reason: str | None = Field(default=None, max_length=2000, description="Reason for escalation")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_current_user(
    token: TokenPayload = Depends(JWTBearer()),
    db: AsyncSession = Depends(get_db_session),
) -> User:
    result = await db.execute(
        select(User).where(User.id == uuid.UUID(token.sub), User.is_active.is_(True))
    )
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found or deactivated.")
    return user


def _require_operator(user: User) -> None:
    """Raise 403 if the user is below operator role."""
    allowed = {UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN, UserRole.MANAGER, UserRole.OPERATOR}
    if user.role not in allowed:
        raise AuthorizationError(message="Operator role or higher is required.")


def _alert_to_response(alert: Alert, camera_name: str | None = None) -> dict:
    raw_type = alert.alert_type.value if isinstance(alert.alert_type, RuleType) else str(alert.alert_type)
    raw_sev = alert.severity.value if isinstance(alert.severity, RuleSeverity) else str(alert.severity)
    raw_status = alert.status.value if isinstance(alert.status, AlertStatus) else str(alert.status)

    if not camera_name:
        if hasattr(alert, "camera") and alert.camera:
            camera_name = alert.camera.name
        else:
            camera_name = "Camera"

    msg = alert.title or alert.description or raw_type.replace("_", " ").title()
    snap_url = alert.snapshot_path or f"/api/v1/cameras/{alert.camera_id}/snapshot"
    meta = alert.metadata_json or {}

    rule_name = None
    if hasattr(alert, "rule") and alert.rule:
        rt = alert.rule.rule_type
        rule_name = rt.value if hasattr(rt, "value") else str(rt)

    return AlertResponse(
        id=alert.id,
        org_id=alert.org_id,
        camera_id=alert.camera_id,
        camera_name=camera_name,
        zone_id=alert.zone_id,
        rule_id=alert.rule_id,
        rule_name=rule_name,
        alert_type=raw_type,
        type=raw_type,
        severity=raw_sev,
        title=alert.title or msg,
        description=alert.description,
        message=msg,
        snapshot_path=alert.snapshot_path,
        snapshot_url=snap_url,
        thumbnail_url=f"/api/v1/cameras/{alert.camera_id}/thumbnail",
        video_clip_path=alert.video_clip_path,
        video_clip_url=alert.video_clip_path,
        metadata_json=meta,
        details=meta,
        metadata=meta,
        status=raw_status,
        acknowledged_by=alert.acknowledged_by,
        acknowledged_at=alert.acknowledged_at,
        resolved_by=alert.resolved_by,
        resolved_at=alert.resolved_at,
        created_at=alert.created_at,
        updated_at=alert.updated_at,
    ).model_dump(mode="json")


# ---------------------------------------------------------------------------
# GET / - List alerts (paginated, filterable)
# ---------------------------------------------------------------------------


@router.get(
    "",
    response_model=SuccessResponse,
    summary="List alerts (paginated, filterable)",
)
async def list_alerts(
    severity: str | None = Query(None, description="Filter by severity (single or comma-separated)"),
    alert_type: str | None = Query(None, description="Filter by alert type"),
    type: str | None = Query(None, description="Alias for alert_type"),
    camera_id: uuid.UUID | None = Query(None),
    alert_status: str | None = Query(None, alias="status", description="Filter by status"),
    start_date: datetime | None = Query(None, description="Start date (inclusive)"),
    end_date: datetime | None = Query(None, description="End date (inclusive)"),
    date_from: datetime | None = Query(None, description="Alias for start_date"),
    date_to: datetime | None = Query(None, description="Alias for end_date"),
    search: str | None = Query(None, description="Search keyword"),
    sort_by: str | None = Query("created_at"),
    sort_dir: str | None = Query("desc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=500),
    limit: int | None = Query(None, description="Alias for page_size"),
    user: User = Depends(_get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """Return a paginated list of alerts for the user's organization."""
    if limit is not None:
        page_size = limit

    effective_type = alert_type or type
    effective_start = start_date or date_from
    effective_end = end_date or date_to

    query = (
        select(Alert, Camera.name.label("camera_name"))
        .outerjoin(Camera, Alert.camera_id == Camera.id)
        .where(Alert.org_id == user.org_id)
    )

    if severity:
        sevs = [s.strip().lower() for s in severity.split(",") if s.strip()]
        if len(sevs) == 1:
            try:
                query = query.where(Alert.severity == RuleSeverity(sevs[0]))
            except ValueError:
                pass
        elif len(sevs) > 1:
            valid_sevs = []
            for s in sevs:
                try:
                    valid_sevs.append(RuleSeverity(s))
                except ValueError:
                    pass
            if valid_sevs:
                query = query.where(Alert.severity.in_(valid_sevs))

    if effective_type:
        try:
            query = query.where(Alert.alert_type == RuleType(effective_type))
        except ValueError:
            query = query.where(Alert.alert_type == effective_type)

    if camera_id:
        query = query.where(Alert.camera_id == camera_id)

    if alert_status:
        try:
            query = query.where(Alert.status == AlertStatus(alert_status))
        except ValueError:
            query = query.where(Alert.status == alert_status)

    if effective_start:
        query = query.where(Alert.created_at >= effective_start)
    if effective_end:
        query = query.where(Alert.created_at <= effective_end)

    if search:
        search_kw = f"%{search.strip()}%"
        query = query.where(
            or_(
                Alert.title.ilike(search_kw),
                Alert.description.ilike(search_kw),
                Camera.name.ilike(search_kw),
            )
        )

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    # Sorting
    sort_column = Alert.created_at
    if sort_by == "severity":
        sort_column = Alert.severity
    elif sort_by in ("type", "alert_type"):
        sort_column = Alert.alert_type

    if sort_dir and sort_dir.lower() == "asc":
        query = query.order_by(sort_column.asc())
    else:
        query = query.order_by(sort_column.desc())

    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    rows = result.all()

    alert_responses = []
    for row in rows:
        alert_obj = row[0]
        cam_name = row[1] if len(row) > 1 else "Camera"
        alert_responses.append(_alert_to_response(alert_obj, cam_name))

    return {
        "status": "success",
        "data": alert_responses,
        "items": alert_responses,
        "meta": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": math.ceil(total / page_size) if page_size else 0,
        },
    }


# ---------------------------------------------------------------------------
# GET /stats - Alert statistics
# ---------------------------------------------------------------------------


@router.get(
    "/stats",
    response_model=SuccessResponse,
    summary="Get alert statistics",
)
async def alert_stats(
    start_date: datetime | None = Query(None),
    end_date: datetime | None = Query(None),
    user: User = Depends(_get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """Return alert counts grouped by severity, type, and status."""
    base_filter = [Alert.org_id == user.org_id]
    if start_date:
        base_filter.append(Alert.created_at >= start_date)
    if end_date:
        base_filter.append(Alert.created_at <= end_date)

    # Counts by severity
    severity_q = (
        select(Alert.severity, func.count().label("count"))
        .where(and_(*base_filter))
        .group_by(Alert.severity)
    )
    severity_result = await db.execute(severity_q)
    by_severity = {
        (row.severity.value if isinstance(row.severity, RuleSeverity) else row.severity): row.count
        for row in severity_result.all()
    }

    # Counts by type
    type_q = (
        select(Alert.alert_type, func.count().label("count"))
        .where(and_(*base_filter))
        .group_by(Alert.alert_type)
    )
    type_result = await db.execute(type_q)
    by_type = {
        (row.alert_type.value if isinstance(row.alert_type, RuleType) else row.alert_type): row.count
        for row in type_result.all()
    }

    # Counts by status
    status_q = (
        select(Alert.status, func.count().label("count"))
        .where(and_(*base_filter))
        .group_by(Alert.status)
    )
    status_result = await db.execute(status_q)
    by_status = {
        (row.status.value if isinstance(row.status, AlertStatus) else row.status): row.count
        for row in status_result.all()
    }

    # Total count
    total_q = select(func.count()).where(and_(*base_filter)).select_from(Alert)
    total = (await db.execute(total_q)).scalar() or 0

    return {
        "status": "success",
        "data": {
            "total": total,
            "by_severity": by_severity,
            "by_type": by_type,
            "by_status": by_status,
        },
    }


# ---------------------------------------------------------------------------
# GET /recent - Last 20 alerts for real-time feed
# ---------------------------------------------------------------------------


@router.get(
    "/recent",
    response_model=SuccessResponse,
    summary="Get most recent alerts",
)
async def recent_alerts(
    limit: int = Query(20, ge=1, le=50),
    user: User = Depends(_get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """Return the most recent alerts for real-time dashboard feed."""
    query = (
        select(Alert)
        .where(Alert.org_id == user.org_id)
        .order_by(Alert.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(query)
    alerts = result.scalars().all()

    return {
        "status": "success",
        "data": [_alert_to_response(a) for a in alerts],
    }


# ---------------------------------------------------------------------------
# GET /{alert_id} - Get alert details
# ---------------------------------------------------------------------------


@router.get(
    "/{alert_id}",
    response_model=SuccessResponse,
    summary="Get alert details with related info",
    responses={404: {"model": ErrorResponse}},
)
async def get_alert(
    alert_id: uuid.UUID,
    user: User = Depends(_get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """Retrieve a single alert with its escalation history."""
    result = await db.execute(
        select(Alert).where(Alert.id == alert_id, Alert.org_id == user.org_id)
    )
    alert = result.scalars().first()
    if not alert:
        raise NotFoundError(resource="Alert", identifier=str(alert_id))

    # Fetch escalations
    esc_result = await db.execute(
        select(AlertEscalation).where(AlertEscalation.alert_id == alert_id).order_by(AlertEscalation.created_at.desc())
    )
    escalations = esc_result.scalars().all()
    escalation_data = [
        {
            "id": str(e.id),
            "escalated_to": str(e.escalated_to),
            "escalated_by": str(e.escalated_by),
            "reason": e.reason,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in escalations
    ]

    alert_data = _alert_to_response(alert)
    alert_data["escalations"] = escalation_data

    return {
        "status": "success",
        "data": alert_data,
    }


# ---------------------------------------------------------------------------
# POST / - Create alert manually
# ---------------------------------------------------------------------------


@router.post(
    "",
    response_model=SuccessResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create alert manually",
)
async def create_alert_endpoint(
    body: AlertCreateRequest,
    user: User = Depends(_get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """Create a new alert and dispatch it."""
    # Verify camera
    cam_result = await db.execute(
        select(Camera).where(Camera.id == body.camera_id, Camera.org_id == user.org_id)
    )
    camera = cam_result.scalars().first()
    if not camera:
        raise NotFoundError(resource="Camera", identifier=str(body.camera_id))

    rule_id = body.rule_id
    if not rule_id:
        from app.models.rule import Rule
        r_result = await db.execute(
            select(Rule).where(Rule.camera_id == camera.id, Rule.org_id == user.org_id).limit(1)
        )
        existing_rule = r_result.scalars().first()
        if existing_rule:
            rule_id = existing_rule.id
        else:
            new_rule = Rule(
                id=uuid.uuid4(),
                org_id=user.org_id,
                camera_id=camera.id,
                rule_type=RuleType.INTRUSION_DETECTION,
                severity=RuleSeverity.CRITICAL,
                is_active=True,
            )
            db.add(new_rule)
            await db.flush()
            rule_id = new_rule.id

    try:
        at = RuleType(body.alert_type)
    except ValueError:
        at = RuleType.INTRUSION_DETECTION

    try:
        sev = RuleSeverity(body.severity)
    except ValueError:
        sev = RuleSeverity.CRITICAL

    alert = Alert(
        id=uuid.uuid4(),
        org_id=user.org_id,
        camera_id=camera.id,
        rule_id=rule_id,
        zone_id=body.zone_id,
        alert_type=at,
        severity=sev,
        title=body.title,
        description=body.description,
        snapshot_path=body.snapshot_path or f"/api/v1/cameras/{camera.id}/snapshot",
        metadata_json=body.metadata_json or {"source": "manual", "confidence": 0.95},
        status=AlertStatus.NEW,
    )
    db.add(alert)
    await db.flush()

    try:
        from app.services.alert_dispatcher import dispatch
        await dispatch(alert)
    except Exception as exc:
        logger.warning("Alert dispatch error", error=str(exc))

    return {
        "status": "success",
        "data": _alert_to_response(alert, camera.name),
        "message": "Alert created and dispatched successfully.",
    }


# ---------------------------------------------------------------------------
# POST /simulate - Simulate real-time incident/alert
# ---------------------------------------------------------------------------


@router.post(
    "/simulate",
    response_model=SuccessResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Simulate a real-time incident alert",
)
async def simulate_alert_endpoint(
    body: SimulateAlertRequest,
    user: User = Depends(_get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """Trigger an immediate real-time alert for testing and monitoring."""
    camera = None
    if body.camera_id:
        cam_result = await db.execute(
            select(Camera).where(Camera.id == body.camera_id, Camera.org_id == user.org_id)
        )
        camera = cam_result.scalars().first()

    if not camera:
        cam_result = await db.execute(
            select(Camera).where(Camera.org_id == user.org_id, Camera.is_active.is_(True)).limit(1)
        )
        camera = cam_result.scalars().first()

    if not camera:
        raise NotFoundError(message="No active camera available to trigger alert on.")

    # Find or create a matching rule
    from app.models.rule import Rule
    rule_res = await db.execute(
        select(Rule).where(Rule.camera_id == camera.id, Rule.org_id == user.org_id).limit(1)
    )
    rule = rule_res.scalars().first()
    if not rule:
        rule = Rule(
            id=uuid.uuid4(),
            org_id=user.org_id,
            camera_id=camera.id,
            rule_type=RuleType.INTRUSION_DETECTION,
            severity=RuleSeverity.CRITICAL,
            is_active=True,
        )
        db.add(rule)
        await db.flush()

    try:
        at = RuleType(body.rule_type)
    except ValueError:
        at = RuleType.INTRUSION_DETECTION

    try:
        sev = RuleSeverity(body.severity)
    except ValueError:
        sev = RuleSeverity.CRITICAL

    type_label = at.value.replace("_", " ").title()
    title = body.title or f"{type_label} Triggered on {camera.name}"
    desc = body.description or f"Real-time {type_label.lower()} event detected with 96% AI confidence."

    alert = Alert(
        id=uuid.uuid4(),
        org_id=user.org_id,
        camera_id=camera.id,
        rule_id=rule.id,
        alert_type=at,
        severity=sev,
        title=title,
        description=desc,
        snapshot_path=f"/api/v1/cameras/{camera.id}/snapshot",
        metadata_json={
            "simulated": True,
            "confidence": 0.96,
            "target": "Person",
            "camera_location": camera.location_description or "Main Campus",
            "detected_at": datetime.now(timezone.utc).isoformat(),
        },
        status=AlertStatus.NEW,
    )
    db.add(alert)
    await db.flush()

    try:
        from app.services.alert_dispatcher import dispatch
        await dispatch(alert)
    except Exception as exc:
        logger.warning("Simulated alert dispatch error", error=str(exc))

    return {
        "status": "success",
        "data": _alert_to_response(alert, camera.name),
        "message": f"Simulated {sev.value.upper()} alert '{title}' created successfully.",
    }


# ---------------------------------------------------------------------------
# POST /{alert_id}/acknowledge - Acknowledge alert
# ---------------------------------------------------------------------------


@router.post(
    "/{alert_id}/acknowledge",
    response_model=SuccessResponse,
    summary="Acknowledge an alert",
    responses={404: {"model": ErrorResponse}},
)
@router.patch(
    "/{alert_id}/acknowledge",
    response_model=SuccessResponse,
    summary="Acknowledge an alert (PATCH alias)",
    responses={404: {"model": ErrorResponse}},
)
@router.put(
    "/{alert_id}/acknowledge",
    response_model=SuccessResponse,
    summary="Acknowledge an alert (PUT alias)",
    responses={404: {"model": ErrorResponse}},
)
async def acknowledge_alert(
    alert_id: uuid.UUID,
    user: User = Depends(_get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """Mark an alert as acknowledged. Requires operator role or above."""
    _require_operator(user)

    result = await db.execute(
        select(Alert).where(Alert.id == alert_id, Alert.org_id == user.org_id)
    )
    alert = result.scalars().first()
    if not alert:
        raise NotFoundError(resource="Alert", identifier=str(alert_id))

    if alert.status != AlertStatus.NEW:
        raise ValidationError(message=f"Cannot acknowledge alert with status '{alert.status.value}'. Only 'new' alerts can be acknowledged.")

    alert.status = AlertStatus.ACKNOWLEDGED
    alert.acknowledged_by = user.id
    alert.acknowledged_at = datetime.now(timezone.utc)
    db.add(alert)
    await db.flush()

    logger.info("Alert acknowledged", alert_id=str(alert.id), user_id=str(user.id))

    return {
        "status": "success",
        "data": _alert_to_response(alert),
        "message": "Alert acknowledged successfully.",
    }


# ---------------------------------------------------------------------------
# POST /{alert_id}/resolve - Resolve alert
# ---------------------------------------------------------------------------


@router.post(
    "/{alert_id}/resolve",
    response_model=SuccessResponse,
    summary="Resolve an alert with notes",
    responses={404: {"model": ErrorResponse}},
)
async def resolve_alert(
    alert_id: uuid.UUID,
    body: ResolveRequest | None = None,
    user: User = Depends(_get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """Mark an alert as resolved with optional notes. Requires operator role or above."""
    _require_operator(user)

    result = await db.execute(
        select(Alert).where(Alert.id == alert_id, Alert.org_id == user.org_id)
    )
    alert = result.scalars().first()
    if not alert:
        raise NotFoundError(resource="Alert", identifier=str(alert_id))

    if alert.status in (AlertStatus.RESOLVED, AlertStatus.FALSE_POSITIVE):
        raise ValidationError(message=f"Alert is already '{alert.status.value}'.")

    alert.status = AlertStatus.RESOLVED
    alert.resolved_by = user.id
    alert.resolved_at = datetime.now(timezone.utc)

    # Store resolution notes in metadata
    if body and body.notes:
        existing_meta = alert.metadata_json or {}
        existing_meta["resolution_notes"] = body.notes
        alert.metadata_json = existing_meta

    db.add(alert)
    await db.flush()

    logger.info("Alert resolved", alert_id=str(alert.id), user_id=str(user.id))

    return {
        "status": "success",
        "data": _alert_to_response(alert),
        "message": "Alert resolved successfully.",
    }


# ---------------------------------------------------------------------------
# POST /{alert_id}/false-positive - Mark as false positive
# ---------------------------------------------------------------------------


@router.post(
    "/{alert_id}/false-positive",
    response_model=SuccessResponse,
    summary="Mark alert as false positive",
    responses={404: {"model": ErrorResponse}},
)
async def mark_false_positive(
    alert_id: uuid.UUID,
    user: User = Depends(_get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """Mark an alert as a false positive. Any authenticated user can mark."""
    result = await db.execute(
        select(Alert).where(Alert.id == alert_id, Alert.org_id == user.org_id)
    )
    alert = result.scalars().first()
    if not alert:
        raise NotFoundError(resource="Alert", identifier=str(alert_id))

    alert.status = AlertStatus.FALSE_POSITIVE
    alert.resolved_by = user.id
    alert.resolved_at = datetime.now(timezone.utc)

    existing_meta = alert.metadata_json or {}
    existing_meta["false_positive_marked_by"] = str(user.id)
    alert.metadata_json = existing_meta

    db.add(alert)
    await db.flush()

    logger.info("Alert marked as false positive", alert_id=str(alert.id), user_id=str(user.id))

    return {
        "status": "success",
        "data": _alert_to_response(alert),
        "message": "Alert marked as false positive.",
    }


# ---------------------------------------------------------------------------
# POST /{alert_id}/escalate - Escalate alert
# ---------------------------------------------------------------------------


@router.post(
    "/{alert_id}/escalate",
    response_model=SuccessResponse,
    summary="Escalate alert to another user",
    responses={404: {"model": ErrorResponse}},
)
async def escalate_alert(
    alert_id: uuid.UUID,
    body: EscalateRequest,
    user: User = Depends(_get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """Escalate an alert to another user within the organization."""
    result = await db.execute(
        select(Alert).where(Alert.id == alert_id, Alert.org_id == user.org_id)
    )
    alert = result.scalars().first()
    if not alert:
        raise NotFoundError(resource="Alert", identifier=str(alert_id))

    # Verify the target user exists and belongs to the same org
    target_result = await db.execute(
        select(User).where(
            User.id == body.escalated_to,
            User.org_id == user.org_id,
            User.is_active.is_(True),
        )
    )
    target_user = target_result.scalars().first()
    if not target_user:
        raise NotFoundError(resource="User", identifier=str(body.escalated_to))

    # Cannot escalate to yourself
    if body.escalated_to == user.id:
        raise ValidationError(message="Cannot escalate an alert to yourself.")

    escalation = AlertEscalation(
        alert_id=alert.id,
        escalated_to=body.escalated_to,
        escalated_by=user.id,
        reason=body.reason,
    )
    db.add(escalation)

    alert.status = AlertStatus.ESCALATED
    db.add(alert)
    await db.flush()

    logger.info(
        "Alert escalated",
        alert_id=str(alert.id),
        escalated_to=str(body.escalated_to),
        escalated_by=str(user.id),
    )

    return {
        "status": "success",
        "data": _alert_to_response(alert),
        "message": f"Alert escalated to user {target_user.full_name}.",
    }


# ---------------------------------------------------------------------------
# POST /batch-acknowledge - Batch acknowledge alerts
# ---------------------------------------------------------------------------


class BatchAlertRequest(BaseModel):
    alert_ids: list[uuid.UUID] = Field(..., min_length=1, max_length=500)


@router.post(
    "/batch-acknowledge",
    response_model=SuccessResponse,
    summary="Batch acknowledge multiple alerts",
)
async def batch_acknowledge(
    body: BatchAlertRequest,
    user: User = Depends(_get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """Acknowledge multiple alerts at once. Requires operator role or above."""
    _require_operator(user)

    result = await db.execute(
        select(Alert).where(
            Alert.id.in_(body.alert_ids),
            Alert.org_id == user.org_id,
            Alert.status == AlertStatus.NEW,
        )
    )
    alerts = result.scalars().all()

    now = datetime.now(timezone.utc)
    count = 0
    for alert in alerts:
        alert.status = AlertStatus.ACKNOWLEDGED
        alert.acknowledged_by = user.id
        alert.acknowledged_at = now
        db.add(alert)
        count += 1

    await db.flush()
    logger.info("Batch acknowledge", count=count, user_id=str(user.id))

    return {
        "status": "success",
        "data": {"acknowledged_count": count},
        "message": f"{count} alert(s) acknowledged successfully.",
    }


# ---------------------------------------------------------------------------
# POST /batch-resolve - Batch resolve alerts
# ---------------------------------------------------------------------------


@router.post(
    "/batch-resolve",
    response_model=SuccessResponse,
    summary="Batch resolve multiple alerts",
)
async def batch_resolve(
    body: BatchAlertRequest,
    user: User = Depends(_get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """Resolve multiple alerts at once. Requires operator role or above."""
    _require_operator(user)

    result = await db.execute(
        select(Alert).where(
            Alert.id.in_(body.alert_ids),
            Alert.org_id == user.org_id,
            Alert.status.notin_([AlertStatus.RESOLVED, AlertStatus.FALSE_POSITIVE]),
        )
    )
    alerts = result.scalars().all()

    now = datetime.now(timezone.utc)
    count = 0
    for alert in alerts:
        alert.status = AlertStatus.RESOLVED
        alert.resolved_by = user.id
        alert.resolved_at = now
        db.add(alert)
        count += 1

    await db.flush()
    logger.info("Batch resolve", count=count, user_id=str(user.id))

    return {
        "status": "success",
        "data": {"resolved_count": count},
        "message": f"{count} alert(s) resolved successfully.",
    }
