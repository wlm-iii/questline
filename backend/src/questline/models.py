import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    MetaData,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    metadata = MetaData(schema="questline")


class Trip(Base):
    __tablename__ = "trips"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200))  # Preserve legacy names; API limit is 100.
    origin: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    destination: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    timezone: Mapped[str] = mapped_column(String(100), default="UTC")
    budget_preset: Mapped[str] = mapped_column(String(20), default="comfortable")
    current_plan_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("plans.id", use_alter=True, name="trips_current_plan_fk")
    )
    discord_channel_id: Mapped[str | None] = mapped_column(String(200))
    imessage_chat_guid: Mapped[str | None] = mapped_column(String(300), unique=True)
    revision: Mapped[int] = mapped_column(Integer, default=0)
    unresolved_mentions: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Member(Base):
    __tablename__ = "members"
    __table_args__ = (UniqueConstraint("trip_id", "imessage_handle"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    trip_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("trips.id"), index=True)
    name: Mapped[str] = mapped_column(String(60))
    token_hash: Mapped[str | None] = mapped_column(String(64), unique=True)
    imessage_handle: Mapped[str | None] = mapped_column(String(200))
    discord_user_id: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (UniqueConstraint("trip_id", "external_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    trip_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("trips.id"), index=True)
    external_id: Mapped[str] = mapped_column(String(200))
    author_id: Mapped[str] = mapped_column(String(200))
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    text: Mapped[str] = mapped_column(String(10_000))
    member_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("members.id"))
    source: Mapped[str] = mapped_column(String(20), default="web")
    import_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("imports.id"), index=True)
    reply_to_guid: Mapped[str | None] = mapped_column(String(200))
    reply_to_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("messages.id"))


class PlanGeneration(Base):
    __tablename__ = "plan_generations"
    __table_args__ = (UniqueConstraint("trip_id", "idempotency_key"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    trip_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("trips.id"), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(200))
    transcript_revision: Mapped[int] = mapped_column(Integer)
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB)
    budget_preset: Mapped[str] = mapped_column(String(20), default="comfortable")
    requested_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("members.id"))
    previous_plan_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("plans.id", use_alter=True, name="generation_previous_plan_fk")
    )
    status: Mapped[str] = mapped_column(String(20), default="queued")
    error: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Plan(Base):
    __tablename__ = "plans"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    trip_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("trips.id"), index=True)
    generation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("plan_generations.id"), unique=True)
    budget_preset: Mapped[str] = mapped_column(String(20), default="comfortable")
    revision: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20), default="draft")
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    content: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Import(Base):
    __tablename__ = "imports"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    trip_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("trips.id"), index=True)
    member_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("members.id"))
    source: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="queued")
    message_count: Mapped[int] = mapped_column(Integer, default=0)
    message_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
    error: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Place(Base):
    __tablename__ = "places"
    __table_args__ = (
        UniqueConstraint("trip_id", "google_place_id"),
        CheckConstraint("lat BETWEEN -90 AND 90 AND lng BETWEEN -180 AND 180"),
        CheckConstraint("price_level IS NULL OR price_level BETWEEN 0 AND 4"),
        CheckConstraint(
            "(est_cost_low IS NULL AND est_cost_high IS NULL) OR "
            "(est_cost_low IS NOT NULL AND est_cost_high IS NOT NULL "
            "AND est_cost_low >= 0 AND est_cost_high >= est_cost_low)"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    trip_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("trips.id"), index=True)
    google_place_id: Mapped[str] = mapped_column(String(300))
    name: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(20))
    address: Mapped[str] = mapped_column(String(500))
    lat: Mapped[float] = mapped_column(Float)
    lng: Mapped[float] = mapped_column(Float)
    google_maps_uri: Mapped[str | None] = mapped_column(String(1000))
    price_level: Mapped[int | None] = mapped_column(Integer)
    est_cost_low: Mapped[float | None] = mapped_column(Float)
    est_cost_high: Mapped[float | None] = mapped_column(Float)
    cost_basis: Mapped[str | None] = mapped_column(String(500))
    source: Mapped[str] = mapped_column(String(20))
    mentioned_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("members.id"))
    mentioned_by_name: Mapped[str | None] = mapped_column(String(200))
    source_message_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Vote(Base):
    __tablename__ = "votes"
    __table_args__ = (
        UniqueConstraint("place_id", "member_id"),
        CheckConstraint("kind IN ('in', 'ok', 'out')"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    trip_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("trips.id"), index=True)
    place_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("places.id"), index=True)
    member_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("members.id"))
    kind: Mapped[str] = mapped_column(String(10))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    trip_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("trips.id"), index=True)
    place_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("places.id"))
    text: Mapped[str] = mapped_column(String(200))
    owner_member_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("members.id"))
    done_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("members.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Checkin(Base):
    __tablename__ = "checkins"
    __table_args__ = (UniqueConstraint("trip_id", "place_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    trip_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("trips.id"), index=True)
    place_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("places.id"))
    member_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("members.id"))
    completed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
