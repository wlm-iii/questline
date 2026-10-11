"""Simulate a session pooler ignoring the private startup search_path."""

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.engine import URL
from test_integration import drain, request_generation, seed

from questline.config import Settings
from questline.jobs import install_queue_schema
from questline.main import create_app

pytestmark = pytest.mark.integration


class PublicStartupSettings(Settings):
    @property
    def sqlalchemy_url(self) -> URL:
        return super().sqlalchemy_url.update_query_dict({"options": "-csearch_path=public"})


async def test_api_and_worker_use_private_schema_despite_public_startup(api):
    _, original = api
    settings = PublicStartupSettings(_env_file=None, **original.state.settings.model_dump())
    await install_queue_schema(settings)
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        async with app.state.sessions() as session:
            assert await session.scalar(text("SELECT current_schema()")) == "questline"
            await session.rollback()
            assert await session.scalar(text("SELECT current_schema()")) == "questline"
        async with app.state.queue.open_async():
            async with app.state.queue.connector.pool.connection() as connection:
                cursor = await connection.execute("SELECT current_schema()")
                assert await cursor.fetchone() == ("questline",)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
            headers={"Authorization": "Bearer test-token"},
        ) as client:
            trip_id = await seed(client)
            generation = (await request_generation(client, trip_id)).json()["generation"]
            await drain(app)
            response = await client.get(f"/api/v1/plan-generations/{generation['id']}")
            assert response.json()["generation"]["status"] == "succeeded"
