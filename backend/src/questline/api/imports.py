from uuid import UUID

import psycopg
from fastapi import APIRouter, HTTPException, Request
from pydantic import ValidationError
from sqlalchemy import select

from questline.api.dependencies import AccessDep, SessionDep, SettingsDep
from questline.models import Import, Message
from questline.persistence_schemas import ImportCreate
from questline.services.persistence import ingest, locked_trip, parse_chat

router = APIRouter(tags=["imports"])


def require_fake_extraction(settings):
    if settings.planner_provider != "fake" or settings.maps_provider != "fake":
        raise HTTPException(503, "Real extraction providers are not implemented yet")


async def enqueue_import(session, request, trip, imported, external_ids):
    await session.flush()
    messages = (
        await session.scalars(
            select(Message).where(Message.trip_id == trip.id, Message.external_id.in_(external_ids))
        )
    ).all()
    imported.message_ids = [str(message.id) for message in messages]
    imported.message_count = len(messages)
    trip.revision += 1
    raw = await (await session.connection()).get_raw_connection()
    assert isinstance(raw.driver_connection, psycopg.AsyncConnection)
    await request.app.state.extract_task.configure(
        connection=raw.driver_connection, lock=f"trip:{trip.id}"
    ).defer_async(import_id=str(imported.id))


@router.post("/trips/{trip_id}/import", status_code=202)
async def import_chat(
    trip_id: UUID,
    body: ImportCreate,
    session: SessionDep,
    settings: SettingsDep,
    access: AccessDep,
    request: Request,
):
    require_fake_extraction(settings)
    trip = await locked_trip(session, trip_id, access)
    if len(body.text) > settings.max_transcript_chars:
        raise HTTPException(413, "Import text is too large")
    try:
        messages = parse_chat(body.text)
    except ValidationError as exc:
        raise HTTPException(422, "Invalid message length or author") from exc
    imported = Import(
        trip_id=trip_id, source="paste", member_id=access.member.id if access.member else None
    )
    session.add(imported)
    await session.flush()
    inserted = await ingest(
        session,
        trip,
        messages,
        settings.max_transcript_chars,
        source="import",
        import_id=imported.id,
    )
    await enqueue_import(session, request, trip, imported, [m.external_id for m in messages])
    await session.commit()
    return {
        "import_id": imported.id,
        "message_count": imported.message_count,
        "inserted": len(inserted),
        "status": imported.status,
    }
