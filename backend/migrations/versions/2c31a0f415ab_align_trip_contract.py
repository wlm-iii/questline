"""Rename conversations and align request snapshots without deleting existing plans.

Revision ID: 2c31a0f415ab
Revises: f8a6451f9eac
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "2c31a0f415ab"
down_revision = "f8a6451f9eac"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.rename_table("conversations", "trips", schema="questline")
    op.alter_column("trips", "title", new_column_name="name", schema="questline")
    # Preserve legacy names (up to 200 chars). New API requests enforce 100 chars.
    for table in ("messages", "plan_generations", "plans"):
        op.alter_column(table, "conversation_id", new_column_name="trip_id", schema="questline")
        op.drop_index(f"ix_questline_{table}_conversation_id", table_name=table, schema="questline")
        op.create_index(f"ix_questline_{table}_trip_id", table, ["trip_id"], schema="questline")
    for name in ("origin", "destination"):
        op.add_column(
            "trips", sa.Column(name, postgresql.JSONB(), nullable=True), schema="questline"
        )
    for name in ("start_date", "end_date"):
        op.add_column("trips", sa.Column(name, sa.Date(), nullable=True), schema="questline")
    for name, default, length in (("timezone", "UTC", 100), ("budget_preset", "comfortable", 20)):
        op.add_column(
            "trips",
            sa.Column(name, sa.String(length), nullable=False, server_default=default),
            schema="questline",
        )
        op.alter_column("trips", name, server_default=None, schema="questline")
    op.add_column(
        "trips",
        sa.Column("unresolved_mentions", postgresql.JSONB(), nullable=False, server_default="[]"),
        schema="questline",
    )
    op.alter_column("trips", "unresolved_mentions", server_default=None, schema="questline")
    op.add_column(
        "trips", sa.Column("current_plan_id", sa.Uuid(), nullable=True), schema="questline"
    )
    op.create_foreign_key(
        "trips_current_plan_fk",
        "trips",
        "plans",
        ["current_plan_id"],
        ["id"],
        source_schema="questline",
        referent_schema="questline",
    )
    op.create_table(
        "members",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("trip_id", sa.Uuid(), sa.ForeignKey("questline.trips.id"), nullable=False),
        sa.Column("name", sa.String(60), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        schema="questline",
    )
    op.create_index("ix_questline_members_trip_id", "members", ["trip_id"], schema="questline")
    for table in ("plans", "plan_generations"):
        op.add_column(
            table,
            sa.Column("budget_preset", sa.String(20), nullable=False, server_default="comfortable"),
            schema="questline",
        )
        op.alter_column(table, "budget_preset", server_default=None, schema="questline")
    op.add_column(
        "plans",
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        schema="questline",
    )
    op.add_column(
        "plan_generations",
        sa.Column("previous_plan_id", sa.Uuid(), nullable=True),
        schema="questline",
    )
    op.create_foreign_key(
        "generation_previous_plan_fk",
        "plan_generations",
        "plans",
        ["previous_plan_id"],
        ["id"],
        source_schema="questline",
        referent_schema="questline",
    )
    op.add_column(
        "plan_generations",
        sa.Column("snapshot", postgresql.JSONB(), nullable=True),
        schema="questline",
    )
    op.execute("""UPDATE questline.plan_generations SET snapshot = jsonb_build_object(
        'messages', transcript, 'members', '[]'::jsonb, 'places', '[]'::jsonb,
        'votes', '[]'::jsonb, 'budget_preset', budget_preset, 'timezone', timezone)""")
    op.alter_column("plan_generations", "snapshot", nullable=False, schema="questline")
    for name in ("transcript", "instructions", "timezone"):
        op.drop_column("plan_generations", name, schema="questline")


def downgrade() -> None:
    op.add_column(
        "plan_generations",
        sa.Column("transcript", postgresql.JSONB(), nullable=True),
        schema="questline",
    )
    op.add_column(
        "plan_generations",
        sa.Column(
            "instructions", sa.String(2000), nullable=False, server_default="Suggest a trip plan"
        ),
        schema="questline",
    )
    op.add_column(
        "plan_generations",
        sa.Column("timezone", sa.String(100), nullable=False, server_default="UTC"),
        schema="questline",
    )
    op.execute(
        "UPDATE questline.plan_generations SET transcript = snapshot->'messages', "
        "timezone = COALESCE(snapshot->>'timezone', 'UTC')"
    )
    op.alter_column("plan_generations", "transcript", nullable=False, schema="questline")
    for name in ("instructions", "timezone"):
        op.alter_column("plan_generations", name, server_default=None, schema="questline")
    op.drop_constraint(
        "generation_previous_plan_fk", "plan_generations", type_="foreignkey", schema="questline"
    )
    for name in ("snapshot", "previous_plan_id", "budget_preset"):
        op.drop_column("plan_generations", name, schema="questline")
    for name in ("budget_preset", "accepted_at"):
        op.drop_column("plans", name, schema="questline")
    op.drop_table("members", schema="questline")
    op.drop_constraint("trips_current_plan_fk", "trips", type_="foreignkey", schema="questline")
    for name in (
        "origin",
        "destination",
        "start_date",
        "end_date",
        "timezone",
        "budget_preset",
        "unresolved_mentions",
        "current_plan_id",
    ):
        op.drop_column("trips", name, schema="questline")
    for table in ("messages", "plan_generations", "plans"):
        op.drop_index(f"ix_questline_{table}_trip_id", table_name=table, schema="questline")
        op.alter_column(table, "trip_id", new_column_name="conversation_id", schema="questline")
        op.create_index(
            f"ix_questline_{table}_conversation_id", table, ["conversation_id"], schema="questline"
        )
    op.alter_column(
        "trips", "name", type_=sa.String(200), new_column_name="title", schema="questline"
    )
    op.rename_table("trips", "conversations", schema="questline")
