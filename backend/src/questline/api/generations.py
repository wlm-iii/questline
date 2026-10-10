from typing import Annotated
from uuid import UUID

import psycopg
from fastapi import APIRouter, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from questline.api.dependencies import SessionDep, SettingsDep
from questline.models import Conversation, Message, Plan, PlanGeneration
from questline.schemas import GenerationCreate, GenerationRead, MessageRead

router = APIRouter(tags=["generations"])


@router.post(
    "/conversations/{conversation_id}/plan-generations",
    response_model=GenerationRead,
    status_code=202,
)
async def create_generation(
    conversation_id: UUID,
    body: GenerationCreate,
    session: SessionDep,
    settings: SettingsDep,
    request: Request,
    idempotency_key: Annotated[str, Header(min_length=1, max_length=200)],
):
    conversation = await session.get(Conversation, conversation_id, with_for_update=True)
    if conversation is None:
        raise HTTPException(404, "Conversation not found")
    existing = await session.scalar(
        select(PlanGeneration).where(
            PlanGeneration.conversation_id == conversation_id,
            PlanGeneration.idempotency_key == idempotency_key,
        )
    )
    if existing:
        if existing.instructions != body.instructions or existing.timezone != body.timezone:
            raise HTTPException(409, "Idempotency key was used with a different request")
        return await generation_response(existing, session)
    messages = (
        await session.scalars(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.sent_at, Message.id)
        )
    ).all()
    if not messages:
        raise HTTPException(422, "Import a transcript before generating a plan")
    if sum(len(message.text) for message in messages) > settings.max_transcript_chars:
        raise HTTPException(413, "Transcript exceeds the generation limit")
    generation = PlanGeneration(
        conversation_id=conversation_id,
        idempotency_key=idempotency_key,
        transcript_revision=conversation.revision,
        transcript=[MessageRead.model_validate(m).model_dump(mode="json") for m in messages],
        instructions=body.instructions,
        timezone=body.timezone,
    )
    session.add(generation)
    await session.flush()
    # Enqueue on the SAME transaction: a committed generation always has a job.
    connection = await session.connection()
    raw = await connection.get_raw_connection()
    driver = raw.driver_connection
    assert isinstance(driver, psycopg.AsyncConnection)
    await request.app.state.generate_task.configure(
        connection=driver, lock=f"generation:{generation.id}"
    ).defer_async(generation_id=str(generation.id))
    await session.commit()
    return await generation_response(generation, session)


async def generation_response(generation: PlanGeneration, session: AsyncSession) -> GenerationRead:
    plan_id = await session.scalar(select(Plan.id).where(Plan.generation_id == generation.id))
    result = GenerationRead.model_validate(generation)
    result.plan_id = plan_id
    return result


@router.get("/plan-generations/{generation_id}", response_model=GenerationRead)
async def get_generation(generation_id: UUID, session: SessionDep):
    generation = await session.get(PlanGeneration, generation_id)
    if generation is None:
        raise HTTPException(404, "Generation not found")
    return await generation_response(generation, session)
