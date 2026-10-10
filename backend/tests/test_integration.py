import asyncio
from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy import select, text

from questline.models import PlanGeneration
from questline.providers.fake import FakePlanner
from questline.services.plan_generation import generate_plan

pytestmark = pytest.mark.integration

TRIP = {
    "name": "Weekend trip",
    "origin": "San Jose, CA",
    "destination": "Big Sur, CA",
    "start_date": "2026-10-17",
    "end_date": "2026-10-18",
    "timezone": "America/Los_Angeles",
    "organizer_name": "Alice",
}
MESSAGE = {
    "external_id": "message-1",
    "author_id": "alice",
    "sent_at": "2026-10-10T14:30:00Z",
    "text": "Let's go hiking Saturday and be back for dinner.",
}


async def seed(client):
    response = await client.post("/api/v1/trips", json=TRIP)
    assert response.status_code == 201, response.text
    trip_id = response.json()["trip"]["id"]
    response = await client.post(
        f"/api/v1/trips/{trip_id}/messages/batch", json={"messages": [MESSAGE]}
    )
    assert response.json() == {"inserted": 1, "revision": 2}
    return trip_id


async def request_generation(client, trip_id, key="generation-1", preset="comfortable"):
    return await client.post(
        f"/api/v1/trips/{trip_id}/plan-generations",
        json={"budget_preset": preset},
        headers={"Idempotency-Key": key},
    )


async def drain(app):
    async with app.state.queue.open_async():
        await app.state.queue.run_worker_async(wait=False, queues=["plans"], concurrency=1)


async def test_end_to_end_worker_and_edit_conflicts(api):
    client, app = api
    trip_id = await seed(client)
    response = await request_generation(client, trip_id)
    assert response.status_code == 202, response.text
    generation = response.json()["generation"]
    assert generation["status"] == "queued"
    assert (await request_generation(client, trip_id)).json()["generation"]["id"] == generation[
        "id"
    ]
    assert (await request_generation(client, trip_id, "new-key")).json()["generation"][
        "id"
    ] == generation["id"]
    conflict = await request_generation(client, trip_id, "other-preset", "shoestring")
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "plan_in_progress"
    await drain(app)
    result = (await client.get(f"/api/v1/plan-generations/{generation['id']}")).json()["generation"]
    assert result["status"] == "succeeded", result
    plan_url = f"/api/v1/plans/{result['plan_id']}"
    plan = (await client.get(plan_url)).json()["plan"]
    assert plan["status"] == "draft"
    plan["content"]["title"] = "Our edited trip"
    patch = {"revision": plan["revision"], "content": plan["content"]}
    edited = await client.patch(plan_url, json=patch)
    assert edited.json()["plan"]["revision"] == 2
    assert (await client.patch(plan_url, json=patch)).status_code == 409
    accepted = await client.post(f"{plan_url}/accept", json={"revision": 2})
    assert accepted.json()["plan"]["accepted_at"] is not None
    assert (await client.post(f"{plan_url}/accept", json={"revision": 2})).status_code == 409
    await generate_plan(UUID(generation["id"]), app.state.sessions, FakePlanner())
    assert (await client.get(plan_url)).json()["plan"]["content"]["title"] == "Our edited trip"
    new_generation = (
        await request_generation(client, trip_id, "generation-2", "shoestring")
    ).json()["generation"]
    await drain(app)
    state = (await client.get(f"/api/v1/trips/{trip_id}")).json()
    assert state["current_plan"]["generation_id"] == new_generation["id"]
    assert state["trip"]["budget_preset"] == "shoestring"
    unchanged = await client.get(f"/api/v1/trips/{trip_id}?revision={state['revision']}")
    assert unchanged.json() == {"unchanged": True, "revision": state["revision"]}


async def test_transcript_deduplication_snapshot_and_idempotency(api):
    client, app = api
    trip_id = await seed(client)
    url = f"/api/v1/trips/{trip_id}/messages/batch"
    duplicate = await client.post(url, json={"messages": [MESSAGE, MESSAGE]})
    assert duplicate.json() == {"inserted": 0, "revision": 2}
    conflict = await client.post(
        url, json={"messages": [{**MESSAGE, "external_id": "new"}, {**MESSAGE, "text": "Changed"}]}
    )
    assert conflict.status_code == 409
    generation = (await request_generation(client, trip_id)).json()["generation"]
    await client.post(url, json={"messages": [{**MESSAGE, "external_id": "message-2"}]})
    async with app.state.sessions() as session:
        saved = await session.get(PlanGeneration, UUID(generation["id"]))
        assert len(saved.snapshot["messages"]) == 1
        assert len(saved.snapshot["members"]) == 1
        assert set(saved.snapshot) >= {"places", "votes", "members", "budget_preset"}
        assert saved.transcript_revision == 2
        assert await session.scalar(text("SELECT count(*) FROM questline.procrastinate_jobs")) == 1
    assert (await request_generation(client, trip_id, preset="treat")).status_code == 409


async def test_empty_missing_and_oversized_transcripts(api):
    client, app = api
    assert (await request_generation(client, str(uuid4()))).status_code == 404
    empty = (await client.post("/api/v1/trips", json=TRIP)).json()["trip"]["id"]
    assert (await request_generation(client, empty)).status_code == 422
    app.state.settings.max_transcript_chars = 5
    response = await client.post(
        f"/api/v1/trips/{empty}/messages/batch", json={"messages": [MESSAGE]}
    )
    assert response.status_code == 413
    assert (await request_generation(client, empty)).status_code == 422


async def test_generation_and_queue_insert_roll_back_together(api):
    client, app = api
    trip_id = await seed(client)
    original = app.state.generate_task

    class BrokenQueue:
        def configure(self, **kwargs):
            return self

        async def defer_async(self, **kwargs):
            raise RuntimeError("Simulated queue failure")

    app.state.generate_task = BrokenQueue()
    with pytest.raises(RuntimeError, match="Simulated"):
        await request_generation(client, trip_id)
    app.state.generate_task = original
    async with app.state.sessions() as session:
        assert await session.scalar(select(PlanGeneration.id)) is None
    assert (await request_generation(client, trip_id)).status_code == 202


async def test_failed_provider_preserves_current_plan(api):
    client, app = api
    trip_id = await seed(client)
    await request_generation(client, trip_id)
    await drain(app)
    before = (await client.get(f"/api/v1/trips/{trip_id}")).json()
    generation = (await request_generation(client, trip_id, "failure", "treat")).json()[
        "generation"
    ]

    class BrokenPlanner:
        async def generate(self, snapshot, request):
            raise ValueError("secret-provider-error")

    await generate_plan(UUID(generation["id"]), app.state.sessions, BrokenPlanner())
    result = await client.get(f"/api/v1/plan-generations/{generation['id']}")
    assert result.json()["generation"]["status"] == "failed"
    assert "secret-provider-error" not in result.text
    after = (await client.get(f"/api/v1/trips/{trip_id}")).json()
    assert after["trip"]["current_plan_id"] == before["trip"]["current_plan_id"]
    assert after["trip"]["budget_preset"] == "comfortable"
    assert after["revision"] > before["revision"]


async def test_member_auth_and_cross_trip_references(api):
    client, app = api
    created = (await client.post("/api/v1/trips", json=TRIP)).json()
    trip_id = created["trip"]["id"]
    other = (await client.post("/api/v1/trips", json=TRIP)).json()["trip"]["id"]
    client.headers.pop("Authorization")
    assert (await client.get(f"/api/v1/trips/{trip_id}")).status_code == 401
    client.headers["X-Member-Token"] = created["member_token"]
    state = (await client.get(f"/api/v1/trips/{trip_id}")).json()
    assert "token_hash" not in str(state)
    assert (await client.get(f"/api/v1/trips/{other}")).status_code == 422
    join = await client.post(f"/api/v1/trips/{trip_id}/members", json={"name": "  Sam  "})
    assert join.json()["member"]["name"] == "Sam"
    assert "member_token" in join.json()
    await client.post(f"/api/v1/trips/{trip_id}/messages/batch", json={"messages": [MESSAGE]})
    generation = (await request_generation(client, trip_id)).json()["generation"]
    await drain(app)
    result = (await client.get(f"/api/v1/plan-generations/{generation['id']}")).json()["generation"]
    plan_url = f"/api/v1/plans/{result['plan_id']}"
    plan = (await client.get(plan_url)).json()["plan"]
    response = await client.patch(plan_url, json={"revision": 1, "content": plan["content"]})
    assert response.status_code == 403
    assert (await client.post(f"{plan_url}/accept", json={"revision": 1})).status_code == 200


async def test_in_process_worker_fallback(api):
    from questline.main import create_app

    client, original = api
    trip_id = await seed(client)
    settings = original.state.settings.model_copy(update={"run_worker_in_process": True})
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
            headers={"Authorization": "Bearer test-token"},
        ) as worker_client:
            generation = (await request_generation(worker_client, trip_id)).json()["generation"]
            async with asyncio.timeout(10):
                while True:
                    result = (
                        await worker_client.get(f"/api/v1/plan-generations/{generation['id']}")
                    ).json()["generation"]
                    if result["status"] == "succeeded":
                        break
                    await asyncio.sleep(0.05)


async def test_unimplemented_real_providers_fail_explicitly(api):
    client, app = api
    trip_id = await seed(client)
    app.state.settings.planner_provider = "gemini"
    response = await request_generation(client, trip_id)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "provider_unavailable"
    app.state.settings.maps_provider = "google"
    assert (await client.post("/api/v1/trips", json=TRIP)).status_code == 503
