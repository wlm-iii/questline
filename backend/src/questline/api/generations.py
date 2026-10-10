from typing import Annotated
from uuid import UUID

import psycopg
from fastapi import APIRouter, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from questline.api.dependencies import AccessDep, SessionDep, SettingsDep
from questline.models import Member, Message, Plan, PlanGeneration, Trip
from questline.schemas import (
    GenerationCreate,
    GenerationRead,
    GenerationResult,
    MemberRead,
    MessageRead,
)

router = APIRouter(tags=["generations"])


@router.post("/trips/{trip_id}/plan-generations", response_model=GenerationResult, status_code=202)
async def create_generation(
    trip_id: UUID,
    body: GenerationCreate,
    session: SessionDep,
    settings: SettingsDep,
    request: Request,
    access: AccessDep,
    idempotency_key: Annotated[str, Header(min_length=1, max_length=200)],
):
    access.check_trip(trip_id)
    if settings.planner_provider != "fake":
        raise HTTPException(503, "Gemini provider is not implemented yet")
    trip = await session.get(Trip, trip_id, with_for_update=True)
    if trip is None:
        raise HTTPException(404, "Trip not found")
    existing = await session.scalar(
        select(PlanGeneration).where(
            PlanGeneration.trip_id == trip_id, PlanGeneration.idempotency_key == idempotency_key
        )
    )
    if existing:
        if existing.budget_preset != body.budget_preset:
            raise HTTPException(409, "Idempotency key was used with a different request")
        return GenerationResult(generation=await generation_response(existing, session))
    active = await session.scalar(
        select(PlanGeneration).where(
            PlanGeneration.trip_id == trip_id, PlanGeneration.status.in_(["queued", "running"])
        )
    )
    if active:
        if active.budget_preset != body.budget_preset:
            raise HTTPException(
                409,
                {
                    "code": "plan_in_progress",
                    "message": "A different preset is building",
                    "generation_id": str(active.id),
                },
            )
        return GenerationResult(generation=await generation_response(active, session))
    messages = (
        await session.scalars(
            select(Message).where(Message.trip_id == trip_id).order_by(Message.sent_at, Message.id)
        )
    ).all()
    if not messages:
        raise HTTPException(422, "Import a transcript before generating a plan")
    if sum(len(m.text) for m in messages) > settings.max_transcript_chars:
        raise HTTPException(413, "Transcript exceeds the generation limit")
    members = (await session.scalars(select(Member).where(Member.trip_id == trip_id))).all()
    generation = PlanGeneration(
        trip_id=trip_id,
        idempotency_key=idempotency_key,
        transcript_revision=trip.revision,
        snapshot={
            "messages": [MessageRead.model_validate(m).model_dump(mode="json") for m in messages],
            "members": [MemberRead.model_validate(m).model_dump(mode="json") for m in members],
            "places": [],
            "votes": [],
            "budget_preset": body.budget_preset,
            "timezone": trip.timezone,
        },
        budget_preset=body.budget_preset,
        previous_plan_id=trip.current_plan_id,
    )
    session.add(generation)
    trip.revision += 1
    await session.flush()
    connection = await session.connection()
    raw = await connection.get_raw_connection()
    driver = raw.driver_connection
    assert isinstance(driver, psycopg.AsyncConnection)
    await request.app.state.generate_task.configure(
        connection=driver, lock=f"trip:{trip_id}"
    ).defer_async(generation_id=str(generation.id))
    await session.commit()
    return GenerationResult(generation=await generation_response(generation, session))


async def generation_response(generation: PlanGeneration, session: AsyncSession) -> GenerationRead:
    result = GenerationRead.model_validate(generation)
    result.plan_id = await session.scalar(
        select(Plan.id).where(Plan.generation_id == generation.id)
    )
    return result


@router.get("/plan-generations/{generation_id}", response_model=GenerationResult)
async def get_generation(generation_id: UUID, session: SessionDep, access: AccessDep):
    generation = await session.get(PlanGeneration, generation_id)
    if generation is None:
        raise HTTPException(404, "Generation not found")
    access.check_trip(generation.trip_id)
    return GenerationResult(generation=await generation_response(generation, session))
