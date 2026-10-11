from uuid import UUID

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from questline.api.dependencies import AccessDep, SessionDep, SettingsDep
from questline.models import Place, Vote
from questline.persistence_schemas import PlaceCreate, PlaceRead, VoteCreate, VoteRead
from questline.providers.selection import maps_for_settings
from questline.services.persistence import locked_trip, set_vote

router = APIRouter(tags=["waypoints"])


@router.post("/trips/{trip_id}/places", status_code=201)
async def add_place(
    trip_id: UUID, body: PlaceCreate, session: SessionDep, settings: SettingsDep, access: AccessDep
):
    from questline.services.persistence import upsert_place

    access.check_trip(trip_id)
    resolved = await maps_for_settings(settings).resolve_place(body.query)
    if resolved is None:
        raise HTTPException(404, {"code": "place_not_found", "message": "Couldn't find that place"})
    trip = await locked_trip(session, trip_id, access)
    place = await upsert_place(
        session,
        trip_id,
        resolved,
        source="added",
        member_id=access.member.id if access.member else None,
    )
    trip.revision += 1
    votes = (await session.scalars(select(Vote).where(Vote.place_id == place.id))).all()
    result = PlaceRead.model_validate(place)
    for vote in votes:
        result.vote_tallies[vote.kind] += 1
    result.contested = result.vote_tallies["in"] > 0 and result.vote_tallies["out"] > 0
    await session.commit()
    return {"place": result}


@router.post("/places/{place_id}/votes")
async def vote(place_id: UUID, body: VoteCreate, session: SessionDep, access: AccessDep):
    place = await session.get(Place, place_id)
    if place is None:
        raise HTTPException(404, "Place not found")
    trip = await locked_trip(session, place.trip_id, access)
    member_id = access.member.id if access.member else body.member_id
    if member_id is None or (access.member and body.member_id not in (None, member_id)):
        raise HTTPException(422, "A vote requires the caller's member identity")
    result = await set_vote(session, place, member_id, body.kind, toggle=True)
    trip.revision += 1
    await session.commit()
    return {"vote": VoteRead.model_validate(result) if result else None}
