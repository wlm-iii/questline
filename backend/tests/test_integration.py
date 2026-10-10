from uuid import UUID, uuid4

import pytest
from sqlalchemy import select, text

from questline.models import PlanGeneration
from questline.providers.fake import FakePlanner
from questline.services.plan_generation import generate_plan

pytestmark = pytest.mark.integration

MESSAGE = {
    "external_id": "message-1",
    "author_id": "alice",
    "sent_at": "2026-07-10T14:30:00Z",
    "text": "Let's go hiking Saturday and be back for dinner.",
}


async def seed(client):
    response = await client.post("/api/v1/conversations", json={"title": "Weekend trip"})
    assert response.status_code == 201
    conversation_id = response.json()["id"]
    response = await client.post(
        f"/api/v1/conversations/{conversation_id}/messages/batch", json={"messages": [MESSAGE]}
    )
    assert response.json() == {"inserted": 1, "transcript_revision": 1}
    return conversation_id


async def request_generation(client, conversation_id, key="generation-1"):
    return await client.post(
        f"/api/v1/conversations/{conversation_id}/plan-generations",
        json={"timezone": "America/Los_Angeles"},
        headers={"Idempotency-Key": key},
    )


async def test_end_to_end_worker_and_edit_conflicts(api):
    client, app = api
    assert (await client.get("/health/ready")).status_code == 200
    conversation_id = await seed(client)
    response = await request_generation(client, conversation_id)
    assert response.status_code == 202, response.text
    generation = response.json()
    assert generation["status"] == "queued"
    repeated = await request_generation(client, conversation_id)
    assert repeated.json()["id"] == generation["id"]

    # Exercise the real queue and worker, not FastAPI BackgroundTasks or direct mocks.
    async with app.state.queue.open_async():
        await app.state.queue.run_worker_async(wait=False, queues=["plans"], concurrency=1)
    result = (await client.get(f"/api/v1/plan-generations/{generation['id']}")).json()
    assert result["status"] == "succeeded", result
    plan_url = f"/api/v1/plans/{result['plan_id']}"
    plan = (await client.get(plan_url)).json()
    plan["content"]["title"] = "Our edited trip"
    patch = {"revision": plan["revision"], "content": plan["content"]}
    edited = await client.patch(plan_url, json=patch)
    assert edited.status_code == 200
    assert edited.json()["revision"] == 2
    assert (await client.patch(plan_url, json=patch)).status_code == 409
    accepted = await client.post(f"{plan_url}/accept", json={"revision": 2})
    assert accepted.json()["status"] == "accepted"
    assert (await client.post(f"{plan_url}/accept", json={"revision": 2})).status_code == 409

    # Replaying a completed task must not duplicate or overwrite the edited plan.
    await generate_plan(UUID(generation["id"]), app.state.sessions, FakePlanner())
    assert (await client.get(plan_url)).json()["content"]["title"] == "Our edited trip"
    new_generation = (await request_generation(client, conversation_id, "generation-2")).json()
    async with app.state.queue.open_async():
        await app.state.queue.run_worker_async(wait=False, queues=["plans"], concurrency=1)
    new_result = (await client.get(f"/api/v1/plan-generations/{new_generation['id']}")).json()
    assert new_result["plan_id"] != result["plan_id"]
    assert (await client.get(plan_url)).json()["content"]["title"] == "Our edited trip"


async def test_transcript_deduplication_snapshot_and_idempotency(api):
    client, app = api
    conversation_id = await seed(client)
    message_url = f"/api/v1/conversations/{conversation_id}/messages/batch"
    duplicate = await client.post(message_url, json={"messages": [MESSAGE, MESSAGE]})
    assert duplicate.json() == {"inserted": 0, "transcript_revision": 1}
    conflict = await client.post(
        message_url,
        json={"messages": [{**MESSAGE, "external_id": "new"}, {**MESSAGE, "text": "Changed"}]},
    )
    assert conflict.status_code == 409
    generation = (await request_generation(client, conversation_id)).json()
    await client.post(message_url, json={"messages": [{**MESSAGE, "external_id": "message-2"}]})
    async with app.state.sessions() as session:
        snapshot = await session.get(PlanGeneration, UUID(generation["id"]))
        assert (
            len(snapshot.transcript) == 1
        )  # Conflicting batch rolled back, later message excluded.
        assert snapshot.transcript_revision == 1
        assert await session.scalar(text("SELECT count(*) FROM questline.procrastinate_jobs")) == 1
    conflict = await client.post(
        f"/api/v1/conversations/{conversation_id}/plan-generations",
        json={"instructions": "Different instructions"},
        headers={"Idempotency-Key": "generation-1"},
    )
    assert conflict.status_code == 409


async def test_empty_missing_and_oversized_transcripts(api):
    client, app = api
    assert (await request_generation(client, str(uuid4()))).status_code == 404
    empty = (await client.post("/api/v1/conversations", json={"title": "Empty"})).json()["id"]
    assert (await request_generation(client, empty)).status_code == 422
    app.state.settings.max_transcript_chars = 5
    response = await client.post(
        f"/api/v1/conversations/{empty}/messages/batch", json={"messages": [MESSAGE]}
    )
    assert response.status_code == 413
    assert (await request_generation(client, empty)).status_code == 422


async def test_generation_and_queue_insert_roll_back_together(api):
    client, app = api
    conversation_id = await seed(client)
    original = app.state.generate_task

    class BrokenQueue:
        def configure(self, **kwargs):
            return self

        async def defer_async(self, **kwargs):
            raise RuntimeError("Simulated queue failure")

    app.state.generate_task = BrokenQueue()
    with pytest.raises(RuntimeError, match="Simulated"):
        await request_generation(client, conversation_id)
    app.state.generate_task = original
    async with app.state.sessions() as session:
        assert await session.scalar(select(PlanGeneration.id)) is None
    assert (await request_generation(client, conversation_id)).status_code == 202


async def test_failed_provider_does_not_expose_error_details(api):
    client, app = api
    conversation_id = await seed(client)
    generation = (await request_generation(client, conversation_id)).json()

    class BrokenPlanner:
        async def generate(self, transcript, request):
            raise ValueError("secret-provider-error")

    await generate_plan(UUID(generation["id"]), app.state.sessions, BrokenPlanner())
    result = await client.get(f"/api/v1/plan-generations/{generation['id']}")
    assert result.json()["status"] == "failed"
    assert "secret-provider-error" not in result.text
