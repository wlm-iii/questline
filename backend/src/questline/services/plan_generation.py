import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from questline.config import Settings
from questline.models import Plan, PlanGeneration, Trip
from questline.providers.planner import Planner
from questline.providers.selection import planner_for_settings
from questline.schemas import GenerationCreate, PlanContent
from questline.services.questline_plan import PlanningError
from questline.services.suggestions import register_suggestions

logger = logging.getLogger(__name__)


async def generate_plan(
    generation_id: UUID,
    sessions: async_sessionmaker[AsyncSession],
    planner: Planner | None = None,
    *,
    settings: Settings | None = None,
) -> None:
    async with sessions() as session:
        generation = await session.get(PlanGeneration, generation_id)
        if generation is None:
            raise ValueError("Generation does not exist")
        # Failed is final, including builds that timed out before a worker ran them.
        if generation.status in ("succeeded", "failed"):
            return
        trip = await session.get(Trip, generation.trip_id, with_for_update=True)
        assert trip is not None
        await session.refresh(generation)
        if generation.status in ("succeeded", "failed"):
            return
        generation.status = "running"
        generation.error = None
        snapshot = generation.snapshot
        trip_id = generation.trip_id
        request = GenerationCreate.model_validate({"budget_preset": generation.budget_preset})
        trip.revision += 1
        await session.commit()

    try:
        if planner is None:
            if settings is None:
                raise ValueError("Planner or settings required")

            async def sink(found):
                return await register_suggestions(sessions, trip_id, found)

            effective = settings.model_copy(update=snapshot.get("planning_limits", {}))
            planner = planner_for_settings(effective, register_suggestions=sink)
        content = PlanContent.model_validate(await planner.generate(snapshot, request))
        if content.budget_preset != request.budget_preset:
            raise ValueError("Provider returned a different budget preset")
        message_ids = {UUID(message["id"]) for message in snapshot["messages"]}
        if any(
            source not in message_ids
            for node in content.graph.nodes
            for source in node.source_message_ids
        ):
            raise ValueError("Provider referenced an unknown source message")
        async with sessions() as session:
            generation = await session.get(PlanGeneration, generation_id)
            assert generation is not None
            trip = await session.get(Trip, generation.trip_id, with_for_update=True)
            assert trip is not None
            await session.refresh(generation)
            if generation.status in ("succeeded", "failed"):
                return
            plan = Plan(
                trip_id=generation.trip_id,
                generation_id=generation.id,
                status="draft",
                budget_preset=generation.budget_preset,
                content=content.model_dump(mode="json"),
            )
            session.add(plan)
            await session.flush()
            trip.current_plan_id = plan.id
            trip.budget_preset = generation.budget_preset
            trip.revision += 1
            generation.status = "succeeded"
            generation.error = None
            await session.commit()
    except Exception as exc:
        logger.error("Plan generation failed: %s", generation_id)
        async with sessions() as session:
            generation = await session.get(PlanGeneration, generation_id)
            assert generation is not None
            trip = await session.get(Trip, generation.trip_id, with_for_update=True)
            assert trip is not None
            await session.refresh(generation)
            if generation.status in ("succeeded", "failed"):
                return
            generation.status = "failed"
            generation.error = (
                str(exc)
                if isinstance(exc, PlanningError)
                else "Plan generation failed. Submit a new request to try again."
            )
            trip.revision += 1
            # Leave current_plan_id and the successful preset unchanged on failure.
            await session.commit()
