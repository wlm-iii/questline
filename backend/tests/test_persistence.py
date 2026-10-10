from uuid import UUID

import httpx
import pytest
from sqlalchemy.exc import IntegrityError
from test_integration import TRIP, drain, request_generation

from questline.integrations.imessage.api import QuestlineClient
from questline.models import Place, PlanGeneration
from questline.persistence_schemas import RelayBatch

pytestmark = pytest.mark.integration


async def create(client):
    result = await client.post("/api/v1/trips", json=TRIP)
    assert result.status_code == 201, result.text
    return result.json()


async def add(client, trip_id, query="McWay Falls"):
    result = await client.post(f"/api/v1/trips/{trip_id}/places", json={"query": query})
    assert result.status_code == 201, result.text
    return result.json()["place"]


async def state(client, trip_id):
    result = await client.get(f"/api/v1/trips/{trip_id}")
    assert result.status_code == 200, result.text
    return result.json()


async def test_places_votes_tasks_checkins_and_snapshot(api):
    client, app = api
    created = await create(client)
    tid = created["trip"]["id"]
    mid = created["member"]["id"]
    place = await add(client, tid)
    assert (await add(client, tid))["id"] == place["id"]
    second = (await client.post(f"/api/v1/trips/{tid}/members", json={"name": "Sam"})).json()[
        "member"
    ]["id"]
    vote_url = f"/api/v1/places/{place['id']}/votes"
    for member_id, kind in ((mid, "in"), (second, "out")):
        assert (
            await client.post(vote_url, json={"kind": kind, "member_id": member_id})
        ).status_code == 200
    saved = await state(client, tid)
    assert len(saved["places"]) == 1
    assert saved["places"][0]["vote_tallies"] == {"in": 1, "ok": 0, "out": 1}
    assert saved["places"][0]["contested"]
    assert (await client.post(vote_url, json={"kind": "out", "member_id": second})).json()[
        "vote"
    ] is None
    await client.post(vote_url, json={"kind": "ok", "member_id": second})
    task = (
        await client.post(
            f"/api/v1/trips/{tid}/tasks",
            json={
                "place_id": place["id"],
                "text": "Book entry",
                "owner_member_id": mid,
            },
        )
    ).json()["task"]
    changed = await client.patch(
        f"/api/v1/tasks/{task['id']}", json={"done": True, "owner_member_id": None}
    )
    assert changed.json()["task"]["done_at"]
    assert changed.json()["task"]["owner_member_id"] is None
    checkin_url = f"/api/v1/places/{place['id']}/checkins"
    first = (await client.post(checkin_url)).json()["checkin"]
    assert (await client.post(checkin_url)).json()["checkin"]["id"] == first["id"]
    await client.post(f"/api/v1/trips/{tid}/import", json={"text": "Alice: McWay Falls please"})
    await drain(app)
    generation = (await request_generation(client, tid)).json()["generation"]
    async with app.state.sessions() as session:
        saved = await session.get(PlanGeneration, UUID(generation["id"]))
        assert len(saved.snapshot["places"]) == 1
        assert len(saved.snapshot["votes"]) == 2
    await client.post(vote_url, json={"kind": "out", "member_id": mid})
    async with app.state.sessions() as session:
        saved = await session.get(PlanGeneration, UUID(generation["id"]))
        assert saved.snapshot["votes"][0]["kind"] in {"in", "ok"}
        assert not any(v["kind"] == "out" for v in saved.snapshot["votes"])
    await drain(app)
    refreshed = await state(client, tid)
    assert len(refreshed["checkins"]) == 1
    assert len(refreshed["tasks"]) == 1
    assert refreshed["tasks"][0]["done_at"]
    assert (await client.delete(checkin_url)).status_code == 204
    assert not (await state(client, tid))["checkins"]


async def test_paste_deduplication_evidence_and_unresolved(api):
    client, app = api
    tid = (await create(client))["trip"]["id"]
    text = "Alice: McWay Falls please\n  Saturday morning\nSam: Big Sur Bakery\nSam: Mystery Cafe"
    for _ in range(2):
        result = await client.post(f"/api/v1/trips/{tid}/import", json={"text": text})
        assert result.status_code == 202, result.text
        await drain(app)
    saved = await state(client, tid)
    assert len(saved["messages"]) == 3
    assert len(saved["places"]) == 2
    assert len(saved["imports"]) == 2
    assert all(job["status"] == "succeeded" for job in saved["imports"])
    assert len(saved["trip"]["unresolved_mentions"]) == 1
    assert saved["messages"][0]["text"].endswith("\nSaturday morning")
    ids = {message["id"] for message in saved["messages"]}
    assert all(set(place["source_message_ids"]) <= ids for place in saved["places"])
    assert all(place["source"] == "group" for place in saved["places"])
    app.state.settings.max_transcript_chars = 5
    assert (
        await client.post(f"/api/v1/trips/{tid}/import", json={"text": text})
    ).status_code == 413


async def test_imessage_handles_reply_evidence_and_explicit_reactions(api):
    client, app = api
    tid = (await create(client))["trip"]["id"]
    relay = QuestlineClient("http://test", "test-token", transport=httpx.ASGITransport(app=app))
    try:
        assert await relay.lookup_chat("iMessage;+;test") is None
        await relay.link_chat(tid, "iMessage;+;test")
        payload = {
            "messages": [
                {
                    "guid": "reply",
                    "handle": "+15550000002",
                    "sent_at": "2026-10-10T12:01:00Z",
                    "text": "Sounds good",
                    "reply_to_guid": "parent",
                },
                {
                    "guid": "parent",
                    "handle": "+15550000001",
                    "display_name": "Alice",
                    "sent_at": "2026-10-10T12:00:00Z",
                    "text": "McWay Falls",
                },
            ]
        }
        from questline.integrations.imessage.api import BatchMessage, Reaction

        messages = [BatchMessage.model_validate(m) for m in payload["messages"]]
        assert await relay.post_batch(tid, messages) == 2
        assert await relay.post_batch(tid, messages) == 0
        await drain(app)
        saved = await state(client, tid)
        assert len(saved["members"]) == 3  # Organizer + separate handle identities.
        assert not saved["votes"]  # A reply is evidence, not an inferred vote.
        assert len(saved["places"][0]["source_message_ids"]) == 2
        reply = next(m for m in saved["messages"] if m["external_id"] == "reply")
        assert reply["reply_to_id"] is not None
        await relay.rename_member(tid, "+15550000002", "Sam")
        reaction = Reaction(handle="+15550000002", target_guid="parent", kind="love", added=True)
        await relay.post_reactions(tid, [reaction, reaction])
        assert len((await state(client, tid))["votes"]) == 1
        await relay.post_reactions(tid, [reaction.model_copy(update={"added": False})])
        assert not (await state(client, tid))["votes"]
        other = (await create(client))["trip"]["id"]
        conflict = await client.post(
            f"/api/v1/trips/{other}/channels/imessage", json={"chat_guid": "iMessage;+;test"}
        )
        assert conflict.status_code == 409
        await relay.unlink_chat(tid)
        assert await relay.lookup_chat("iMessage;+;test") is None
        assert (
            await client.post(f"/api/v1/trips/{tid}/imessage/batch", json=payload)
        ).status_code == 409
        assert len((await state(client, tid))["messages"]) == 2
    finally:
        await relay.aclose()


async def test_cross_trip_writes_and_member_impersonation_are_rejected(api):
    client, app = api
    one, two = await create(client), await create(client)
    tid, other = one["trip"]["id"], two["trip"]["id"]
    place = await add(client, tid)
    assert (
        await client.post(
            f"/api/v1/trips/{other}/tasks", json={"place_id": place["id"], "text": "Wrong trip"}
        )
    ).status_code == 422
    assert (
        await client.post(
            f"/api/v1/places/{place['id']}/votes",
            json={"kind": "in", "member_id": two["member"]["id"]},
        )
    ).status_code == 422
    client.headers.pop("Authorization")
    client.headers["X-Member-Token"] = one["member_token"]
    assert (
        await client.post(
            f"/api/v1/places/{place['id']}/votes",
            json={"kind": "in", "member_id": two["member"]["id"]},
        )
    ).status_code == 422
    assert (
        await client.post(f"/api/v1/trips/{tid}/channels/imessage", json={"chat_guid": "test"})
    ).status_code == 403
    assert (
        await client.post(f"/api/v1/places/{place['id']}/votes", json={"kind": "in"})
    ).status_code == 200


async def test_import_queue_failure_rolls_back_messages(api):
    client, app = api
    tid = (await create(client))["trip"]["id"]

    class BrokenQueue:
        def configure(self, **kwargs):
            return self

        async def defer_async(self, **kwargs):
            raise RuntimeError("Simulated failure")

    original = app.state.extract_task
    app.state.extract_task = BrokenQueue()
    with pytest.raises(RuntimeError):
        await client.post(f"/api/v1/trips/{tid}/import", json={"text": "Alice: McWay Falls"})
    app.state.extract_task = original
    saved = await state(client, tid)
    assert not saved["messages"] and not saved["imports"]


async def test_place_constraints_reject_invalid_costs(api):
    client, app = api
    tid = (await create(client))["trip"]["id"]
    async with app.state.sessions() as session:
        session.add(
            Place(
                trip_id=UUID(tid),
                google_place_id="bad",
                name="Bad",
                category="do",
                address="fixture",
                lat=0,
                lng=0,
                source="added",
                est_cost_low=20,
                est_cost_high=10,
            )
        )
        with pytest.raises(IntegrityError):
            await session.commit()


def test_relay_contract_accepts_reply_linkage():
    parsed = RelayBatch.model_validate(
        {
            "messages": [
                {
                    "guid": "reply",
                    "handle": "+1555",
                    "sent_at": "2026-10-10T12:00:00Z",
                    "text": "sounds good",
                    "reply_to_guid": "parent",
                }
            ]
        }
    )
    assert parsed.messages[0].reply_to_guid == "parent"
