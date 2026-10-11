import pytest
from test_integration import TRIP, drain, request_generation

pytestmark = pytest.mark.integration


async def build_trip(client, app):
    created = (await client.post("/api/v1/trips", json=TRIP)).json()
    trip_id, alice = created["trip"]["id"], created["member"]["id"]
    sam = (await client.post(f"/api/v1/trips/{trip_id}/members", json={"name": "Sam"})).json()[
        "member"
    ]["id"]
    await client.post(
        f"/api/v1/trips/{trip_id}/import",
        json={"text": "Alice: we HAVE to hit McWay Falls\nSam: Big Sur Bakery for breakfast?"},
    )
    await drain(app)
    places = {
        p["name"]: p["id"] for p in (await client.get(f"/api/v1/trips/{trip_id}")).json()["places"]
    }
    mcway, bakery = places["McWay Falls (fixture)"], places["Big Sur Bakery (fixture)"]
    for member, place, kind in ((alice, mcway, "in"), (sam, mcway, "out"), (alice, bakery, "in")):
        vote = await client.post(
            f"/api/v1/places/{place}/votes", json={"kind": kind, "member_id": member}
        )
        assert vote.status_code == 200, vote.text
    assert (await request_generation(client, trip_id)).status_code == 202
    await drain(app)
    state = (await client.get(f"/api/v1/trips/{trip_id}")).json()
    return state, mcway, bakery, sam


async def test_build_edit_resolve_accept_and_assign(api):
    client, app = api
    state, mcway, bakery, sam = await build_trip(client, app)
    plan = state["current_plan"]
    assert plan is not None, state["jobs"]
    nodes = {node["id"]: node for node in plan["content"]["graph"]["nodes"]}
    # Alice in (+2), Sam out (-1) leaves McWay below the main-quest bar: a contested side quest.
    assert nodes[bakery]["quest"] == "main" and nodes[mcway]["quest"] == "side"
    assert nodes[mcway]["detour_min"] is not None
    assert any(c["kind"] == "split_vote" for c in plan["content"]["conflicts"])
    url = f"/api/v1/plans/{plan['id']}"

    options = (await client.post(f"{url}/resolutions", json={"node_id": mcway})).json()["options"]
    assert [option["label"] for option in options][0] == "Put it on the main quest"
    assert all("Sam voted Skip" in option["rationale"] for option in options)
    bad = await client.post(f"{url}/resolutions", json={"node_id": "start"})
    assert bad.status_code == 422

    edited = await client.post(
        f"{url}/operations",
        json={"revision": plan["revision"], "operations": options[0]["operations"]},
    )
    assert edited.status_code == 200, edited.text
    edited_plan = edited.json()["plan"]
    main = [n["id"] for n in edited_plan["content"]["graph"]["nodes"] if n["quest"] == "main"]
    assert main == ["start", bakery, mcway, "end"] or main == ["start", mcway, bakery, "end"]
    assert (
        "Promoted McWay Falls (fixture) to the main quest"
        in (edited_plan["content"]["changed_from_previous"])
    )
    stale = await client.post(
        f"{url}/operations",
        json={"revision": plan["revision"], "operations": [{"op": "drop", "node_id": mcway}]},
    )
    assert stale.status_code == 409
    invalid = await client.post(
        f"{url}/operations",
        json={
            "revision": edited_plan["revision"],
            "operations": [{"op": "drop", "node_id": "end"}],
        },
    )
    assert invalid.status_code == 422

    accepted = (
        await client.post(f"{url}/accept", json={"revision": edited_plan["revision"]})
    ).json()["plan"]
    assert accepted["status"] == "accepted"
    # Owners are follow-through: assigning one keeps the questline accepted.
    owned = await client.post(
        f"{url}/operations",
        json={
            "revision": accepted["revision"],
            "operations": [{"op": "assign_owner", "node_id": bakery, "member_id": sam}],
        },
    )
    owned_plan = owned.json()["plan"]
    assert owned_plan["status"] == "accepted"
    owner = next(n for n in owned_plan["content"]["graph"]["nodes"] if n["id"] == bakery)
    assert owner["owner_member_id"] == sam
    # A structural edit after acceptance returns the plan to draft.
    dropped = await client.post(
        f"{url}/operations",
        json={"revision": owned_plan["revision"], "operations": [{"op": "drop", "node_id": mcway}]},
    )
    assert dropped.json()["plan"]["status"] == "draft"


async def test_rebuild_keeps_owners_and_reports_changes(api):
    client, app = api
    state, _, bakery, sam = await build_trip(client, app)
    plan = state["current_plan"]
    await client.post(
        f"/api/v1/plans/{plan['id']}/operations",
        json={
            "revision": plan["revision"],
            "operations": [{"op": "assign_owner", "node_id": bakery, "member_id": sam}],
        },
    )
    assert (
        await request_generation(client, state["trip"]["id"], "rebuild", "treat")
    ).status_code == 202
    await drain(app)
    rebuilt = (await client.get(f"/api/v1/trips/{state['trip']['id']}")).json()["current_plan"]
    assert rebuilt["id"] != plan["id"]
    owner = next(n for n in rebuilt["content"]["graph"]["nodes"] if n["id"] == bakery)
    assert owner["owner_member_id"] == sam
    assert rebuilt["content"]["changed_from_previous"] == ["No changes from the previous questline"]
