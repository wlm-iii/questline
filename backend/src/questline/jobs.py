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
from questline.providers.fake import FakePlanner
from questline.services.extraction import extract_places
from questline.services.plan_generation import generate_plan


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
        if settings.planner_provider != "fake":
            raise RuntimeError("Gemini provider has not been implemented")
        await generate_plan(UUID(generation_id), sessions, FakePlanner())

    @app.task(name="questline.extract_places", queue="plans")
    async def extract_task(import_id: str) -> None:
        await extract_places(UUID(import_id), sessions, settings=settings)

    return app, generate_task, extract_task


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
