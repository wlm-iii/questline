"""Decision-only editor contracts. Applying/recomputing operations is a later slice.

Clients must not supply derived fields such as route polylines, times, or cost estimates.
"""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field

from questline.schemas import Schema


class SetQuest(Schema):
    op: Literal["set_quest"]
    node_id: str
    quest: Literal["main", "side"]


class Move(Schema):
    op: Literal["move"]
    node_id: str
    after: str


class SetAnchor(Schema):
    op: Literal["set_anchor"]
    node_id: str
    anchor: str


class Drop(Schema):
    op: Literal["drop"]
    node_id: str


class Add(Schema):
    op: Literal["add"]
    place_id: UUID
    quest: Literal["main", "side"]
    after: str | None = None
    anchor: str | None = None


class AssignOwner(Schema):
    op: Literal["assign_owner"]
    node_id: str
    member_id: UUID | None


class SetNote(Schema):
    op: Literal["set_note"]
    node_id: str
    notes: str = Field(max_length=500)


Operation = Annotated[
    SetQuest | Move | SetAnchor | Drop | Add | AssignOwner | SetNote,
    Field(discriminator="op"),
]


class OperationsRequest(Schema):
    revision: int = Field(ge=1)
    operations: list[Operation] = Field(min_length=1, max_length=100)
