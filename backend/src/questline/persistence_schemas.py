from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, ConfigDict, Field

from questline.schemas import Schema


class PlaceCreate(Schema):
    query: str = Field(min_length=1, max_length=300)


class PlaceRead(Schema):
    id: UUID
    trip_id: UUID
    google_place_id: str
    name: str
    category: Literal["eat", "do", "stay", "along_the_way"]
    address: str
    lat: float
    lng: float
    google_maps_uri: str | None
    price_level: int | None
    est_cost_low: float | None
    est_cost_high: float | None
    cost_basis: str | None
    source: Literal["group", "suggested", "added"]
    mentioned_by: UUID | None
    mentioned_by_name: str | None
    source_message_ids: list[UUID]
    # Derived from rows, not stored counters.
    vote_tallies: dict[str, int] = Field(default_factory=lambda: {"in": 0, "ok": 0, "out": 0})
    contested: bool = False


class VoteCreate(Schema):
    kind: Literal["in", "ok", "out"]
    # Service callers may specify a member; browsers cannot impersonate another member.
    member_id: UUID | None = None


class VoteRead(Schema):
    id: UUID
    trip_id: UUID
    place_id: UUID
    member_id: UUID
    kind: Literal["in", "ok", "out"]


class ImportCreate(Schema):
    text: str = Field(min_length=1)


class ImportRead(Schema):
    id: UUID
    trip_id: UUID
    source: Literal["paste", "imessage"]
    status: Literal["queued", "running", "succeeded", "failed"]
    message_count: int
    error: str | None


class ChatLink(Schema):
    chat_guid: str = Field(min_length=1, max_length=300)


class RelayMessage(Schema):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)
    guid: str = Field(min_length=1, max_length=200)
    handle: str = Field(min_length=1, max_length=200)
    display_name: str | None = Field(default=None, min_length=1, max_length=60)
    sent_at: AwareDatetime
    text: str = Field(min_length=1, max_length=10_000)
    reply_to_guid: str | None = Field(default=None, min_length=1, max_length=200)


class RelayBatch(Schema):
    messages: list[RelayMessage] = Field(min_length=1, max_length=500)


class ReactionInput(Schema):
    handle: str = Field(min_length=1, max_length=200)
    target_guid: str = Field(min_length=1, max_length=200)
    kind: Literal["love", "like", "dislike"]
    added: bool


class Reactions(Schema):
    reactions: list[ReactionInput] = Field(min_length=1, max_length=500)


class TaskCreate(Schema):
    place_id: UUID
    text: str = Field(min_length=1, max_length=200)
    owner_member_id: UUID | None = None


class TaskUpdate(Schema):
    text: str | None = Field(default=None, min_length=1, max_length=200)
    owner_member_id: UUID | None = None
    done: bool | None = None


class TaskRead(Schema):
    id: UUID
    trip_id: UUID
    place_id: UUID
    text: str
    owner_member_id: UUID | None
    done_at: datetime | None
    created_by: UUID | None


class CheckinRead(Schema):
    id: UUID
    trip_id: UUID
    place_id: UUID
    member_id: UUID | None
    completed_at: datetime
