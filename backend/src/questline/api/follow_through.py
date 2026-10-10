from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, Response
from sqlalchemy import select

from questline.api.dependencies import AccessDep, SessionDep
from questline.models import Checkin, Place, Task
from questline.persistence_schemas import CheckinRead, TaskCreate, TaskRead, TaskUpdate
from questline.services.persistence import locked_trip, same_trip_member

router = APIRouter(tags=["quest log"])


@router.post("/trips/{trip_id}/tasks", status_code=201)
async def create_task(trip_id: UUID, body: TaskCreate, session: SessionDep, access: AccessDep):
    trip = await locked_trip(session, trip_id, access)
    place = await session.get(Place, body.place_id)
    if place is None or place.trip_id != trip_id:
        raise HTTPException(422, "Place does not belong to the trip")
    await same_trip_member(session, body.owner_member_id, trip_id)
    task = Task(
        trip_id=trip_id, **body.model_dump(), created_by=access.member.id if access.member else None
    )
    session.add(task)
    trip.revision += 1
    await session.commit()
    return {"task": TaskRead.model_validate(task)}


@router.patch("/tasks/{task_id}")
async def edit_task(task_id: UUID, body: TaskUpdate, session: SessionDep, access: AccessDep):
    task = await session.get(Task, task_id)
    if task is None:
        raise HTTPException(404, "Task not found")
    trip = await locked_trip(session, task.trip_id, access)
    await session.refresh(task)
    if "owner_member_id" in body.model_fields_set:
        await same_trip_member(session, body.owner_member_id, trip.id)
        task.owner_member_id = body.owner_member_id
    if "text" in body.model_fields_set:
        if body.text is None:
            raise HTTPException(422, "Task text cannot be null")
        task.text = body.text
    if "done" in body.model_fields_set:
        if body.done is None:
            raise HTTPException(422, "Task done cannot be null")
        task.done_at = (task.done_at or datetime.now(UTC)) if body.done else None
    trip.revision += 1
    await session.commit()
    return {"task": TaskRead.model_validate(task)}


async def checkin_context(place_id, session, access):
    place = await session.get(Place, place_id)
    if place is None:
        raise HTTPException(404, "Place not found")
    trip = await locked_trip(session, place.trip_id, access)
    checkin = await session.scalar(
        select(Checkin).where(Checkin.trip_id == trip.id, Checkin.place_id == place_id)
    )
    return trip, checkin


@router.post("/places/{place_id}/checkins")
async def complete(place_id: UUID, session: SessionDep, access: AccessDep):
    trip, checkin = await checkin_context(place_id, session, access)
    if checkin is None:
        checkin = Checkin(
            trip_id=trip.id,
            place_id=place_id,
            member_id=access.member.id if access.member else None,
        )
        session.add(checkin)
        trip.revision += 1
    await session.commit()
    return {"checkin": CheckinRead.model_validate(checkin)}


@router.delete("/places/{place_id}/checkins", status_code=204)
async def undo_complete(place_id: UUID, session: SessionDep, access: AccessDep):
    trip, checkin = await checkin_context(place_id, session, access)
    if checkin:
        await session.delete(checkin)
        trip.revision += 1
    await session.commit()
    return Response(status_code=204)
