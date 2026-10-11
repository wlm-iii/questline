"""Shared persistence rules. Callers lock the trip before changing its rows."""

import hashlib
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

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
from questline.pricing import apply_estimate
from questline.providers.maps import ResolvedPlace
from questline.schemas import MessageInput


async def locked_trip(session: AsyncSession, trip_id: UUID, access) -> Trip:
    access.check_trip(trip_id)
    trip = await session.get(Trip, trip_id, with_for_update=True)
    if trip is None:
        raise HTTPException(404, "Trip not found")
    return trip


async def same_trip_member(session: AsyncSession, member_id: UUID | None, trip_id: UUID):
    if member_id is None:
        return None
    member = await session.get(Member, member_id)
    if member is None or member.trip_id != trip_id:
        raise HTTPException(422, "Member does not belong to the trip")
    return member


async def member_for_handle(
    session: AsyncSession, trip_id: UUID, handle: str, name: str | None = None
):
    # Preserve platform identifiers; don't guess country codes or merge by display name.
    member = await session.scalar(
        select(Member).where(Member.trip_id == trip_id, Member.imessage_handle == handle)
    )
    if member is None:
        member = Member(trip_id=trip_id, name=name or handle[:60], imessage_handle=handle)
        session.add(member)
        await session.flush()
    return member


async def claim_handle(session: AsyncSession, trip_id: UUID, handle: str, name: str) -> Member:
    """`@questline I'm <name>`: tie a chat handle to a person.

    When exactly one member with that name has no handle yet (someone who joined on the web),
    the handle becomes theirs, and anything the handle already did in the chat moves to them.
    Otherwise the handle's member is renamed, or created. Names never merge two handles.
    """
    current = await session.scalar(
        select(Member).where(Member.trip_id == trip_id, Member.imessage_handle == handle)
    )
    matches = (
        await session.scalars(
            select(Member).where(
                Member.trip_id == trip_id,
                Member.imessage_handle.is_(None),
                func.lower(Member.name) == name.casefold(),
            )
        )
    ).all()
    if len(matches) != 1:
        if current is None:
            current = Member(trip_id=trip_id, name=name, imessage_handle=handle)
            session.add(current)
        else:
            current.name = name
        await session.flush()
        await _refresh_mention_names(session, trip_id, current)
        return current
    target = matches[0]
    if current is not None:
        await merge_member(session, trip_id, current, target)
    target.imessage_handle = handle
    await session.flush()
    await _refresh_mention_names(session, trip_id, target)
    return target


async def _refresh_mention_names(session: AsyncSession, trip_id: UUID, member: Member) -> None:
    """Places show who mentioned them by name; keep that in step with the member's name."""
    await session.execute(
        update(Place)
        .where(Place.trip_id == trip_id, Place.mentioned_by == member.id)
        .values(mentioned_by_name=member.name)
        .execution_options(synchronize_session=False)
    )


async def merge_member(session: AsyncSession, trip_id: UUID, source: Member, target: Member):
    """Move everything `source` did to `target`, then delete `source`. Callers lock the trip."""
    old, new = source.id, target.id
    # One vote per member and place: keep whichever was cast most recently.
    for vote in (await session.scalars(select(Vote).where(Vote.member_id == old))).all():
        existing = await session.scalar(
            select(Vote).where(Vote.place_id == vote.place_id, Vote.member_id == new)
        )
        if existing is None:
            vote.member_id = new
        elif vote.created_at > existing.created_at:
            await session.delete(existing)
            await session.flush()
            vote.member_id = new
        else:
            await session.delete(vote)
    for model, column in (
        (Message, Message.member_id),
        (Place, Place.mentioned_by),
        (Task, Task.owner_member_id),
        (Task, Task.created_by),
        (Checkin, Checkin.member_id),
        (Import, Import.member_id),
        (PlanGeneration, PlanGeneration.requested_by),
    ):
        await session.execute(
            update(model)
            .where(model.trip_id == trip_id, column == old)
            .values({column.key: new})
            .execution_options(synchronize_session=False)
        )
    for plan in (await session.scalars(select(Plan).where(Plan.trip_id == trip_id))).all():
        nodes = plan.content.get("graph", {}).get("nodes", [])
        if any(node.get("owner_member_id") == str(old) for node in nodes):
            content = dict(plan.content)
            content["graph"] = {
                **content["graph"],
                "nodes": [
                    {**node, "owner_member_id": str(new)}
                    if node.get("owner_member_id") == str(old)
                    else node
                    for node in nodes
                ],
            }
            plan.content = content
    await session.flush()
    await session.execute(delete(Member).where(Member.id == old))
    session.expunge(source)


async def ingest(
    session: AsyncSession,
    trip: Trip,
    messages: list[MessageInput],
    limit: int,
    *,
    source: str,
    import_id: UUID | None = None,
    members: dict[str, UUID] | None = None,
    replies: dict[str, str | None] | None = None,
) -> list[Message]:
    stored = (await session.scalars(select(Message).where(Message.trip_id == trip.id))).all()
    by_external = {message.external_id: message for message in stored}
    total = sum(len(message.text) for message in stored)
    inserted = []
    for incoming in messages:
        if incoming.text.lstrip().lower().startswith("@questline") and source == "imessage":
            continue  # Defense in depth: bot commands never enter the extraction transcript.
        existing = by_external.get(incoming.external_id)
        if existing is not None:
            if MessageInput.model_validate(existing) != incoming or (
                replies is not None and existing.reply_to_guid != replies.get(incoming.external_id)
            ):
                raise HTTPException(409, "Message ID already exists with different content")
            continue
        total += len(incoming.text)
        if total > limit:
            raise HTTPException(413, "Transcript too large; messages were not imported")
        message = Message(
            trip_id=trip.id,
            **incoming.model_dump(),
            source=source,
            import_id=import_id,
            member_id=(members or {}).get(incoming.author_id),
            reply_to_guid=(replies or {}).get(incoming.external_id),
        )
        session.add(message)
        inserted.append(message)
        by_external[incoming.external_id] = message
    await session.flush()
    # Resolve out-of-order replies when their parent eventually arrives, but only within this trip.
    for message in by_external.values():
        parent = by_external.get(message.reply_to_guid) if message.reply_to_guid else None
        if parent is not None and parent.id != message.id:
            message.reply_to_id = parent.id
    return inserted


async def upsert_place(
    session: AsyncSession,
    trip_id: UUID,
    resolved: ResolvedPlace,
    *,
    source: str,
    message_ids: list[UUID] | None = None,
    member_id: UUID | None = None,
    author_name: str | None = None,
) -> Place:
    await same_trip_member(session, member_id, trip_id)
    for message_id in message_ids or []:
        message = await session.get(Message, message_id)
        if message is None or message.trip_id != trip_id:
            raise HTTPException(422, "Evidence does not belong to the trip")
    place = await session.scalar(
        select(Place).where(
            Place.trip_id == trip_id, Place.google_place_id == resolved.google_place_id
        )
    )
    if place is None:
        place = Place(
            trip_id=trip_id,
            **resolved.model_dump(),
            source=source,
            mentioned_by=member_id,
            mentioned_by_name=author_name,
            source_message_ids=[str(mid) for mid in message_ids or []],
        )
        session.add(place)
    else:
        if source != "suggested":
            refreshed = {
                "category": place.category,
                "price_level": resolved.price_level,
                "est_cost_low": place.est_cost_low,
                "est_cost_high": place.est_cost_high,
                "cost_basis": place.cost_basis,
            }
            apply_estimate(refreshed)
            for field in ("price_level", "est_cost_low", "est_cost_high", "cost_basis"):
                setattr(place, field, refreshed[field])
        place.source_message_ids = list(
            dict.fromkeys([*place.source_message_ids, *(str(mid) for mid in message_ids or [])])
        )
        if source == "group":
            if place.source != "group":
                place.mentioned_by = member_id
                place.mentioned_by_name = author_name
            place.source = "group"
    await session.flush()
    return place


async def set_vote(
    session: AsyncSession, place: Place, member_id: UUID, kind: str, *, toggle: bool
):
    await same_trip_member(session, member_id, place.trip_id)
    vote = await session.scalar(
        select(Vote).where(Vote.place_id == place.id, Vote.member_id == member_id)
    )
    if vote and vote.kind == kind and toggle:
        await session.delete(vote)
        return None
    if vote is None:
        vote = Vote(trip_id=place.trip_id, place_id=place.id, member_id=member_id, kind=kind)
        session.add(vote)
    else:
        vote.kind = kind
    await session.flush()
    return vote


def parse_chat(text: str) -> list[MessageInput]:
    rows: list[tuple[str, str]] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        if ":" in line and not line[:1].isspace():
            name, body = line.split(":", 1)
            if not name.strip() or not body.strip():
                raise HTTPException(422, "Use Name: text lines")
            rows.append((name.strip(), body.strip()))
        elif rows:
            name, body = rows[-1]
            rows[-1] = (name, body + "\n" + line.strip())
        else:
            raise HTTPException(422, "Use Name: text lines")
    if not rows:
        raise HTTPException(422, "No messages found")
    # Synthetic, stable ordering—not claimed to be the original chat's timestamps.
    epoch = datetime(2000, 1, 1, tzinfo=UTC)
    return [
        MessageInput(
            external_id="paste:" + hashlib.sha256(f"{index}:{name}:{body}".encode()).hexdigest(),
            author_id=name,
            text=body,
            sent_at=epoch + timedelta(seconds=index),
        )
        for index, (name, body) in enumerate(rows)
    ]
