import httpx
import pytest
from test_integration import TRIP, drain
from test_persistence import state

from questline.integrations.imessage.api import BatchMessage, QuestlineClient, Reaction

pytestmark = pytest.mark.integration

HANDLE = "max@example.com"


def message(guid, text, minute=0):
    return BatchMessage.model_validate(
        {"guid": guid, "handle": HANDLE, "sent_at": f"2026-10-10T12:0{minute}:00Z", "text": text}
    )


async def linked(client, app):
    created = (await client.post("/api/v1/trips", json={**TRIP, "organizer_name": "Max"})).json()
    relay = QuestlineClient("http://test", "test-token", transport=httpx.ASGITransport(app=app))
    await relay.link_chat(created["trip"]["id"], "iMessage;+;identity")
    return created, relay


async def test_claiming_a_name_first_reuses_the_web_member(api):
    client, app = api
    created, relay = await linked(client, app)
    tid, organizer = created["trip"]["id"], created["member"]["id"]
    try:
        await relay.rename_member(tid, HANDLE, "max")  # Case-insensitive match.
        await relay.post_batch(tid, [message("m1", "McWay Falls")])
        await drain(app)
        saved = await state(client, tid)
        assert [(m["id"], m["name"], m["imessage_handle"]) for m in saved["members"]] == [
            (organizer, "Max", HANDLE)
        ]
        assert saved["messages"][0]["member_id"] == organizer
    finally:
        await relay.aclose()


async def test_claiming_later_merges_chat_activity_into_the_web_member(api):
    client, app = api
    created, relay = await linked(client, app)
    tid, organizer = created["trip"]["id"], created["member"]["id"]
    try:
        await relay.post_batch(
            tid, [message("m1", "McWay Falls"), message("m2", "Big Sur Bakery", 1)]
        )
        await drain(app)
        places = {p["name"]: p["id"] for p in (await state(client, tid))["places"]}
        mcway, bakery = places["McWay Falls (fixture)"], places["Big Sur Bakery (fixture)"]
        # Web vote first, then a newer chat vote on the same place, plus a chat-only vote.
        vote = await client.post(
            f"/api/v1/places/{mcway}/votes", json={"kind": "out", "member_id": organizer}
        )
        assert vote.status_code == 200
        await relay.post_reactions(
            tid,
            [
                Reaction(handle=HANDLE, target_guid="m1", kind="love", added=True),
                Reaction(handle=HANDLE, target_guid="m2", kind="like", added=True),
            ],
        )
        before = await state(client, tid)
        assert len(before["members"]) == 2  # The known duplicate, before claiming.
        await relay.rename_member(tid, HANDLE, "Max")
        after = await state(client, tid)
        assert [(m["id"], m["imessage_handle"]) for m in after["members"]] == [(organizer, HANDLE)]
        assert {m["member_id"] for m in after["messages"]} == {organizer}
        votes = {(v["place_id"], v["kind"]) for v in after["votes"]}
        assert votes == {(mcway, "in"), (bakery, "ok")}  # Newest vote wins on McWay.
        assert all(v["member_id"] == organizer for v in after["votes"])
        assert {p["mentioned_by"] for p in after["places"]} == {organizer}
        # Later chat activity keeps landing on the same member.
        await relay.post_batch(tid, [message("m3", "McWay Falls again", 2)])
        assert len((await state(client, tid))["members"]) == 1
    finally:
        await relay.aclose()


async def test_names_never_merge_two_handles_or_ambiguous_members(api):
    client, app = api
    created, relay = await linked(client, app)
    tid = created["trip"]["id"]
    try:
        await client.post(f"/api/v1/trips/{tid}/members", json={"name": "Max"})  # Two web "Max"es.
        await relay.rename_member(tid, HANDLE, "Max")
        saved = await state(client, tid)
        assert len(saved["members"]) == 3
        assert sum(1 for m in saved["members"] if m["imessage_handle"] == HANDLE) == 1
    finally:
        await relay.aclose()
