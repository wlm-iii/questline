from uuid import UUID

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from questline.api.dependencies import SessionDep, SettingsDep
from questline.models import Conversation, Message
from questline.schemas import (
    ConversationCreate,
    ConversationRead,
    IngestResult,
    MessageBatch,
    MessageInput,
)

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.post("", response_model=ConversationRead, status_code=201)
async def create_conversation(body: ConversationCreate, session: SessionDep):
    conversation = Conversation(title=body.title)
    session.add(conversation)
    await session.commit()
    return conversation


@router.post("/{conversation_id}/messages/batch", response_model=IngestResult)
async def ingest_messages(
    conversation_id: UUID, body: MessageBatch, session: SessionDep, settings: SettingsDep
):
    # Serializes ingestion and snapshot creation for this conversation.
    conversation = await session.get(Conversation, conversation_id, with_for_update=True)
    if conversation is None:
        raise HTTPException(404, "Conversation not found")
    stored = (
        await session.scalars(select(Message).where(Message.conversation_id == conversation_id))
    ).all()
    by_external_id = {
        message.external_id: MessageInput.model_validate(message) for message in stored
    }
    total_chars = sum(len(message.text) for message in stored)
    inserted = 0
    for message in body.messages:
        previous = by_external_id.get(message.external_id)
        if previous is not None:
            if previous != message:
                raise HTTPException(409, "Message ID already exists with different content")
            continue
        total_chars += len(message.text)
        if total_chars > settings.max_transcript_chars:
            raise HTTPException(413, "Transcript too large; messages were not imported")
        session.add(Message(conversation_id=conversation_id, **message.model_dump()))
        by_external_id[message.external_id] = message
        inserted += 1
    if inserted:
        conversation.revision += 1
    await session.commit()
    return IngestResult(inserted=inserted, transcript_revision=conversation.revision)
