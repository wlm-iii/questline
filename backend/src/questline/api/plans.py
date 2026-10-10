from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from questline.api.dependencies import AccessDep, SessionDep
from questline.models import Plan, Trip
from questline.schemas import PlanAccept, PlanRead, PlanResult, PlanUpdate

router = APIRouter(prefix="/plans", tags=["plans"])


async def lock_plan(plan_id: UUID, session: AsyncSession, access) -> tuple[Plan, Trip]:
    plan = await session.get(Plan, plan_id)
    if plan is None:
        raise HTTPException(404, "Plan not found")
    access.check_trip(plan.trip_id)
    trip = await session.get(Trip, plan.trip_id, with_for_update=True)
    assert trip is not None
    # Refresh after obtaining trip lock; another writer may have committed while we waited.
    await session.refresh(plan, with_for_update=True)
    return plan, trip


@router.get("/{plan_id}", response_model=PlanResult)
async def get_plan(plan_id: UUID, session: SessionDep, access: AccessDep):
    plan = await session.get(Plan, plan_id)
    if plan is None:
        raise HTTPException(404, "Plan not found")
    access.check_trip(plan.trip_id)
    return PlanResult(plan=PlanRead.model_validate(plan))


@router.patch("/{plan_id}", response_model=PlanResult)
async def edit_plan(plan_id: UUID, body: PlanUpdate, session: SessionDep, access: AccessDep):
    access.require_service()  # Full replacement is tooling-only, never a browser write path.
    plan, trip = await lock_plan(plan_id, session, access)
    if plan.revision != body.revision:
        raise HTTPException(409, "Plan changed; fetch the latest revision before editing")
    plan.content = body.content.model_dump(mode="json")
    plan.revision += 1
    plan.status = "draft"
    plan.accepted_at = None
    trip.revision += 1
    await session.commit()
    return PlanResult(plan=PlanRead.model_validate(plan))


@router.post("/{plan_id}/accept", response_model=PlanResult)
async def accept_plan(plan_id: UUID, body: PlanAccept, session: SessionDep, access: AccessDep):
    plan, trip = await lock_plan(plan_id, session, access)
    if plan.revision != body.revision:
        raise HTTPException(409, "Plan changed; fetch the latest revision before accepting")
    plan.status = "accepted"
    plan.accepted_at = datetime.now(UTC)
    plan.revision += 1
    trip.revision += 1
    await session.commit()
    return PlanResult(plan=PlanRead.model_validate(plan))
