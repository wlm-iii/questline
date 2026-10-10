from datetime import datetime
from typing import Literal, Self
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator


class Schema(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


class ConversationCreate(Schema):
    title: str = Field(min_length=1, max_length=200)


class ConversationRead(ConversationCreate):
    id: UUID
    revision: int
    created_at: datetime


class MessageInput(Schema):
    external_id: str = Field(min_length=1, max_length=200)
    author_id: str = Field(min_length=1, max_length=200)
    sent_at: AwareDatetime
    text: str = Field(min_length=1, max_length=10_000)


class MessageBatch(Schema):
    messages: list[MessageInput] = Field(min_length=1, max_length=500)


class MessageRead(MessageInput):
    id: UUID


class IngestResult(Schema):
    inserted: int
    transcript_revision: int


class GenerationCreate(Schema):
    instructions: str = Field(default="Suggest a trip plan", max_length=2000)
    timezone: str = Field(default="UTC", max_length=100)

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("Use an IANA timezone such as America/Los_Angeles") from exc
        return value


class GenerationRead(Schema):
    id: UUID
    conversation_id: UUID
    transcript_revision: int
    status: Literal["queued", "running", "succeeded", "failed"]
    plan_id: UUID | None = None
    error: str | None = None


class PlanNode(Schema):
    id: str = Field(min_length=1, max_length=100)
    kind: Literal["place", "activity", "lodging"]
    title: str = Field(min_length=1, max_length=200)
    notes: str = Field(default="", max_length=2000)
    source_message_ids: list[UUID] = Field(default_factory=list, max_length=500)
    # Store place IDs rather than unrestricted copies of Google Maps responses.
    place_id: str | None = Field(default=None, max_length=300)


class PlanEdge(Schema):
    id: str = Field(min_length=1, max_length=100)
    source: str
    target: str
    kind: Literal["precedes", "travel", "alternative"]


class PlanGraph(Schema):
    nodes: list[PlanNode] = Field(default_factory=list, max_length=500)
    edges: list[PlanEdge] = Field(default_factory=list, max_length=2000)

    @model_validator(mode="after")
    def valid_references(self) -> Self:
        node_ids = {node.id for node in self.nodes}
        if len(node_ids) != len(self.nodes):
            raise ValueError("Node IDs must be unique")
        if len({edge.id for edge in self.edges}) != len(self.edges):
            raise ValueError("Edge IDs must be unique")
        for edge in self.edges:
            if edge.source not in node_ids or edge.target not in node_ids:
                raise ValueError("Edges must reference existing nodes")
            if edge.source == edge.target:
                raise ValueError("Self-edges are not supported")
        return self


class PlanContent(Schema):
    title: str = Field(min_length=1, max_length=200)
    graph: PlanGraph
    assumptions: list[str] = Field(default_factory=list, max_length=100)
    open_questions: list[str] = Field(default_factory=list, max_length=100)
    warnings: list[str] = Field(default_factory=list, max_length=100)


class PlanRead(Schema):
    id: UUID
    conversation_id: UUID
    generation_id: UUID
    revision: int
    status: Literal["draft", "accepted"]
    content: PlanContent


class PlanUpdate(Schema):
    revision: int = Field(ge=1)
    content: PlanContent


class PlanAccept(Schema):
    revision: int = Field(ge=1)
