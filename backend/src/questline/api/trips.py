import secrets
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from questline.api.dependencies import AccessDep, SessionDep, SettingsDep, token_hash
from questline.api.generations import generation_response
from questline.models import (
    Checkin,
    Import,
    Member,
    Message,
    Place,
    Plan,
    PlanGeneration,
    Task,
    Trip,
    Vote,
)
from questline.persistence_schemas import CheckinRead, ImportRead, PlaceRead, TaskRead, VoteRead
from questline.providers.selection import maps_for_settings
from questline.schemas import (
    IngestResult,
    JoinResult,
    MemberCreate,
    MemberRead,
    MessageBatch,
    MessageRead,
    PlanRead,
    TripCreate,
    TripCreated,
    TripRead,
)
from questline.services.persistence import ingest, locked_trip

router = APIRouter(prefix="/trips", tags=["trips"])


def add_member(session, trip_id: UUID, name: str) -> tuple[Member, str]:
    token = secrets.token_urlsafe(32)
    member = Member(trip_id=trip_id, name=name, token_hash=token_hash(token))
    session.add(member)
    return member, token


@router.post("", response_model=TripCreated, status_code=201)
async def create_trip(body: TripCreate, session: SessionDep, settings: SettingsDep):
    maps = maps_for_settings(settings)
    origin = await maps.resolve_endpoint(body.origin)
    destination = await maps.resolve_endpoint(body.destination)
    if origin is None or destination is None:
        message = (
            "Fake Maps supports only San Jose, CA and Big Sur, CA"
            if settings.maps_provider == "fake"
            else "Couldn't resolve origin or destination. Try including the city or region."
        )
        raise HTTPException(422, message)
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
    places = (await session.scalars(select(Place).where(Place.trip_id == trip_id))).all()
    votes = (await session.scalars(select(Vote).where(Vote.trip_id == trip_id))).all()
    tasks = (await session.scalars(select(Task).where(Task.trip_id == trip_id))).all()
    checkins = (await session.scalars(select(Checkin).where(Checkin.trip_id == trip_id))).all()
    imports = (await session.scalars(select(Import).where(Import.trip_id == trip_id))).all()
    messages = (
        await session.scalars(
            select(Message).where(Message.trip_id == trip_id).order_by(Message.sent_at, Message.id)
        )
    ).all()
    place_reads = [PlaceRead.model_validate(place) for place in places]
    for place in place_reads:
        for vote in votes:
            if vote.place_id == place.id:
                place.vote_tallies[vote.kind] += 1
        place.contested = place.vote_tallies["in"] > 0 and place.vote_tallies["out"] > 0
    return {
        "trip": TripRead.model_validate(trip),
        "members": [MemberRead.model_validate(member) for member in members],
        "places": place_reads,
        "votes": [VoteRead.model_validate(vote) for vote in votes],
        "tasks": [TaskRead.model_validate(task) for task in tasks],
        "checkins": [CheckinRead.model_validate(checkin) for checkin in checkins],
        "imports": [ImportRead.model_validate(imported) for imported in imports],
        "messages": [MessageRead.model_validate(message) for message in messages],
        "current_plan": PlanRead.model_validate(plan) if plan else None,
        "jobs": [await generation_response(job, session) for job in jobs],
        "revision": trip.revision,
    }


@router.post("/{trip_id}/messages/batch", response_model=IngestResult)
async def ingest_messages(
    trip_id: UUID, body: MessageBatch, session: SessionDep, settings: SettingsDep, access: AccessDep
):
    trip = await locked_trip(session, trip_id, access)
    members = (
        {message.author_id: access.member.id for message in body.messages} if access.member else {}
    )
    inserted = await ingest(
        session, trip, body.messages, settings.max_transcript_chars, source="web", members=members
    )
    if inserted:
        trip.revision += 1
    await session.commit()
    return IngestResult(inserted=len(inserted), revision=trip.revision)
