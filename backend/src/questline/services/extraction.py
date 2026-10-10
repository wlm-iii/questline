import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from questline.models import Import, Message, Place, Trip
from questline.providers.extractor import FakeExtractor
from questline.providers.maps import FakeMaps
from questline.schemas import MessageRead
from questline.services.persistence import upsert_place

logger = logging.getLogger(__name__)


async def extract_places(import_id: UUID, sessions: async_sessionmaker[AsyncSession]) -> None:
    async with sessions() as session:
        imported = await session.get(Import, import_id)
        if imported is None:
            raise ValueError("Import not found")
        trip = await session.get(Trip, imported.trip_id, with_for_update=True)
        assert trip is not None
        if imported.status == "succeeded":
            return
        imported.status = "running"
        imported.error = None
        messages = (
            await session.scalars(
                select(Message).where(
                    Message.trip_id == imported.trip_id,
                    Message.id.in_([UUID(mid) for mid in imported.message_ids]),
                )
            )
        ).all()
        inputs = [MessageRead.model_validate(m) for m in messages]
        trip.revision += 1
        await session.commit()
    try:
        # Provider calls never hold the trip's transaction open.
        mentions = await FakeExtractor().extract(inputs)
        resolved = [
            (mention, await FakeMaps().resolve_place(mention.search_query)) for mention in mentions
        ]
        allowed_ids = {m.id for m in inputs}
        if any(mid not in allowed_ids for mention, _ in resolved for mid in mention.message_ids):
            raise ValueError("Extractor referenced messages outside this import")
        async with sessions() as session:
            imported = await session.get(Import, import_id)
            assert imported is not None
            trip = await session.get(Trip, imported.trip_id, with_for_update=True)
            assert trip is not None
            await session.refresh(imported)
            if imported.status == "succeeded":
                return
            unresolved = list(trip.unresolved_mentions)
            for mention, result in resolved:
                if result is None:
                    entry = {
                        "mention_text": mention.mention_text,
                        "message_ids": [str(mid) for mid in mention.message_ids],
                    }
                    if entry not in unresolved:
                        unresolved.append(entry)
                    continue
                first = await session.get(Message, mention.message_ids[0])
                assert first is not None
                await upsert_place(
                    session,
                    trip.id,
                    result,
                    source="group",
                    message_ids=mention.message_ids,
                    member_id=first.member_id,
                    author_name=first.author_id,
                )
            # Replies are evidence, never guessed votes. Parents may arrive in later imports.
            all_messages = (
                await session.scalars(select(Message).where(Message.trip_id == trip.id))
            ).all()
            places = (await session.scalars(select(Place).where(Place.trip_id == trip.id))).all()
            for message in all_messages:
                if message.reply_to_id is None:
                    continue
                parents = [p for p in places if str(message.reply_to_id) in p.source_message_ids]
                if len(parents) == 1:
                    place = parents[0]
                    place.source_message_ids = list(
                        dict.fromkeys([*place.source_message_ids, str(message.id)])
                    )
            trip.unresolved_mentions = unresolved
            imported.status = "succeeded"
            trip.revision += 1
            await session.commit()
    except Exception:
        logger.error("Extraction failed: %s", import_id)
        async with sessions() as session:
            imported = await session.get(Import, import_id)
            assert imported is not None
            trip = await session.get(Trip, imported.trip_id, with_for_update=True)
            assert trip is not None
            imported.status = "failed"
            imported.error = "Extraction failed. Import again to retry."
            trip.revision += 1
            await session.commit()
