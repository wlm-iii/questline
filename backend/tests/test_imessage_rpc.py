import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

from questline.integrations.imessage.imsg_rpc import ImsgClosed, ImsgError, ImsgRpc
from questline.integrations.imessage.models import ImsgMessage

FAKE_IMSG = [sys.executable, str(Path(__file__).with_name("fake_imsg.py"))]


def message(rowid: int, **fields) -> dict:
    return {
        "id": rowid,
        "guid": f"guid-{rowid}",
        "chat_id": 7,
        "chat_guid": "iMessage;+;chat7",
        "is_group": True,
        "sender": "+15550001111",
        "sender_name": "Sam",
        "is_from_me": False,
        "text": f"message {rowid}",
        "created_at": "2026-10-17T16:30:00.000Z",
        "attachments": [],
        **fields,
    }


@pytest.fixture
def fake_env(monkeypatch, tmp_path):
    log = tmp_path / "requests.jsonl"
    monkeypatch.setenv("FAKE_IMSG_LOG", str(log))
    monkeypatch.setenv("FAKE_IMSG_MESSAGES", json.dumps([message(1), message(2)]))
    return log


def logged(log: Path) -> list[dict]:
    return [json.loads(line) for line in log.read_text().splitlines()]


async def test_call_returns_result(fake_env):
    async with ImsgRpc(FAKE_IMSG) as rpc:
        assert await rpc.call("initialize", {"protocol_version": 1}) == {"protocol_version": 1}


async def test_error_response_raises_imsg_error(fake_env):
    async with ImsgRpc(FAKE_IMSG) as rpc:
        with pytest.raises(ImsgError) as raised:
            await rpc.call("bogus")
    assert raised.value.code == -32601


async def test_subscribe_streams_parsed_messages_after_the_cursor(fake_env):
    async with ImsgRpc(FAKE_IMSG) as rpc:
        await rpc.subscribe(since_rowid=1)
        event = await anext(rpc.events())
    assert event.method == "message"
    parsed = event.message
    assert parsed is not None
    assert (parsed.id, parsed.guid, parsed.text) == (2, "guid-2", "message 2")
    assert parsed.created_at == datetime(2026, 10, 17, 16, 30, tzinfo=UTC)
    [request] = [r for r in logged(fake_env) if r["method"] == "watch.subscribe"]
    assert request["params"] == {"since_rowid": 1, "include_reactions": True}


async def test_send_targets_the_chat_guid(fake_env):
    async with ImsgRpc(FAKE_IMSG) as rpc:
        await rpc.send("iMessage;+;chat7", "Got it, Sam.")
    [request] = [r for r in logged(fake_env) if r["method"] == "send"]
    assert request["params"] == {"chat_guid": "iMessage;+;chat7", "text": "Got it, Sam."}


async def test_history_returns_messages(fake_env):
    async with ImsgRpc(FAKE_IMSG) as rpc:
        history = await rpc.history(chat_id=7, limit=1)
    assert [m.id for m in history] == [2]


async def test_child_exit_fails_pending_calls_and_ends_events(fake_env):
    async with ImsgRpc(FAKE_IMSG) as rpc:
        with pytest.raises(ImsgClosed):
            await rpc.call("exit")
        assert [event async for event in rpc.events()] == []


def test_message_model_reads_reaction_fields():
    parsed = ImsgMessage.model_validate(
        message(
            3,
            text=None,
            is_reaction=True,
            reaction_type="love",
            is_reaction_add=True,
            reacted_to_guid="guid-1",
            unknown_future_field=1,
        )
    )
    assert (parsed.text, parsed.reaction_type, parsed.reacted_to_guid) == (None, "love", "guid-1")


def test_message_model_treats_naive_timestamps_as_local_time():
    parsed = ImsgMessage.model_validate(message(4, created_at="2026-10-17T09:30:00"))
    assert parsed.created_at.tzinfo is not None
    assert parsed.created_at == datetime(2026, 10, 17, 9, 30).astimezone()
