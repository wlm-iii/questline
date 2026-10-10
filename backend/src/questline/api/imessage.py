from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Response
from sqlalchemy import false, select
from sqlalchemy.exc import IntegrityError

from questline.api.dependencies import AccessDep, SessionDep, SettingsDep
from questline.api.imports import enqueue_import, require_fake_extraction
from questline.models import Import, Member, Message, Place, Trip, Vote
from questline.persistence_schemas import ChatLink, Reactions, RelayBatch
from questline.schemas import MemberCreate, MemberRead, MessageInput, TripRead
from questline.services.persistence import ingest, locked_trip, member_for_handle, set_vote

router = APIRouter(tags=["iMessage service"])


@router.get("/channels/imessage/{chat_guid:path}")
async def lookup(chat_guid: str, session: SessionDep, access: AccessDep):
    access.require_service()
    trip = await session.scalar(select(Trip).where(Trip.imessage_chat_guid == chat_guid))
    if trip is None:
        raise HTTPException(404, "Chat is not linked")
    return {"trip_id": trip.id}


@router.post("/trips/{trip_id}/channels/imessage")
async def link(trip_id: UUID, body: ChatLink, session: SessionDep, access: AccessDep):
    access.require_service()
    trip = await locked_trip(session, trip_id, access)
    other = await session.scalar(select(Trip).where(Trip.imessage_chat_guid == body.chat_guid))
    if (other and other.id != trip_id) or trip.imessage_chat_guid not in (None, body.chat_guid):
        raise HTTPException(409, "Unlink the existing chat before relinking")
    if trip.imessage_chat_guid != body.chat_guid:
        trip.imessage_chat_guid = body.chat_guid
        trip.revision += 1
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(409, "Chat is already linked") from exc
    return {"trip": TripRead.model_validate(trip)}


@router.delete("/trips/{trip_id}/channels/imessage", status_code=204)
async def unlink(trip_id: UUID, session: SessionDep, access: AccessDep):
    access.require_service()
    trip = await locked_trip(session, trip_id, access)
    if trip.imessage_chat_guid is not None:
        trip.imessage_chat_guid = None
        trip.revision += 1
    await session.commit()
    return Response(status_code=204)


@router.patch("/trips/{trip_id}/imessage/members/{handle}")
async def rename(
    trip_id: UUID, handle: str, body: MemberCreate, session: SessionDep, access: AccessDep
):
    access.require_service()
    trip = await locked_trip(session, trip_id, access)
    member = await session.scalar(
        select(Member).where(Member.trip_id == trip_id, Member.imessage_handle == handle)
    )
    if member is None:
        raise HTTPException(404, "Member handle not found")
    member.name = body.name
    trip.revision += 1
    await session.commit()
    return {"member": MemberRead.model_validate(member)}


@router.post("/trips/{trip_id}/imessage/batch", status_code=202)
async def batch(
    trip_id: UUID,
    body: RelayBatch,
    session: SessionDep,
    settings: SettingsDep,
    access: AccessDep,
    request: Request,
):
    access.require_service()
    require_fake_extraction(settings)
    trip = await locked_trip(session, trip_id, access)
    if trip.imessage_chat_guid is None:
        raise HTTPException(409, "Chat must be linked before ingestion")
    imported = Import(trip_id=trip_id, source="imessage")
    session.add(imported)
    await session.flush()
    messages, members, replies = [], {}, {}
    for message in body.messages:
        if message.text.lstrip().lower().startswith("@questline"):
            continue
        member = await member_for_handle(session, trip_id, message.handle, message.display_name)
        members[message.handle] = member.id
        replies[message.guid] = message.reply_to_guid
        messages.append(
            MessageInput(
                external_id=message.guid,
                author_id=message.handle,
                sent_at=message.sent_at,
                text=message.text,
            )
        )
    inserted = await ingest(
        session,
        trip,
        messages,
        settings.max_transcript_chars,
        source="imessage",
        import_id=imported.id,
        members=members,
        replies=replies,
    )
    await enqueue_import(session, request, trip, imported, [m.external_id for m in messages])
    await session.commit()
    return {"import_id": imported.id, "inserted": len(inserted)}


@router.post("/trips/{trip_id}/imessage/reactions")
async def reactions(trip_id: UUID, body: Reactions, session: SessionDep, access: AccessDep):
    access.require_service()
    trip = await locked_trip(session, trip_id, access)
    if trip.imessage_chat_guid is None:
        raise HTTPException(409, "Chat must be linked before reactions")
    kinds = {"love": "in", "like": "ok", "dislike": "out"}
    applied, skipped = 0, 0
    for reaction in body.reactions:
        message = await session.scalar(
            select(Message).where(
                Message.trip_id == trip_id,
                Message.external_id == reaction.target_guid,
                Message.source == "imessage",
            )
        )
        places = (
            await session.scalars(
                select(Place).where(
                    Place.trip_id == trip_id,
                    Place.source_message_ids.contains([str(message.id)]) if message else false(),
                )
            )
        ).all()
        if len(places) != 1:
            skipped += 1
            continue
        member = await member_for_handle(session, trip_id, reaction.handle)
        kind = kinds[reaction.kind]
        if reaction.added:
            # Redelivery SETS rather than toggles the vote; removals are explicit.
            await set_vote(session, places[0], member.id, kind, toggle=False)
        else:
            vote = await session.scalar(
                select(Vote).where(
                    Vote.place_id == places[0].id, Vote.member_id == member.id, Vote.kind == kind
                )
            )
            if vote:
                await session.delete(vote)
        applied += 1
    if applied:
        trip.revision += 1
    await session.commit()
    return {"applied": applied, "skipped": skipped}
