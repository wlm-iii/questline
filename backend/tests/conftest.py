import os
import subprocess

import httpx
import psycopg
import pytest
from pydantic import SecretStr
from sqlalchemy.engine import make_url

from questline.config import Settings
from questline.jobs import install_queue_schema
from questline.main import create_app


@pytest.fixture(scope="session")
def database_url():
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL to a disposable PostgreSQL database ending in _test")
    parsed = make_url(url)
    if not parsed.database or not parsed.database.endswith("_test"):
        pytest.fail("Refusing destructive tests: TEST_DATABASE_URL database must end in _test")
    settings = Settings(_env_file=None, database_url=SecretStr(url), app_env="test")
    with psycopg.connect(settings.psycopg_url) as connection:
        connection.execute("DROP SCHEMA IF EXISTS questline CASCADE")
    subprocess.run(
        ["alembic", "upgrade", "head"],
        check=True,
        env={**os.environ, "DATABASE_URL": url, "APP_ENV": "test"},
    )
    return url


@pytest.fixture
async def api(database_url):
    settings = Settings(
        _env_file=None,
        database_url=SecretStr(database_url),
        app_env="test",
        api_token=SecretStr("test-token"),
    )
    await install_queue_schema(settings)
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
            headers={"Authorization": "Bearer test-token"},
        ) as client:
            yield client, app
        async with await psycopg.AsyncConnection.connect(settings.psycopg_url) as connection:
            await connection.execute(
                "TRUNCATE questline.conversations, questline.procrastinate_jobs CASCADE"
            )
