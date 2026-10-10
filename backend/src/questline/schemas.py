from datetime import date, datetime
from typing import Literal, Self
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

BudgetPreset = Literal["shoestring", "comfortable", "treat"]


class Schema(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True, str_strip_whitespace=True)


class MemberCreate(Schema):
    name: str = Field(min_length=1, max_length=60)


class MemberRead(MemberCreate):
    id: UUID
    trip_id: UUID
    imessage_handle: str | None = None
    discord_user_id: str | None = None


class Endpoint(Schema):
    label: str
    google_place_id: str
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


class TripCreate(Schema):
    name: str = Field(min_length=1, max_length=100)
    origin: str = Field(min_length=1, max_length=200)
    destination: str = Field(min_length=1, max_length=200)
    start_date: date
    end_date: date
    timezone: str = Field(min_length=1, max_length=100)
    organizer_name: str = Field(min_length=1, max_length=60)

    @model_validator(mode="after")
    def validate_dates(self) -> Self:
        if not 0 <= (self.end_date - self.start_date).days <= 2:
            raise ValueError("Trips must span one to three inclusive days")
        try:
            ZoneInfo(self.timezone)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("Use a valid IANA timezone") from exc
        return self


class TripRead(Schema):
    id: UUID
    name: str
    origin: Endpoint | None
    destination: Endpoint | None
    start_date: date | None
    end_date: date | None
    timezone: str
    budget_preset: BudgetPreset
    current_plan_id: UUID | None
    imessage_chat_guid: str | None
    unresolved_mentions: list[dict] = Field(default_factory=list)
    revision: int
    created_at: datetime


class JoinResult(Schema):
    member: MemberRead
    member_token: str


class TripCreated(JoinResult):
    trip: TripRead


class MessageInput(Schema):
    # Transcript text must retain exact whitespace for evidence and deduplication.
    model_config = ConfigDict(extra="forbid", from_attributes=True, str_strip_whitespace=False)
    external_id: str = Field(min_length=1, max_length=200)
    author_id: str = Field(min_length=1, max_length=200)
    sent_at: AwareDatetime
    text: str = Field(min_length=1, max_length=10_000)


class MessageBatch(Schema):
    messages: list[MessageInput] = Field(min_length=1, max_length=500)


class MessageRead(MessageInput):
    id: UUID
    member_id: UUID | None = None
    source: str = "web"
    import_id: UUID | None = None
    reply_to_guid: str | None = None
    reply_to_id: UUID | None = None


class IngestResult(Schema):
    inserted: int
    revision: int


class GenerationCreate(Schema):
    budget_preset: BudgetPreset = "comfortable"


class GenerationRead(Schema):
    id: UUID
    trip_id: UUID
    transcript_revision: int
    budget_preset: BudgetPreset
    previous_plan_id: UUID | None
    status: Literal["queued", "running", "succeeded", "failed"]
    plan_id: UUID | None = None
    error: str | None = None


class GenerationResult(Schema):
    generation: GenerationRead


class PlanNode(Schema):
    id: str = Field(min_length=1, max_length=100)
    kind: Literal["place", "activity", "lodging"] = "place"
    role: Literal["start", "stop", "end"] = "stop"
    quest: Literal["main", "side"] = "main"
    anchor: str | None = None
    title: str = Field(min_length=1, max_length=200)
    notes: str = Field(default="", max_length=500)
    source_message_ids: list[UUID] = Field(default_factory=list, max_length=500)
    place_id: str | None = Field(default=None, max_length=300)
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)
    category: Literal["eat", "do", "stay", "along_the_way"] | None = None
    arrive: AwareDatetime | None = None
    depart: AwareDatetime | None = None
    duration_min: int | None = Field(default=None, ge=0)
    detour_min: int | None = Field(default=None, ge=0)
    est_cost: tuple[float, float] | None = None
    cost_basis: str | None = None
    hours_status: Literal["verified", "unknown"] = "unknown"
    source: Literal["group", "suggested", "added"] = "group"
    why: str = ""
    owner_member_id: UUID | None = None

    @model_validator(mode="after")
    def validate_values(self) -> Self:
        if self.est_cost is not None and not 0 <= self.est_cost[0] <= self.est_cost[1]:
            raise ValueError("Cost range must be nonnegative and ordered")
        if self.arrive and self.depart and self.depart < self.arrive:
            raise ValueError("Departure cannot precede arrival")
        return self


class PlanEdge(Schema):
    id: str = Field(min_length=1, max_length=100)
    source: str
    target: str
    kind: Literal["precedes", "travel", "alternative", "detour"]
    drive_min: float | None = Field(default=None, ge=0)
    distance_m: int | None = Field(default=None, ge=0)
    polyline: str | None = None
    detour_min: int | None = Field(default=None, ge=0)


class PlanGraph(Schema):
    nodes: list[PlanNode] = Field(default_factory=list, max_length=500)
    edges: list[PlanEdge] = Field(default_factory=list, max_length=2000)

    @model_validator(mode="after")
    def valid_references(self) -> Self:
        node_ids = {node.id for node in self.nodes}
        main_ids = {node.id for node in self.nodes if node.quest == "main"}
        if len(node_ids) != len(self.nodes):
            raise ValueError("Node IDs must be unique")
        if len({edge.id for edge in self.edges}) != len(self.edges):
            raise ValueError("Edge IDs must be unique")
        for node in self.nodes:
            if node.quest == "side" and node.anchor not in main_ids:
                raise ValueError("Side quests must anchor to a main node")
        for edge in self.edges:
            if edge.source not in node_ids or edge.target not in node_ids:
                raise ValueError("Edges must reference existing nodes")
            if edge.source == edge.target:
                raise ValueError("Self-edges are not supported")
        return self


class PlanDay(Schema):
    date: date
    start_at: AwareDatetime
    end_at: AwareDatetime
    node_ids: list[str]


class Conflict(Schema):
    node_id: str
    kind: Literal["split_vote", "over_budget", "does_not_fit", "hours"]
    detail: str


class PlanContent(Schema):
    title: str = Field(min_length=1, max_length=200)
    budget_preset: BudgetPreset = "comfortable"
    currency: Literal["USD"] = "USD"
    timezone: str = "UTC"
    derived_stale: bool = False
    graph: PlanGraph
    days: list[PlanDay] = Field(default_factory=list)
    per_person_estimate: tuple[float, float] | None = None
    estimate_scope: Literal["food_and_activities_main_quest"] = "food_and_activities_main_quest"
    estimate_is_partial: bool = False
    unpriced_node_ids: list[str] = Field(default_factory=list)
    excluded_costs: list[str] = Field(
        default_factory=lambda: [
            "lodging",
            "fuel",
            "tolls",
            "parking",
            "taxes",
            "tips",
            "side quests",
        ]
    )
    conflicts: list[Conflict] = Field(default_factory=list)
    changed_from_previous: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list, max_length=100)
    open_questions: list[str] = Field(default_factory=list, max_length=100)
    warnings: list[str] = Field(default_factory=list, max_length=100)


class PlanRead(Schema):
    id: UUID
    trip_id: UUID
    generation_id: UUID
    budget_preset: BudgetPreset
    revision: int
    status: Literal["draft", "accepted"]
    accepted_at: datetime | None
    content: PlanContent


class PlanResult(Schema):
    plan: PlanRead


class PlanUpdate(Schema):
    revision: int = Field(ge=1)
    content: PlanContent


class PlanAccept(Schema):
    revision: int = Field(ge=1)
