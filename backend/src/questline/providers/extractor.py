"""Deterministic development extraction; no AI calls or inferred votes."""

from typing import Protocol
from uuid import UUID

from questline.schemas import MessageRead, Schema


class Mention(Schema):
    mention_text: str
    search_query: str
    message_ids: list[UUID]


class Extractor(Protocol):
    async def extract(self, messages: list[MessageRead]) -> list[Mention]: ...


class FakeExtractor:
    async def extract(self, messages: list[MessageRead]) -> list[Mention]:
        mentions = []
        for message in messages:
            for name in ("McWay Falls", "Big Sur Bakery", "Mystery Cafe"):
                if name.lower() in message.text.lower():
                    mentions.append(
                        Mention(mention_text=name, search_query=name, message_ids=[message.id])
                    )
        return mentions
