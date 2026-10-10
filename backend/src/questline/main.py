from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from questline.api import conversations, generations, health, plans
from questline.api.dependencies import require_api_token
from questline.config import Settings, get_settings
from questline.db import create_database
from questline.jobs import create_queue


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    engine, sessions = create_database(settings)
    queue, generate_task = create_queue(settings, sessions)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        try:
            yield
        finally:
            await engine.dispose()

    app = FastAPI(title="Questline API", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.sessions = sessions
    app.state.queue = queue
    app.state.generate_task = generate_task
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "PATCH"],
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
    )
    app.include_router(health.router)
    for router in (conversations.router, generations.router, plans.router):
        app.include_router(router, prefix="/api/v1", dependencies=[Depends(require_api_token)])
    return app


app = create_app()
