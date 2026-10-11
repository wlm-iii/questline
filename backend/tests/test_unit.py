import httpx
import pytest
from pydantic import SecretStr, ValidationError
from sqlalchemy.exc import OperationalError

from questline.api.dependencies import session_for_request
from questline.config import Settings
from questline.main import create_app
from questline.operations import OperationsRequest
from questline.schemas import PlanEdge, PlanGraph, PlanNode, TripCreate


@pytest.fixture
async def client():
    app = create_app(Settings(_env_file=None, app_env="test"))
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            yield client, app


async def test_health_openapi_and_cors(client):
    client, app = client
    assert (await client.get("/health/live")).json() == {"ok": True}
    assert (await client.get("/api/v1/health/live")).json() == {"ok": True}
    schema = (await client.get("/openapi.json")).json()
    assert "/api/v1/trips/{trip_id}/plan-generations" in schema["paths"]
    assert not any("conversations" in path for path in schema["paths"])
    response = await client.options(
        "/api/v1/trips/test",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "DELETE",
            "Access-Control-Request-Headers": "X-Member-Token",
        },
    )
    assert response.status_code == 200


async def test_api_requires_token(client):
    client, app = client
    response = await client.get("/api/v1/trips/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


async def test_errors_hide_input(client):
    client, app = client
    response = await client.post("/api/v1/trips", json={"secret": "private-input"})
    assert response.status_code == 422
    assert "private-input" not in response.text

    class BrokenSession:
        async def execute(self, query):
            raise OperationalError("private connection details", {}, None)

    async def broken_session():
        yield BrokenSession()

    app.dependency_overrides[session_for_request] = broken_session
    response = await client.get("/health/ready")
    assert response.status_code == 503
    assert response.json()["error"]["message"] == "Database unavailable"


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


@pytest.mark.parametrize(
    "changes",
    [
        {"timezone": "not/a/timezone"},
        {"end_date": "2026-10-16"},
        {"end_date": "2026-10-20"},
        {"organizer_name": "   "},
    ],
)
def test_trip_validation(changes):
    with pytest.raises(ValidationError):
        TripCreate.model_validate(
            {
                "name": "Trip",
                "origin": "San Jose, CA",
                "destination": "Big Sur, CA",
                "start_date": "2026-10-17",
                "end_date": "2026-10-18",
                "timezone": "UTC",
                "organizer_name": "Alice",
                **changes,
            }
        )


def test_graph_integrity():
    node = PlanNode(id="one", title="Lunch")
    with pytest.raises(ValidationError, match="unique"):
        PlanGraph(nodes=[node, node])
    with pytest.raises(ValidationError, match="existing nodes"):
        PlanGraph(
            nodes=[node], edges=[PlanEdge(id="edge", source="one", target="missing", kind="travel")]
        )
    with pytest.raises(ValidationError, match="Self-edges"):
        PlanGraph(
            nodes=[node], edges=[PlanEdge(id="edge", source="one", target="one", kind="travel")]
        )
    with pytest.raises(ValidationError, match="anchor"):
        PlanGraph(nodes=[PlanNode(id="side", title="Side", quest="side", anchor="missing")])


def test_operation_contract_excludes_derived_fields():
    request = OperationsRequest.model_validate(
        {
            "revision": 1,
            "operations": [{"op": "set_quest", "node_id": "stop-1", "quest": "side"}],
        }
    )
    assert request.operations[0].op == "set_quest"
    with pytest.raises(ValidationError):
        OperationsRequest.model_validate(
            {
                "revision": 1,
                "operations": [
                    {"op": "move", "node_id": "stop-1", "after": "start", "drive_min": 5}
                ],
            }
        )


def test_spec_graph_fields_are_accepted():
    graph = PlanGraph.model_validate(
        {
            "nodes": [
                {"id": "start", "title": "Origin", "role": "start", "lat": 37, "lng": -121},
                {"id": "end", "title": "Destination", "role": "end"},
                {
                    "id": "side",
                    "title": "Optional",
                    "quest": "side",
                    "anchor": "start",
                    "category": "eat",
                    "detour_min": None,
                    "est_cost": [10, 20],
                    "why": "Group pick",
                },
            ],
            "edges": [
                {
                    "id": "main-leg",
                    "source": "start",
                    "target": "end",
                    "kind": "travel",
                    "drive_min": 60,
                    "distance_m": 50000,
                    "polyline": "fixture-polyline",
                },
                {"id": "detour-leg", "source": "start", "target": "side", "kind": "detour"},
            ],
        }
    )
    assert graph.nodes[2].detour_min is None
    assert graph.edges[0].polyline == "fixture-polyline"


async def test_in_process_worker_restarts_after_a_crash():
    from questline.main import supervise_worker

    class Queue:
        runs = 0

        async def run_worker_async(self, **kwargs):
            self.runs += 1
            if self.runs == 1:
                raise RuntimeError("connection lost")

    queue = Queue()
    await supervise_worker(queue, restart_delay=0)  # type: ignore[arg-type]
    assert queue.runs == 2
