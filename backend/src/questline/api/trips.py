import secrets
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from questline.api.dependencies import AccessDep, SessionDep, SettingsDep, token_hash
from questline.api.generations import generation_response
from questline.models import Member, Message, Plan, PlanGeneration, Trip
from questline.providers.maps import FakeMaps
from questline.schemas import (
    IngestResult,
    JoinResult,
    MemberCreate,
    MemberRead,
    MessageBatch,
    MessageInput,
    PlanRead,
    TripCreate,
    TripCreated,
    TripRead,
)

router = APIRouter(prefix="/trips", tags=["trips"])


def add_member(session, trip_id: UUID, name: str) -> tuple[Member, str]:
    token = secrets.token_urlsafe(32)
    member = Member(trip_id=trip_id, name=name, token_hash=token_hash(token))
    session.add(member)
    return member, token


@router.post("", response_model=TripCreated, status_code=201)
async def create_trip(body: TripCreate, session: SessionDep, settings: SettingsDep):
    if settings.maps_provider != "fake":
        raise HTTPException(503, "Google Maps provider is not implemented yet")
    maps = FakeMaps()
    origin = await maps.resolve_endpoint(body.origin)
    destination = await maps.resolve_endpoint(body.destination)
    if origin is None or destination is None:
        raise HTTPException(422, "Fake Maps supports only San Jose, CA and Big Sur, CA")
    trip = Trip(
        name=body.name,
        origin=origin.model_dump(),
        destination=destination.model_dump(),
        start_date=body.start_date,
        end_date=body.end_date,
        timezone=body.timezone,
        revision=1,
    )
    session.add(trip)
    await session.flush()
    member, token = add_member(session, trip.id, body.organizer_name)
    await session.commit()
    return TripCreated(
        trip=TripRead.model_validate(trip),
        member=MemberRead.model_validate(member),
        member_token=token,
    )


@router.post("/{trip_id}/members", response_model=JoinResult, status_code=201)
async def join_trip(trip_id: UUID, body: MemberCreate, session: SessionDep):
    trip = await session.get(Trip, trip_id, with_for_update=True)
    if trip is None:
        raise HTTPException(404, "Trip not found")
    member, token = add_member(session, trip_id, body.name)
    trip.revision += 1
    await session.commit()
    return JoinResult(member=MemberRead.model_validate(member), member_token=token)


@router.get("/{trip_id}")
async def get_trip(
    trip_id: UUID,
    session: SessionDep,
    access: AccessDep,
    revision: Annotated[int | None, Query(ge=0)] = None,
):
    access.check_trip(trip_id)
    # A shared row lock yields a consistent view; all trip writes take an exclusive lock first.
    trip = await session.scalar(select(Trip).where(Trip.id == trip_id).with_for_update(read=True))
    if trip is None:
        raise HTTPException(404, "Trip not found")
    if revision == trip.revision:
        return {"unchanged": True, "revision": trip.revision}
    members = (await session.scalars(select(Member).where(Member.trip_id == trip_id))).all()
    jobs = (
        await session.scalars(select(PlanGeneration).where(PlanGeneration.trip_id == trip_id))
    ).all()
    plan = await session.get(Plan, trip.current_plan_id) if trip.current_plan_id else None
    return {
        "trip": TripRead.model_validate(trip),
        "members": [MemberRead.model_validate(member) for member in members],
        # Candidate/vote/task/checkin persistence is the next implementation slice.
        "places": [],
        "votes": [],
        "tasks": [],
        "checkins": [],
        "current_plan": PlanRead.model_validate(plan) if plan else None,
        "jobs": [await generation_response(job, session) for job in jobs],
        "revision": trip.revision,
    }


@router.post("/{trip_id}/messages/batch", response_model=IngestResult)
async def ingest_messages(
    trip_id: UUID, body: MessageBatch, session: SessionDep, settings: SettingsDep, access: AccessDep
):
    access.check_trip(trip_id)
    trip = await session.get(Trip, trip_id, with_for_update=True)
    if trip is None:
        raise HTTPException(404, "Trip not found")
    stored = (await session.scalars(select(Message).where(Message.trip_id == trip_id))).all()
    by_external_id = {m.external_id: MessageInput.model_validate(m) for m in stored}
    total_chars = sum(len(message.text) for message in stored)
    inserted = 0
    for message in body.messages:
        previous = by_external_id.get(message.external_id)
        if previous is not None:
            if previous != message:
                raise HTTPException(409, "Message ID already exists with different content")
            continue
        total_chars += len(message.text)
        if total_chars > settings.max_transcript_chars:
            raise HTTPException(413, "Transcript too large; messages were not imported")
        session.add(Message(trip_id=trip_id, **message.model_dump()))
        by_external_id[message.external_id] = message
        inserted += 1
    if inserted:
        trip.revision += 1
    await session.commit()
    return IngestResult(inserted=inserted, revision=trip.revision)
