"""Deterministic development extraction; no AI calls or inferred votes."""

from typing import Literal, Protocol
from uuid import UUID

from pydantic import Field

from questline.schemas import MessageRead, Schema


class Mention(Schema):
    mention_text: str = Field(min_length=1, max_length=300)
    search_query: str = Field(min_length=1, max_length=500)
    message_ids: list[UUID] = Field(min_length=1, max_length=10)
    category_guess: Literal["eat", "do", "stay", "along_the_way"] | None = None


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
