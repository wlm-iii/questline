from uuid import uuid4

import httpx
import pytest
from pydantic import SecretStr, ValidationError
from sqlalchemy.exc import OperationalError

from questline.api.dependencies import session_for_request
from questline.config import Settings
from questline.main import create_app
from questline.providers.fake import FakePlanner
from questline.schemas import GenerationCreate, MessageRead, PlanEdge, PlanGraph, PlanNode


@pytest.fixture
def app():
    return create_app(Settings(_env_file=None, app_env="test"))


@pytest.fixture
async def client(app):
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            yield client


async def test_health_and_openapi_need_no_database(client):
    assert (await client.get("/health/live")).json() == {"status": "ok"}
    schema = (await client.get("/openapi.json")).json()
    assert "/api/v1/conversations/{conversation_id}/plan-generations" in schema["paths"]
    assert schema["components"]["securitySchemes"]["HTTPBearer"]


async def test_api_requires_token(client):
    assert (await client.post("/api/v1/conversations", json={"title": "Trip"})).status_code == 401
    response = await client.post(
        "/api/v1/conversations",
        json={"title": "Trip"},
        headers={"Authorization": "Bearer wrong"},
    )
    assert response.status_code == 401


async def test_readiness_hides_database_errors(app, client):
    class BrokenSession:
        async def execute(self, query):
            raise OperationalError("private connection details", {}, None)

    async def broken_session():
        yield BrokenSession()

    app.dependency_overrides[session_for_request] = broken_session
    response = await client.get("/health/ready")
    assert response.status_code == 503
    assert response.json() == {"detail": "Database unavailable"}


def test_production_rejects_default_token():
    with pytest.raises(ValidationError, match="unique API_TOKEN"):
        Settings(
            _env_file=None, app_env="production", api_token=SecretStr("local-development-only")
        )


def test_postgres_url_and_secret_handling():
    settings = Settings(
        _env_file=None,
        database_url=SecretStr("postgresql://postgres:secret@host/db?sslmode=require"),
    )
    assert settings.sqlalchemy_url.drivername == "postgresql+psycopg"
    assert settings.sqlalchemy_url.query["sslmode"] == "require"
    assert settings.sqlalchemy_url.query["options"] == "-csearch_path=questline"
    assert "secret" not in repr(settings)
    with pytest.raises(ValidationError, match="PostgreSQL"):
        Settings(_env_file=None, database_url=SecretStr("sqlite:///test.db"))


@pytest.mark.parametrize("timezone", ["not/a/timezone", "../UTC"])
def test_invalid_timezone(timezone):
    with pytest.raises(ValidationError):
        GenerationCreate(timezone=timezone)


def test_graph_integrity():
    node = PlanNode(id="one", kind="activity", title="Lunch")
    with pytest.raises(ValidationError, match="unique"):
        PlanGraph(nodes=[node, node])
    with pytest.raises(ValidationError, match="existing nodes"):
        PlanGraph(
            nodes=[node],
            edges=[PlanEdge(id="edge", source="one", target="missing", kind="travel")],
        )
    with pytest.raises(ValidationError, match="Self-edges"):
        PlanGraph(
            nodes=[node], edges=[PlanEdge(id="edge", source="one", target="one", kind="travel")]
        )


async def test_fake_planner_is_deterministic_and_explicit():
    transcript = [
        MessageRead(
            id=uuid4(),
            external_id="1",
            author_id="alice",
            sent_at="2026-07-10T14:30:00Z",
            text="Let's go hiking",
        )
    ]
    planner = FakePlanner()
    request = GenerationCreate()
    first = await planner.generate(transcript, request)
    assert first == await planner.generate(transcript, request)
    assert first.graph.nodes[0].source_message_ids == [transcript[0].id]
    assert "Mock output" in first.warnings[0]
