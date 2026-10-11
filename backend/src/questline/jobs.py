"""Run `python -m questline.jobs schema` once, then `python -m questline.jobs worker`."""

import argparse
import asyncio
import logging
from uuid import UUID

import procrastinate
import psycopg
from procrastinate.schema import SchemaManager
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from questline.config import Settings, get_settings
from questline.db import configure_queue_connection, create_database
from questline.services.extraction import extract_places
from questline.services.plan_generation import generate_plan

logger = logging.getLogger(__name__)
# Workers send a heartbeat every 10 seconds; three missed beats means the worker is gone.
STALLED_SECONDS = 30


def create_queue(settings: Settings, sessions: async_sessionmaker[AsyncSession]):
    app = procrastinate.App(
        connector=procrastinate.PsycopgConnector(
            conninfo=settings.psycopg_url,
            min_size=1,
            max_size=3,
            configure=configure_queue_connection,
        )
    )

    @app.task(name="questline.generate_plan", queue="plans")
    async def generate_task(generation_id: str) -> None:
        await generate_plan(UUID(generation_id), sessions, settings=settings)

    @app.task(name="questline.extract_places", queue="plans")
    async def extract_task(import_id: str) -> None:
        await extract_places(UUID(import_id), sessions, settings=settings)

    # A worker that dies mid-job (crash, kill, restart) leaves its job in `doing`, still holding
    # the trip's queue lock, so every later build or import for that trip would wait forever.
    @app.periodic(cron="* * * * *", periodic_id="retry_stalled_jobs")
    @app.task(name="questline.retry_stalled_jobs", queue="plans", queueing_lock="retry_stalled")
    async def retry_stalled_task(timestamp: int) -> None:
        await retry_stalled_jobs(app)

    return app, generate_task, extract_task


async def retry_stalled_jobs(app: procrastinate.App) -> int:
    """Requeue jobs whose worker stopped sending heartbeats. Both job kinds are safe to rerun."""
    stalled = list(await app.job_manager.get_stalled_jobs(seconds_since_heartbeat=STALLED_SECONDS))
    for job in stalled:
        logger.warning("Retrying stalled job %s (%s)", job.id, job.task_name)
        await app.job_manager.retry_job(job)
    return len(stalled)


async def install_queue_schema(settings: Settings) -> None:
    # Bootstrap only. Procrastinate is pinned; upgrades require its SQL migrations.
    async with await psycopg.AsyncConnection.connect(settings.psycopg_url) as connection:
        # Do not rely on startup options: Supabase session pooling may ignore them.
        await connection.execute("SET LOCAL search_path TO questline")
        # Serialize simultaneous setup commands across teammates/processes.
        await connection.execute("SELECT pg_advisory_xact_lock(71623841)")
        cursor = await connection.execute("SELECT to_regclass('questline.procrastinate_jobs')")
        row = await cursor.fetchone()
        if row and row[0] is None:
            await connection.execute(SchemaManager.get_schema())


async def run(command: str) -> None:
    settings = get_settings()
    if command == "schema":
        await install_queue_schema(settings)
        return
    engine, sessions = create_database(settings)
    app, _, _ = create_queue(settings, sessions)
    try:
        async with app.open_async():
            await app.run_worker_async(queues=["plans"], concurrency=2)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["schema", "worker"])
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run(args.command))
