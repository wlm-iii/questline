import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from questline.models import Plan, PlanGeneration
from questline.providers.planner import Planner
from questline.schemas import GenerationCreate, MessageRead, PlanContent

logger = logging.getLogger(__name__)


async def generate_plan(
    generation_id: UUID, sessions: async_sessionmaker[AsyncSession], planner: Planner
) -> None:
    # The queue's per-generation lock serializes retries; the unique generation_id
    # on plans is a second guard against duplicate output.
    async with sessions() as session:
        generation = await session.get(PlanGeneration, generation_id)
        if generation is None:
            raise ValueError("Generation does not exist")
        if generation.status == "succeeded":
            return
        generation.status = "running"
        generation.error = None
        transcript = [MessageRead.model_validate(message) for message in generation.transcript]
        request = GenerationCreate(
            instructions=generation.instructions, timezone=generation.timezone
        )
        await session.commit()

    try:
        # No database transaction held open during a potentially slow provider call.
        content = PlanContent.model_validate(await planner.generate(transcript, request))
        message_ids = {message.id for message in transcript}
        if any(
            source not in message_ids
            for node in content.graph.nodes
            for source in node.source_message_ids
        ):
            raise ValueError("Provider referenced an unknown source message")
        async with sessions() as session:
            generation = await session.get(PlanGeneration, generation_id, with_for_update=True)
            assert generation is not None
            if generation.status == "succeeded":
                return
            session.add(
                Plan(
                    conversation_id=generation.conversation_id,
                    generation_id=generation.id,
                    content=content.model_dump(mode="json"),
                )
            )
            generation.status = "succeeded"
            generation.error = None
            await session.commit()
    except Exception:
        # Don't put raw provider errors (which might contain transcript or keys) in responses/logs.
        logger.error("Plan generation failed: %s", generation_id)
        async with sessions() as session:
            generation = await session.get(PlanGeneration, generation_id)
            assert generation is not None
            generation.status = "failed"
            generation.error = "Plan generation failed. Submit a new request to try again."
            await session.commit()
        # Failure is persisted; automatic paid-provider retries will be added with
        # an explicit transient-error policy when real providers are implemented.
