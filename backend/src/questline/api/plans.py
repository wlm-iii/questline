from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from questline.api.dependencies import AccessDep, SessionDep, SettingsDep
from questline.api.generations import trip_snapshot
from questline.models import Message, Place, Plan, Trip
from questline.operations import OperationsRequest
from questline.providers.errors import ProviderUnavailable
from questline.providers.routes import EstimateRouter, Router
from questline.providers.selection import router_for_settings
from questline.schemas import PlanAccept, PlanContent, PlanRead, PlanResult, PlanUpdate, Schema
from questline.services.persistence import same_trip_member
from questline.services.plan_edits import (
    InvalidOperation,
    ResolutionOption,
    apply_operations,
    only_follow_through,
    resolution_options,
)
from questline.services.questline_plan import compose, decisions_from

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
    for node in body.content.graph.nodes:
        await same_trip_member(session, node.owner_member_id, trip.id)
        for message_id in node.source_message_ids:
            message = await session.get(Message, message_id)
            if message is None or message.trip_id != trip.id:
                raise HTTPException(422, "Evidence does not belong to the trip")
        if node.role == "stop":
            try:
                place_id = UUID(node.id)
            except ValueError as exc:
                raise HTTPException(422, "Stop IDs must be local waypoint UUIDs") from exc
            place = await session.get(Place, place_id)
            if place is None or place.trip_id != trip.id or place.google_place_id != node.place_id:
                raise HTTPException(422, "Stop does not match a waypoint in this trip")
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


class ResolutionRequest(Schema):
    node_id: str


class ResolutionResult(Schema):
    options: list[ResolutionOption]


@router.post("/{plan_id}/operations", response_model=PlanResult)
async def apply_plan_operations(
    plan_id: UUID,
    body: OperationsRequest,
    session: SessionDep,
    settings: SettingsDep,
    access: AccessDep,
):
    plan = await session.get(Plan, plan_id)
    if plan is None:
        raise HTTPException(404, "Plan not found")
    access.check_trip(plan.trip_id)
    if plan.revision != body.revision:
        raise HTTPException(409, "Plan changed; fetch the latest revision before editing")
    trip = await session.get(Trip, plan.trip_id)
    assert trip is not None
    snapshot = await trip_snapshot(session, trip)
    previous, preset = plan.content, plan.budget_preset
    try:
        decisions = apply_operations(snapshot, decisions_from(previous), body.operations)
    except InvalidOperation as exc:
        raise HTTPException(422, str(exc)) from None
    follow_through = only_follow_through(body.operations)
    router: Router
    try:
        router = EstimateRouter() if follow_through else router_for_settings(settings)
    except ProviderUnavailable:
        router = EstimateRouter()
    # Recompute before taking the trip lock; routing calls can take seconds. The reads above
    # take no row locks, and the revision is checked again under the lock below.
    if follow_through:
        content = PlanContent.model_validate(previous)
        for node in content.graph.nodes:
            if node.id in decisions.owner:
                owner = decisions.owner[node.id]
                node.owner_member_id = UUID(owner) if owner else None
            node.notes = decisions.notes.get(node.id, node.notes)
    else:
        content = await compose(
            snapshot,
            decisions,
            budget_preset=preset,
            router=router,
            previous=previous,
        )
    plan, trip = await lock_plan(plan_id, session, access)
    if plan.revision != body.revision:
        raise HTTPException(409, "Plan changed; fetch the latest revision before editing")
    plan.content = content.model_dump(mode="json")
    plan.revision += 1
    if not follow_through:
        plan.status = "draft"
        plan.accepted_at = None
    trip.revision += 1
    await session.commit()
    return PlanResult(plan=PlanRead.model_validate(plan))


@router.post("/{plan_id}/resolutions", response_model=ResolutionResult)
async def resolve(plan_id: UUID, body: ResolutionRequest, session: SessionDep, access: AccessDep):
    plan = await session.get(Plan, plan_id)
    if plan is None:
        raise HTTPException(404, "Plan not found")
    access.check_trip(plan.trip_id)
    trip = await session.get(Trip, plan.trip_id)
    assert trip is not None
    snapshot = await trip_snapshot(session, trip)
    try:
        options = resolution_options(snapshot, decisions_from(plan.content), body.node_id)
    except InvalidOperation as exc:
        raise HTTPException(422, str(exc)) from None
    return ResolutionResult(options=options)
