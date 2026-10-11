from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from sqlalchemy import select
from test_integration import TRIP, drain, request_generation

from questline.models import Place, PlanGeneration, Trip
from questline.providers.errors import ProviderUnavailable
from questline.providers.maps import FakeMaps, ResolvedPlace
from questline.providers.routes import Leg
from questline.services.plan_generation import generate_plan

pytestmark = pytest.mark.integration


async def manual_trip(client):
    created = (await client.post("/api/v1/trips", json=TRIP)).json()
    trip_id = created["trip"]["id"]
    response = await client.post(
        f"/api/v1/trips/{trip_id}/places", json={"query": "Big Sur Bakery"}
    )
    assert response.status_code == 201, response.text
    return created, response.json()["place"]


async def test_manual_only_build_and_price_refresh_snapshot_isolation(api, monkeypatch):
    from questline.api import waypoints

    client, app = api
    created, place = await manual_trip(client)
    trip_id, pid = created["trip"]["id"], place["id"]
    generation = (await request_generation(client, trip_id)).json()["generation"]
    maps = FakeMaps()
    maps.price_level = AsyncMock(return_value=0)
    monkeypatch.setattr(waypoints, "maps_for_settings", lambda _: maps)
    refreshed = await client.post(f"/api/v1/places/{pid}/price-refresh")
    assert refreshed.status_code == 200, refreshed.text
    assert refreshed.json()["place"]["est_cost_low"] == 0
    await drain(app)
    before = (await client.get(f"/api/v1/trips/{trip_id}")).json()
    node = next(n for n in before["current_plan"]["content"]["graph"]["nodes"] if n["id"] == pid)
    # Refresh was after enqueue, so the queued snapshot still has the old unknown price.
    assert node["est_cost"] is None
    async with app.state.sessions() as session:
        saved = await session.get(PlanGeneration, UUID(generation["id"]))
        assert saved.snapshot["places"][0]["price_level"] is None
        assert saved.snapshot["planning_limits"]["planner_detour_limit"] == 5
    await request_generation(client, trip_id, "priced")
    await drain(app)
    state = (await client.get(f"/api/v1/trips/{trip_id}")).json()
    assert state["current_plan"]["content"]["per_person_estimate"] == [0, 0]
    saved_plan = state["current_plan"]
    maps.price_level.return_value = None
    cleared = await client.post(f"/api/v1/places/{pid}/price-refresh")
    assert cleared.json()["place"]["price_level"] is None
    assert cleared.json()["place"]["est_cost_low"] is None
    state = (await client.get(f"/api/v1/trips/{trip_id}")).json()
    assert state["current_plan"] == saved_plan  # Refresh never silently rewrites plans.
    assert state["revision"] > before["revision"]


async def test_price_refresh_auth_failure_and_explicit_prices(api, monkeypatch):
    from questline.api import waypoints

    client, app = api
    created, place = await manual_trip(client)
    other = (await client.post("/api/v1/trips", json=TRIP)).json()
    maps = FakeMaps()
    maps.price_level = AsyncMock(return_value=2)
    monkeypatch.setattr(waypoints, "maps_for_settings", lambda _: maps)
    url = f"/api/v1/places/{place['id']}/price-refresh"
    denied = await client.post(
        url, headers={"Authorization": "", "X-Member-Token": other["member_token"]}
    )
    assert denied.status_code == 422
    assert denied.json()["error"]["code"] == "cross_trip_reference"
    maps.price_level.assert_not_awaited()
    async with app.state.sessions() as session:
        stored = await session.get(Place, UUID(place["id"]))
        stored.est_cost_low, stored.est_cost_high, stored.cost_basis = 15, 25, "Supplied estimate"
        await session.commit()
    refreshed = await client.post(
        url, headers={"Authorization": "", "X-Member-Token": created["member_token"]}
    )
    assert refreshed.status_code == 200
    assert refreshed.json()["place"]["est_cost_low"] == 15
    maps.price_level.return_value = None
    unknown = await client.post(url)
    assert unknown.json()["place"]["price_level"] is None
    assert unknown.json()["place"]["est_cost_low"] == 15
    maps.price_level.side_effect = ProviderUnavailable("Price lookup unavailable")
    before = (await client.get(f"/api/v1/trips/{created['trip']['id']}")).json()
    assert (await client.post(url)).status_code == 503
    assert (await client.get(f"/api/v1/trips/{created['trip']['id']}")).json() == before


async def test_discovery_persists_local_ids_without_late_votes_or_paid_calls_under_locks(
    api, monkeypatch
):
    from questline.api import waypoints
    from questline.providers import selection

    client, app = api
    created, _ = await manual_trip(client)
    trip_id = created["trip"]["id"]
    generation = (await request_generation(client, trip_id)).json()["generation"]
    found = ResolvedPlace(
        google_place_id="mock-cafe",
        name="Coast Cafe",
        category="eat",
        address="CA",
        lat=36.8,
        lng=-121.8,
        price_level=1,
    )
    maps = FakeMaps()
    maps.resolve_place = AsyncMock(return_value=found)
    maps.search_along_route = AsyncMock(return_value=[found])
    monkeypatch.setattr(waypoints, "maps_for_settings", lambda _: maps)
    # A waypoint and vote added after enqueue collide with discovery; do not import that vote.
    added = (
        await client.post(f"/api/v1/trips/{trip_id}/places", json={"query": "Coast Cafe"})
    ).json()["place"]
    await client.post(
        f"/api/v1/places/{added['id']}/votes",
        json={"kind": "in", "member_id": created["member"]["id"]},
    )

    class Router:
        routed = True

        async def legs(self, points):
            async with app.state.sessions() as session:
                # Any provider call inside the generation's trip write lock would fail NOWAIT.
                await session.execute(
                    select(Trip).where(Trip.id == UUID(trip_id)).with_for_update(nowait=True)
                )
            return [Leg(10, 1000, "mock-polyline") for _ in points[1:]]

    monkeypatch.setattr(selection, "router_for_settings", lambda _: Router())
    monkeypatch.setattr(selection, "maps_for_settings", lambda _: maps)
    await generate_plan(UUID(generation["id"]), app.state.sessions, settings=app.state.settings)
    state = (await client.get(f"/api/v1/trips/{trip_id}")).json()
    node = next(
        n for n in state["current_plan"]["content"]["graph"]["nodes"] if n["id"] == added["id"]
    )
    assert node["quest"] == "side" and node["source"] == "suggested"
    assert "No votes yet" in node["why"] and node["source_message_ids"] == []
    assert len([p for p in state["places"] if p["google_place_id"] == "mock-cafe"]) == 1
    async with app.state.sessions() as session:
        stored = await session.get(PlanGeneration, UUID(generation["id"]))
        assert len(stored.snapshot["places"]) == 1 and stored.snapshot["votes"] == []
    # The next build includes the now-existing candidate and its actual snapshot vote normally.
    next_job = (await request_generation(client, trip_id, "next-build")).json()["generation"]
    await generate_plan(UUID(next_job["id"]), app.state.sessions, settings=app.state.settings)
    state = (await client.get(f"/api/v1/trips/{trip_id}")).json()
    node = next(
        n for n in state["current_plan"]["content"]["graph"]["nodes"] if n["id"] == added["id"]
    )
    assert node["quest"] == "main" and "Alice voted I'm in" in node["why"]


async def test_late_expired_build_cannot_replace_current_plan(api):
    from questline.models import PlanGeneration
    from questline.providers.fake import FakePlanner

    client, app = api
    created, _ = await manual_trip(client)
    trip_id = created["trip"]["id"]
    await request_generation(client, trip_id)
    await drain(app)
    before = (await client.get(f"/api/v1/trips/{trip_id}")).json()["current_plan"]
    generation = (await request_generation(client, trip_id, "expiring")).json()["generation"]

    class ExpiringPlanner(FakePlanner):
        async def generate(self, snapshot, request):
            result = await super().generate(snapshot, request)
            async with app.state.sessions() as session:
                saved = await session.get(PlanGeneration, UUID(generation["id"]))
                saved.status, saved.error = "failed", "Timed out"
                await session.commit()
            return result

    await generate_plan(UUID(generation["id"]), app.state.sessions, ExpiringPlanner())
    state = (await client.get(f"/api/v1/trips/{trip_id}")).json()
    assert state["current_plan"] == before
    assert next(job for job in state["jobs"] if job["id"] == generation["id"])["status"] == "failed"


async def test_structural_edit_explanations_use_current_votes(api):
    client, app = api
    created, place = await manual_trip(client)
    trip_id, member_id = created["trip"]["id"], created["member"]["id"]
    vote_url = f"/api/v1/places/{place['id']}/votes"
    await client.post(vote_url, json={"member_id": member_id, "kind": "in"})
    await request_generation(client, trip_id)
    await drain(app)
    state = (await client.get(f"/api/v1/trips/{trip_id}")).json()
    plan = state["current_plan"]
    await client.post(vote_url, json={"member_id": member_id, "kind": "out"})
    edited = await client.post(
        f"/api/v1/plans/{plan['id']}/operations",
        json={
            "revision": plan["revision"],
            "operations": [{"op": "set_quest", "node_id": place["id"], "quest": "side"}],
        },
    )
    assert edited.status_code == 200, edited.text
    node = next(
        n for n in edited.json()["plan"]["content"]["graph"]["nodes"] if n["id"] == place["id"]
    )
    assert "Alice voted Skip" in node["why"] and "voted I'm in" not in node["why"]
