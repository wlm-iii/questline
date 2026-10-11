import json
from datetime import UTC, datetime
from uuid import uuid4

import httpx
import pytest

from questline.integrations.imessage.api import (
    BatchMessage,
    Conflict,
    NotFound,
    PlanSummary,
    QuestlineClient,
    Reaction,
    Rejected,
    Unavailable,
)

TRIP_ID = "abc123"


def client_for(handler) -> tuple[QuestlineClient, list[httpx.Request]]:
    requests: list[httpx.Request] = []

    def record(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return handler(request)

    client = QuestlineClient(
        "http://api.test", "secret-token", transport=httpx.MockTransport(record)
    )
    return client, requests


def body(request: httpx.Request):
    return json.loads(request.content)


async def test_requests_use_bearer_token_and_v1_prefix():
    client, requests = client_for(lambda r: httpx.Response(200, json={"trip_id": TRIP_ID}))
    assert await client.lookup_chat("iMessage;+;chat1") == TRIP_ID
    [request] = requests
    assert request.headers["authorization"] == "Bearer secret-token"
    assert request.url.raw_path == b"/api/v1/channels/imessage/iMessage%3B%2B%3Bchat1"


async def test_lookup_of_unlinked_chat_returns_none():
    client, _ = client_for(lambda r: httpx.Response(404, json={"error": {"code": "not_found"}}))
    assert await client.lookup_chat("iMessage;+;chat1") is None


async def test_link_chat_returns_trip_name():
    trip = {"id": TRIP_ID, "name": "Big Sur weekend", "revision": 3}
    client, requests = client_for(lambda r: httpx.Response(200, json={"trip": trip}))
    linked = await client.link_chat(TRIP_ID, "iMessage;+;chat1")
    assert (linked.id, linked.name) == (TRIP_ID, "Big Sur weekend")
    assert requests[0].method == "POST"
    assert requests[0].url.path == f"/api/v1/trips/{TRIP_ID}/channels/imessage"
    assert body(requests[0]) == {"chat_guid": "iMessage;+;chat1"}


async def test_conflict_carries_the_error_envelope():
    error = {"error": {"code": "chat_linked", "message": "Linked to another trip"}}
    client, _ = client_for(lambda r: httpx.Response(409, json=error))
    with pytest.raises(Conflict) as raised:
        await client.link_chat(TRIP_ID, "iMessage;+;chat1")
    assert (raised.value.code, raised.value.message) == ("chat_linked", "Linked to another trip")


async def test_unlink_chat_sends_delete():
    client, requests = client_for(lambda r: httpx.Response(204))
    await client.unlink_chat(TRIP_ID)
    assert (requests[0].method, requests[0].url.path) == (
        "DELETE",
        f"/api/v1/trips/{TRIP_ID}/channels/imessage",
    )


async def test_post_batch_serializes_messages():
    client, requests = client_for(
        lambda r: httpx.Response(202, json={"import_id": str(uuid4()), "inserted": 1})
    )
    message = BatchMessage(
        guid="g1",
        handle="+15550001111",
        display_name=None,
        sent_at=datetime(2026, 10, 17, 9, 30, tzinfo=UTC),
        text="McWay Falls?",
    )
    assert await client.post_batch(TRIP_ID, [message]) == 1
    assert body(requests[0]) == {
        "messages": [
            {
                "guid": "g1",
                "handle": "+15550001111",
                "sent_at": "2026-10-17T09:30:00Z",
                "text": "McWay Falls?",
            }
        ]
    }


@pytest.mark.parametrize(
    ("raw", "sent"),
    [("  Sam  ", "Sam"), ("   ", None), ("", None), ("x" * 80, "x" * 60)],
)
def test_batch_display_name_fits_the_backend_limits(raw, sent):
    message = BatchMessage(
        guid="g1",
        handle="+15550001111",
        display_name=raw,
        sent_at=datetime(2026, 10, 17, 9, 30, tzinfo=UTC),
        text="hi",
    )
    assert message.display_name == sent


async def test_post_reactions():
    client, requests = client_for(lambda r: httpx.Response(200, json={"applied": 1, "skipped": 0}))
    reaction = Reaction(handle="+15550001111", target_guid="g1", kind="love", added=True)
    await client.post_reactions(TRIP_ID, [reaction])
    assert requests[0].url.path == f"/api/v1/trips/{TRIP_ID}/imessage/reactions"
    assert body(requests[0]) == {"reactions": [reaction.model_dump()]}


@pytest.mark.parametrize("status", [413, 422])
async def test_permanent_rejections_raise_rejected(status):
    client, _ = client_for(lambda r: httpx.Response(status, json={"detail": "too big"}))
    with pytest.raises(Rejected):
        await client.post_batch(TRIP_ID, [])


async def test_server_errors_raise_unavailable():
    client, _ = client_for(lambda r: httpx.Response(503, text="upstream down"))
    with pytest.raises(Unavailable):
        await client.post_reactions(TRIP_ID, [])


async def test_transport_errors_raise_unavailable():
    def fail(request):
        raise httpx.ConnectError("refused", request=request)

    client, _ = client_for(fail)
    with pytest.raises(Unavailable):
        await client.lookup_chat("iMessage;+;chat1")


async def test_add_place_returns_resolved_name():
    client, requests = client_for(
        lambda r: httpx.Response(201, json={"place": {"id": str(uuid4()), "name": "Nepenthe"}})
    )
    assert await client.add_place(TRIP_ID, "nepenthe big sur") == "Nepenthe"
    assert body(requests[0]) == {"query": "nepenthe big sur"}


async def test_add_unknown_place_raises_not_found():
    error = {"error": {"code": "place_not_found", "message": "No match"}}
    client, _ = client_for(lambda r: httpx.Response(404, json=error))
    with pytest.raises(NotFound):
        await client.add_place(TRIP_ID, "zzzz")


async def test_create_generation_sends_idempotency_key_and_preset():
    generation_id = uuid4()
    generation = {"id": str(generation_id), "status": "queued", "plan_id": None, "error": None}
    client, requests = client_for(lambda r: httpx.Response(202, json={"generation": generation}))
    created = await client.create_generation(TRIP_ID, "treat", idempotency_key="msg-guid")
    assert (created.id, created.status) == (generation_id, "queued")
    assert requests[0].headers["idempotency-key"] == "msg-guid"
    assert body(requests[0]) == {"budget_preset": "treat"}


async def test_create_generation_without_preset_sends_empty_body():
    generation = {"id": str(uuid4()), "status": "queued"}
    client, requests = client_for(lambda r: httpx.Response(202, json={"generation": generation}))
    await client.create_generation(TRIP_ID, None, idempotency_key="k")
    assert body(requests[0]) == {}


async def test_get_plan_summarizes_main_quests_and_estimate():
    content = {
        "graph": {
            "nodes": [
                {"id": "start", "role": "start", "quest": "main"},
                {"id": "a", "role": "stop", "quest": "main"},
                {"id": "b", "role": "stop", "quest": "main"},
                {"id": "c", "role": "stop", "quest": "side"},
                {"id": "end", "role": "end", "quest": "main"},
            ]
        },
        "per_person_estimate": [40, 85],
        "estimate_is_partial": True,
    }
    plan_id = uuid4()
    client, requests = client_for(
        lambda r: httpx.Response(200, json={"plan": {"id": str(plan_id), "content": content}})
    )
    assert await client.get_plan(plan_id) == PlanSummary(
        main_quests=2, side_quests=1, estimate=(40, 85), estimate_is_partial=True
    )
    assert requests[0].url.path == f"/api/v1/plans/{plan_id}"


async def test_rename_member_escapes_the_handle():
    client, requests = client_for(lambda r: httpx.Response(200, json={"member": {}}))
    await client.rename_member(TRIP_ID, "sam+trips@example.com", "Sam")
    assert requests[0].method == "PATCH"
    assert requests[0].url.raw_path == (
        f"/api/v1/trips/{TRIP_ID}/imessage/members/sam%2Btrips%40example.com".encode()
    )
    assert body(requests[0]) == {"name": "Sam"}
