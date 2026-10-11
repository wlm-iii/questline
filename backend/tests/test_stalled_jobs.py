from uuid import UUID

import pytest
from sqlalchemy import text
from test_integration import drain, request_generation, seed

from questline.jobs import retry_stalled_jobs
from questline.providers.fake import FakePlanner
from questline.services.plan_generation import generate_plan

pytestmark = pytest.mark.integration


async def test_job_from_a_dead_worker_is_retried_and_finishes(api):
    client, app = api
    trip_id = await seed(client)
    generation = (await request_generation(client, trip_id)).json()["generation"]
    async with app.state.sessions() as session:
        # Simulate a worker killed mid-build: its job is `doing` and its heartbeat is old.
        worker = await session.scalar(
            text(
                "INSERT INTO procrastinate_workers (last_heartbeat) "
                "VALUES (now() - interval '1 hour') RETURNING id"
            )
        )
        await session.execute(
            text("UPDATE procrastinate_jobs SET status = 'doing', worker_id = :w"),
            {"w": worker},
        )
        await session.execute(
            text("UPDATE plan_generations SET status = 'running' WHERE id = :g"),
            {"g": generation["id"]},
        )
        await session.commit()
    async with app.state.queue.open_async():
        assert await retry_stalled_jobs(app.state.queue) == 1
    await drain(app)
    result = (await client.get(f"/api/v1/plan-generations/{generation['id']}")).json()
    assert result["generation"]["status"] == "succeeded"
    assert result["generation"]["plan_id"] is not None


async def test_build_that_never_ran_times_out_instead_of_blocking(api):
    client, app = api
    trip_id = await seed(client)
    stuck = (await request_generation(client, trip_id, "stuck")).json()["generation"]
    async with app.state.sessions() as session:
        await session.execute(
            text(
                "UPDATE plan_generations SET created_at = now() - interval '10 minutes' "
                "WHERE id = :g"
            ),
            {"g": stuck["id"]},
        )
        await session.commit()
    fresh = await request_generation(client, trip_id, "fresh", "treat")
    assert fresh.status_code == 202, fresh.text
    old = (await client.get(f"/api/v1/plan-generations/{stuck['id']}")).json()["generation"]
    assert old["status"] == "failed" and "timed out" in old["error"]
    # If the old job runs late anyway, it must not replace newer plans.
    await generate_plan(UUID(stuck["id"]), app.state.sessions, FakePlanner())
    assert (await client.get(f"/api/v1/plan-generations/{stuck['id']}")).json()["generation"][
        "plan_id"
    ] is None
