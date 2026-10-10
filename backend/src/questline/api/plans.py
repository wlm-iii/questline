from uuid import UUID

from fastapi import APIRouter, HTTPException

from questline.api.dependencies import SessionDep
from questline.models import Plan
from questline.schemas import PlanAccept, PlanRead, PlanUpdate

router = APIRouter(prefix="/plans", tags=["plans"])


@router.get("/{plan_id}", response_model=PlanRead)
async def get_plan(plan_id: UUID, session: SessionDep):
    plan = await session.get(Plan, plan_id)
    if plan is None:
        raise HTTPException(404, "Plan not found")
    return plan


@router.patch("/{plan_id}", response_model=PlanRead)
async def edit_plan(plan_id: UUID, body: PlanUpdate, session: SessionDep):
    plan = await session.get(Plan, plan_id, with_for_update=True)
    if plan is None:
        raise HTTPException(404, "Plan not found")
    if plan.revision != body.revision:
        raise HTTPException(409, "Plan changed; fetch the latest revision before editing")
    plan.content = body.content.model_dump(mode="json")
    plan.revision += 1
    # Editing an accepted plan requires accepting the new version again.
    plan.status = "draft"
    await session.commit()
    return plan


@router.post("/{plan_id}/accept", response_model=PlanRead)
async def accept_plan(plan_id: UUID, body: PlanAccept, session: SessionDep):
    plan = await session.get(Plan, plan_id, with_for_update=True)
    if plan is None:
        raise HTTPException(404, "Plan not found")
    if plan.revision != body.revision:
        raise HTTPException(409, "Plan changed; fetch the latest revision before accepting")
    plan.status = "accepted"
    plan.revision += 1
    await session.commit()
    return plan
