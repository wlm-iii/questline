import asyncio
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException

from questline.api import (
    errors,
    follow_through,
    generations,
    health,
    imessage,
    imports,
    plans,
    trips,
    waypoints,
)
from questline.config import Settings, get_settings
from questline.db import create_database
from questline.jobs import create_queue
from questline.providers.google_maps import MapsUnavailable


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    engine, sessions = create_database(settings)
    queue, generate_task, extract_task = create_queue(settings, sessions)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        try:
            if settings.run_worker_in_process:
                async with queue.open_async():
                    worker = asyncio.create_task(
                        queue.run_worker_async(queues=["plans"], concurrency=2)
                    )
                    try:
                        yield
                    finally:
                        worker.cancel()
                        with suppress(asyncio.CancelledError):
                            await worker
            else:
                yield
        finally:
            await engine.dispose()

    app = FastAPI(title="Questline API", version="0.2.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.sessions = sessions
    app.state.queue = queue
    app.state.generate_task = generate_task
    app.state.extract_task = extract_task
    app.add_exception_handler(HTTPException, errors.http_error)
    app.add_exception_handler(MapsUnavailable, errors.maps_error)
    app.add_exception_handler(RequestValidationError, errors.validation_error)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Authorization", "X-Member-Token", "Content-Type", "Idempotency-Key"],
    )
    app.include_router(health.router)
    app.include_router(health.router, prefix="/api/v1")
    for router in (
        trips.router,
        generations.router,
        plans.router,
        waypoints.router,
        imports.router,
        imessage.router,
        follow_through.router,
    ):
        app.include_router(router, prefix="/api/v1")
    return app


app = create_app()
