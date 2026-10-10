"""Exercise the alignment migration with real legacy rows, not just an empty DB."""

import os
import subprocess
from uuid import uuid4

import psycopg
import pytest
from psycopg.types.json import Jsonb

pytestmark = pytest.mark.integration


def test_alignment_preserves_legacy_rows(database_url):
    env = {**os.environ, "DATABASE_URL": database_url, "APP_ENV": "test"}

    def migrate(*args):
        subprocess.run(["alembic", *args], env=env, check=True)

    migrate("downgrade", "f8a6451f9eac")
    trip_id, generation_id, plan_id = uuid4(), uuid4(), uuid4()
    transcript = [
        {
            "id": str(uuid4()),
            "external_id": "legacy-1",
            "author_id": "Alice",
            "sent_at": "2026-10-10T12:00:00Z",
            "text": "Let's go hiking",
        }
    ]
    content = {"title": "Legacy plan", "graph": {"nodes": [], "edges": []}}
    try:
        with psycopg.connect(database_url) as connection:
            connection.execute(
                "INSERT INTO questline.conversations (id, title, revision) VALUES (%s, %s, 1)",
                (trip_id, "A" * 150),
            )
            connection.execute(
                """INSERT INTO questline.messages
                   (id, conversation_id, external_id, author_id, sent_at, text)
                   VALUES (%s, %s, 'legacy-1', 'Alice', '2026-10-10T12:00:00Z', 'Legacy text')""",
                (transcript[0]["id"], trip_id),
            )
            connection.execute(
                """INSERT INTO questline.plan_generations
                   (id, conversation_id, idempotency_key, transcript_revision, transcript,
                    instructions, timezone, status)
                   VALUES (%s, %s, 'legacy-key', 1, %s,
                           'Legacy instructions', 'UTC', 'succeeded')""",
                (generation_id, trip_id, Jsonb(transcript)),
            )
            connection.execute(
                """INSERT INTO questline.plans
                   (id, conversation_id, generation_id, revision, status, content)
                   VALUES (%s, %s, %s, 1, 'draft', %s)""",
                (plan_id, trip_id, generation_id, Jsonb(content)),
            )
        migrate("upgrade", "head")
        with psycopg.connect(database_url) as connection:
            assert connection.execute(
                "SELECT name FROM questline.trips WHERE id = %s", (trip_id,)
            ).fetchone() == ("A" * 150,)
            assert connection.execute(
                "SELECT snapshot->'messages' FROM questline.plan_generations WHERE id = %s",
                (generation_id,),
            ).fetchone() == (transcript,)
            assert connection.execute(
                "SELECT content FROM questline.plans WHERE id = %s", (plan_id,)
            ).fetchone() == (content,)
            assert connection.execute(
                "SELECT text, source FROM questline.messages WHERE trip_id = %s", (trip_id,)
            ).fetchone() == ("Legacy text", "web")
        migrate("downgrade", "f8a6451f9eac")
        with psycopg.connect(database_url) as connection:
            assert connection.execute(
                "SELECT transcript FROM questline.plan_generations WHERE id = %s", (generation_id,)
            ).fetchone() == (transcript,)
    finally:
        migrate("upgrade", "head")
        with psycopg.connect(database_url) as connection:
            connection.execute("TRUNCATE questline.trips CASCADE")
