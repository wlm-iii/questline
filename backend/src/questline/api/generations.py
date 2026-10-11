from collections.abc import Sequence
from typing import Annotated, Any
from uuid import UUID

import psycopg
from fastapi import APIRouter, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from questline.api.dependencies import AccessDep, SessionDep, SettingsDep
from questline.models import Member, Message, Place, Plan, PlanGeneration, Trip, Vote
from questline.persistence_schemas import PlaceRead, VoteRead
from questline.providers.selection import planner_for_settings
from questline.schemas import (
    GenerationCreate,
    GenerationRead,
    GenerationResult,
    MemberRead,
    MessageRead,
    TripRead,
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
    planner_for_settings(settings)  # Missing provider configuration fails before enqueuing.
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
    snapshot = await trip_snapshot(session, trip, messages)
    previous = await session.get(Plan, trip.current_plan_id) if trip.current_plan_id else None
    generation = PlanGeneration(
        trip_id=trip_id,
        idempotency_key=idempotency_key,
        transcript_revision=trip.revision,
        snapshot={
            **snapshot,
            "budget_preset": body.budget_preset,
            "previous_plan": previous.content if previous else None,
        },
        budget_preset=body.budget_preset,
        requested_by=access.member.id if access.member else None,
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


async def trip_snapshot(
    session: AsyncSession, trip: Trip, messages: Sequence[Message] | None = None
) -> dict[str, Any]:
    """Messages, members, places with tallies, votes, and trip context, as planner input."""
    if messages is None:
        messages = (
            await session.scalars(
                select(Message)
                .where(Message.trip_id == trip.id)
                .order_by(Message.sent_at, Message.id)
            )
        ).all()
    members = (await session.scalars(select(Member).where(Member.trip_id == trip.id))).all()
    places = (await session.scalars(select(Place).where(Place.trip_id == trip.id))).all()
    votes = (await session.scalars(select(Vote).where(Vote.trip_id == trip.id))).all()
    place_reads = [PlaceRead.model_validate(place) for place in places]
    for place_read in place_reads:
        for vote in votes:
            if vote.place_id == place_read.id:
                place_read.vote_tallies[vote.kind] += 1
        place_read.contested = (
            place_read.vote_tallies["in"] > 0 and place_read.vote_tallies["out"] > 0
        )
    return {
        "messages": [MessageRead.model_validate(m).model_dump(mode="json") for m in messages],
        "members": [MemberRead.model_validate(m).model_dump(mode="json") for m in members],
        "places": [p.model_dump(mode="json") for p in place_reads],
        "votes": [VoteRead.model_validate(v).model_dump(mode="json") for v in votes],
        "trip": TripRead.model_validate(trip).model_dump(mode="json"),
        "timezone": trip.timezone,
    }


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
