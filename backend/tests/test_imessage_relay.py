import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from questline.integrations.imessage.api import (
    BatchMessage,
    Conflict,
    Generation,
    NotFound,
    PlanSummary,
    Reaction,
    Rejected,
    Trip,
    Unavailable,
)
from questline.integrations.imessage.models import ImsgMessage
from questline.integrations.imessage.relay import UNREACHABLE, Relay
from questline.integrations.imessage.state import RelayState

CHAT = "iMessage;+;chat7"
TRIP_ID = "abc123"
SAM = "+15550001111"
FAKE_IMSG = [sys.executable, str(Path(__file__).with_name("fake_imsg.py"))]


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


class FakeApi:
    def __init__(self) -> None:
        self.links: dict[str, str] = {}
        self.calls: list[tuple] = []
        self.batches: list[tuple[str, list[BatchMessage]]] = []
        self.reactions: list[tuple[str, list[Reaction]]] = []
        self.fail_batches: list[Exception] = []
        self.fail_lookups: list[Exception] = []
        self.link_error: Exception | None = None
        self.place_error: Exception | None = None
        self.generation_statuses = ["running", "succeeded"]
        self.generation_error: str | None = None
        self.create_generation_error: Exception | None = None
        self.plan = PlanSummary(main_quests=3, estimate=(40, 85), estimate_is_partial=False)
        self.batch_posted = asyncio.Event()

    async def lookup_chat(self, chat_guid: str) -> str | None:
        self.calls.append(("lookup_chat", chat_guid))
        if self.fail_lookups:
            raise self.fail_lookups.pop(0)
        return self.links.get(chat_guid)

    async def link_chat(self, trip_id: str, chat_guid: str) -> Trip:
        self.calls.append(("link_chat", trip_id, chat_guid))
        if self.link_error:
            raise self.link_error
        self.links[chat_guid] = trip_id
        return Trip(id=trip_id, name="Big Sur weekend")

    async def unlink_chat(self, trip_id: str) -> None:
        self.calls.append(("unlink_chat", trip_id))
        self.links = {k: v for k, v in self.links.items() if v != trip_id}

    async def post_batch(self, trip_id: str, messages: list[BatchMessage]) -> int:
        if self.fail_batches:
            raise self.fail_batches.pop(0)
        self.batches.append((trip_id, messages))
        self.batch_posted.set()
        return len(messages)

    async def post_reactions(self, trip_id: str, reactions: list[Reaction]) -> None:
        self.reactions.append((trip_id, reactions))

    async def add_place(self, trip_id: str, query: str) -> str:
        self.calls.append(("add_place", trip_id, query))
        if self.place_error:
            raise self.place_error
        return "Nepenthe"

    async def create_generation(
        self, trip_id: str, preset: str | None, *, idempotency_key: str
    ) -> Generation:
        self.calls.append(("create_generation", trip_id, preset, idempotency_key))
        if self.create_generation_error:
            raise self.create_generation_error
        return Generation(id=uuid4(), status="queued")

    async def get_generation(self, generation_id: UUID) -> Generation:
        status = self.generation_statuses.pop(0)
        plan_id = uuid4() if status == "succeeded" else None
        return Generation(
            id=generation_id, status=status, plan_id=plan_id, error=self.generation_error
        )

    async def get_plan(self, plan_id: UUID) -> PlanSummary:
        return self.plan

    async def rename_member(self, trip_id: str, handle: str, name: str) -> None:
        self.calls.append(("rename_member", trip_id, handle, name))


class FakeSender:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    async def send(self, chat_guid: str, text: str) -> None:
        self.sent.append((chat_guid, text))


async def no_sleep(seconds: float) -> None:
    await asyncio.sleep(0)


@pytest.fixture
def api() -> FakeApi:
    return FakeApi()


@pytest.fixture
def sender() -> FakeSender:
    return FakeSender()


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def state_path(tmp_path) -> Path:
    return tmp_path / "relay.json"


@pytest.fixture
def relay(api, sender, clock, state_path) -> Relay:
    return Relay(
        api=api,
        sender=sender,
        state=RelayState(),
        state_path=state_path,
        web_base_url="https://questline.test/",
        flush_seconds=15,
        flush_max=20,
        clock=clock,
        sleep=no_sleep,
    )


def row(rowid: int, text: str | None = "let's hit McWay Falls", **fields) -> ImsgMessage:
    values = {
        "id": rowid,
        "guid": f"guid-{rowid}",
        "chat_id": 7,
        "chat_guid": CHAT,
        "is_group": True,
        "sender": SAM,
        "sender_name": "Sam Lee",
        "is_from_me": False,
        "text": text,
        "created_at": datetime(2026, 10, 17, 16, 30, tzinfo=UTC),
        **fields,
    }
    return ImsgMessage.model_validate(values)


def linked(api: FakeApi) -> FakeApi:
    api.links[CHAT] = TRIP_ID
    return api


def saved_rowid(state_path: Path) -> int:
    return RelayState.load(state_path).last_rowid


def replies(sender: FakeSender) -> list[str]:
    return [text for chat, text in sender.sent if chat == CHAT]


# Inbound messages


async def test_text_in_a_linked_chat_is_batched_after_the_flush_interval(
    relay, api, clock, state_path
):
    linked(api)
    await relay.handle(row(1))
    await relay.flush()
    assert api.batches == []
    clock.now += 15
    await relay.flush()
    [(trip_id, [message])] = api.batches
    assert trip_id == TRIP_ID
    assert message == BatchMessage(
        guid="guid-1",
        handle=SAM,
        display_name="Sam Lee",
        sent_at=datetime(2026, 10, 17, 16, 30, tzinfo=UTC),
        text="let's hit McWay Falls",
    )
    assert saved_rowid(state_path) == 1


async def test_cursor_is_not_saved_past_unflushed_rows(relay, api, state_path):
    linked(api)
    await relay.handle(row(1, is_from_me=True))
    await relay.handle(row(2))
    await relay.flush()
    assert saved_rowid(state_path) == 1


@pytest.mark.parametrize(
    "fields",
    [
        {"is_from_me": True},
        {"is_group": False},
        {"text": None},
        {"text": "   "},
        {"text": "x" * 10_001},
    ],
)
async def test_rows_that_are_not_group_chat_text_are_skipped(relay, api, clock, fields):
    linked(api)
    await relay.handle(row(1, **fields))
    clock.now += 15
    await relay.flush()
    assert api.batches == []


async def test_unlinked_chats_are_ignored_and_negative_lookups_are_cached(relay, api, clock):
    await relay.handle(row(1))
    await relay.handle(row(2))
    clock.now += 15
    await relay.flush()
    assert api.batches == []
    assert api.calls == [("lookup_chat", CHAT)]
    clock.now += 60
    await relay.handle(row(3))
    assert api.calls.count(("lookup_chat", CHAT)) == 2


async def test_linked_chat_lookup_is_saved_to_state(relay, api, state_path):
    linked(api)
    await relay.handle(row(1))
    await relay.handle(row(2))
    assert api.calls == [("lookup_chat", CHAT)]
    assert RelayState.load(state_path).chats == {CHAT: TRIP_ID}


async def test_replayed_rows_are_ignored(relay, api, clock):
    linked(api)
    await relay.handle(row(1))
    await relay.handle(row(1))
    clock.now += 15
    await relay.flush()
    assert [len(messages) for _, messages in api.batches] == [1]


async def test_self_chosen_name_overrides_the_contacts_name(relay, api, clock):
    linked(api)
    relay.state.names[SAM] = "Sammy"
    await relay.handle(row(1))
    clock.now += 15
    await relay.flush()
    assert api.batches[0][1][0].display_name == "Sammy"


async def test_unavailable_api_keeps_the_batch_for_a_later_retry(relay, api, clock, state_path):
    linked(api)
    api.fail_batches = [Unavailable(503, "unavailable", "down")]
    await relay.handle(row(1))
    clock.now += 15
    await relay.flush()
    assert api.batches == []
    assert saved_rowid(state_path) == 0
    clock.now += 15
    await relay.flush()
    assert len(api.batches) == 1
    assert saved_rowid(state_path) == 1


async def test_rejected_batch_is_dropped_so_the_cursor_moves_on(relay, api, clock, state_path):
    linked(api)
    api.fail_batches = [Rejected(413, "too_large", "Transcript too large")]
    await relay.handle(row(1))
    clock.now += 15
    await relay.flush()
    clock.now += 15
    await relay.flush()
    assert api.batches == []
    assert saved_rowid(state_path) == 1


async def test_unavailable_lookup_is_retried_on_the_next_flush(relay, api, clock):
    linked(api)
    api.fail_lookups = [Unavailable(0, "unavailable", "ConnectError")]
    await relay.handle(row(1))
    await relay.flush()  # retries the lookup and buffers the row
    clock.now += 15
    await relay.flush()
    assert [m.guid for _, messages in api.batches for m in messages] == ["guid-1"]


async def test_vote_tapbacks_are_posted_immediately(relay, api, state_path):
    linked(api)
    tapback = {"is_reaction": True, "reacted_to_guid": "guid-1", "is_reaction_add": True}
    await relay.handle(row(2, text=None, reaction_type="love", **tapback))
    await relay.handle(
        row(3, text=None, reaction_type="dislike", **{**tapback, "is_reaction_add": False})
    )
    await relay.flush()
    assert api.reactions == [
        (
            TRIP_ID,
            [
                Reaction(handle=SAM, target_guid="guid-1", kind="love", added=True),
                Reaction(handle=SAM, target_guid="guid-1", kind="dislike", added=False),
            ],
        )
    ]
    assert saved_rowid(state_path) == 3


async def test_other_tapbacks_are_ignored(relay, api):
    linked(api)
    await relay.handle(
        row(2, text=None, is_reaction=True, reaction_type="laugh", reacted_to_guid="guid-1")
    )
    await relay.flush()
    assert api.reactions == []


# Commands


async def test_link_links_the_chat_and_posts_the_one_time_notice(relay, api, sender, clock):
    await relay.handle(row(1, text=f"@questline link {TRIP_ID}"))
    assert ("link_chat", TRIP_ID, CHAT) in api.calls
    assert relay.state.chats == {CHAT: TRIP_ID}
    [notice] = replies(sender)
    assert "Big Sur weekend" in notice
    assert "Google Gemini" in notice
    assert "@questline unlink" in notice
    assert "https://questline.test/t/abc123" in notice
    clock.now += 15
    await relay.flush()
    assert api.batches == []  # commands are never forwarded for extraction


async def test_link_to_a_chat_linked_elsewhere_explains_the_conflict(relay, api, sender):
    api.link_error = Conflict(409, "chat_linked", "Linked to another trip")
    await relay.handle(row(1, text=f"@questline link {TRIP_ID}"))
    assert "already linked" in replies(sender)[0]
    assert relay.state.chats == {}


async def test_link_to_an_unknown_trip(relay, api, sender):
    api.link_error = NotFound(404, "not_found", "Trip not found")
    await relay.handle(row(1, text="@questline link nope"))
    assert "Couldn't find that trip" in replies(sender)[0]


async def test_link_without_id_replies_with_the_trip_link(relay, api, sender):
    linked(api)
    await relay.handle(row(1, text="@questline link"))
    assert replies(sender) == ["https://questline.test/t/abc123"]


async def test_commands_in_an_unlinked_chat_explain_how_to_link(relay, sender):
    await relay.handle(row(1, text="@questline build"))
    assert "@questline link <trip ID>" in replies(sender)[0]


async def test_unlink_stops_reading_the_chat(relay, api, sender, clock):
    linked(api)
    await relay.handle(row(1, text="@questline unlink"))
    assert ("unlink_chat", TRIP_ID) in api.calls
    assert replies(sender) == ["Stopped reading this chat."]
    await relay.handle(row(2))
    clock.now += 15
    await relay.flush()
    assert api.batches == []


async def test_build_reports_the_ready_questline(relay, api, sender):
    linked(api)
    await relay.handle(row(1, text="@questline build treat"))
    await relay.wait_for_tasks()
    assert ("create_generation", TRIP_ID, "treat", "guid-1") in api.calls
    assert replies(sender) == [
        "Building your questline…",
        "Questline ready: 3 main quests, est. $40–85/person (food + activities). "
        "https://questline.test/t/abc123",
    ]


async def test_build_marks_a_partial_estimate(relay, api, sender):
    linked(api)
    api.plan = PlanSummary(main_quests=1, estimate=(10, 20), estimate_is_partial=True)
    await relay.handle(row(1, text="@questline build"))
    await relay.wait_for_tasks()
    assert (
        "1 main quest, est. $10–20/person (food + activities; some stops unpriced)"
        in (replies(sender)[-1])
    )


async def test_build_failure_relays_the_sanitized_error(relay, api, sender):
    linked(api)
    api.generation_statuses = ["failed"]
    api.generation_error = "Planner unavailable"
    await relay.handle(row(1, text="@questline build"))
    await relay.wait_for_tasks()
    assert replies(sender)[-1] == "Build failed: Planner unavailable"


async def test_build_when_the_planner_is_not_ready_says_so(relay, api, sender):
    # Gemini mode answers 503 provider_unavailable until plan building ships; not an outage.
    linked(api)
    api.create_generation_error = Unavailable(
        503, "provider_unavailable", "Gemini provider is not implemented yet"
    )
    await relay.handle(row(1, text="@questline build"))
    await relay.wait_for_tasks()
    assert replies(sender)[-1] == (
        "Plan building isn't available yet. Waypoints and votes are on the map: "
        "https://questline.test/t/abc123"
    )


async def test_build_during_an_outage_says_questline_is_unreachable(relay, api, sender):
    linked(api)
    api.create_generation_error = Unavailable(503, "unavailable", "down")
    await relay.handle(row(1, text="@questline build"))
    await relay.wait_for_tasks()
    assert replies(sender)[-1] == UNREACHABLE


async def test_build_that_outlasts_the_poll_window_points_to_the_map(relay, api, sender, clock):
    linked(api)
    api.generation_statuses = ["running"] * 1000

    async def slow_sleep(seconds: float) -> None:
        clock.now += seconds

    relay.sleep = slow_sleep
    await relay.handle(row(1, text="@questline build"))
    await relay.wait_for_tasks()
    assert replies(sender)[-1] == (
        "Still building — the map will update: https://questline.test/t/abc123"
    )


async def test_add_place(relay, api, sender):
    linked(api)
    await relay.handle(row(1, text="@questline add nepenthe big sur"))
    assert ("add_place", TRIP_ID, "nepenthe big sur") in api.calls
    assert replies(sender) == ["Added Nepenthe · https://questline.test/t/abc123"]


async def test_add_unknown_place(relay, api, sender):
    linked(api)
    api.place_error = NotFound(404, "place_not_found", "No match")
    await relay.handle(row(1, text="@questline add zzzz"))
    assert replies(sender) == ["Couldn't find that place — try adding the city."]


async def test_set_name_is_saved_and_sent(relay, api, sender, state_path):
    linked(api)
    await relay.handle(row(1, text="@questline I'm Sam"))
    assert ("rename_member", TRIP_ID, SAM, "Sam") in api.calls
    assert RelayState.load(state_path).names == {SAM: "Sam"}
    assert replies(sender) == ["Got it, Sam."]


async def test_unreachable_api_during_a_command_says_so(relay, api, sender):
    linked(api)
    api.place_error = Unavailable(0, "unavailable", "ConnectError")
    await relay.handle(row(1, text="@questline add nepenthe"))
    assert replies(sender) == ["Questline is unreachable right now — try again in a minute."]


async def test_unknown_command_gets_usage_help(relay, api, sender):
    linked(api)
    await relay.handle(row(1, text="@questline what's up"))
    [help_text] = replies(sender)
    assert "@questline build" in help_text and "@questline add" in help_text


# Self-account mode: the relay runs on a member's own Apple ID (RELAY_SELF_HANDLE)

ME = "+15559998888"
PREFIX = "🧭 Questline: "


@pytest.fixture
def self_relay(api, sender, clock, state_path) -> Relay:
    return Relay(
        api=api,
        sender=sender,
        state=RelayState(),
        state_path=state_path,
        web_base_url="https://questline.test/",
        flush_seconds=15,
        flush_max=20,
        clock=clock,
        sleep=no_sleep,
        self_handle=ME,
    )


def mine(rowid: int, text: str | None = "I vote Nepenthe", **fields) -> ImsgMessage:
    return row(rowid, text, is_from_me=True, sender="", sender_name=None, **fields)


async def test_own_messages_are_forwarded_under_the_self_handle(self_relay, api, clock):
    linked(api)
    await self_relay.handle(mine(1))
    clock.now += 15
    await self_relay.flush()
    [(_, [message])] = api.batches
    assert (message.handle, message.text, message.display_name) == (ME, "I vote Nepenthe", None)


async def test_own_tapbacks_count_as_votes(self_relay, api):
    linked(api)
    await self_relay.handle(
        mine(2, text=None, is_reaction=True, reaction_type="like", reacted_to_guid="guid-1")
    )
    await self_relay.flush()
    assert api.reactions == [
        (TRIP_ID, [Reaction(handle=ME, target_guid="guid-1", kind="like", added=True)])
    ]


async def test_own_commands_run_and_replies_are_prefixed(self_relay, api, sender):
    linked(api)
    await self_relay.handle(mine(1, text="@questline add nepenthe"))
    assert replies(sender) == [f"{PREFIX}Added Nepenthe · https://questline.test/t/abc123"]


async def test_echoes_of_the_relays_own_replies_are_dropped(self_relay, api, sender, clock):
    linked(api)
    await self_relay.handle(mine(1, text="@questline add nepenthe"))
    [reply] = replies(sender)
    await self_relay.handle(mine(2, text=reply))
    # Messages can split a link into its own row; that is an echo too.
    await self_relay.handle(mine(3, text="https://questline.test/t/abc123"))
    clock.now += 15
    await self_relay.flush()
    assert api.batches == []


async def test_echo_memory_expires(self_relay, api, sender, clock):
    linked(api)
    await self_relay.handle(mine(1, text="@questline add nepenthe"))
    [reply] = replies(sender)
    clock.now += 301
    await self_relay.handle(mine(2, text=reply))
    clock.now += 15
    await self_relay.flush()
    assert [m.guid for _, messages in api.batches for m in messages] == ["guid-2"]


async def test_dedicated_bot_mode_still_ignores_its_own_account(relay, api, sender, clock):
    linked(api)
    await relay.handle(mine(1, text="@questline add nepenthe"))
    await relay.handle(mine(2))
    clock.now += 15
    await relay.flush()
    assert (api.batches, sender.sent) == ([], [])


# Supervisor loop against the fake imsg process


async def test_run_links_and_forwards_messages_through_imsg(api, state_path, monkeypatch, tmp_path):
    log = tmp_path / "imsg.jsonl"
    rows = [
        row(1, text=f"@questline link {TRIP_ID}").model_dump(mode="json"),
        row(2).model_dump(mode="json"),
    ]
    monkeypatch.setenv("FAKE_IMSG_MESSAGES", json.dumps(rows))
    monkeypatch.setenv("FAKE_IMSG_LOG", str(log))
    relay = Relay(
        api=api,
        sender=None,
        state=RelayState(),
        state_path=state_path,
        web_base_url="https://questline.test",
        flush_seconds=0,
        flush_max=20,
    )
    task = asyncio.create_task(relay.run(FAKE_IMSG, flush_interval=0.01))
    async with asyncio.timeout(5):
        await api.batch_posted.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert [m.guid for m in api.batches[0][1]] == ["guid-2"]
    sends = [json.loads(line) for line in log.read_text().splitlines()]
    assert any(r["method"] == "send" and r["params"]["chat_guid"] == CHAT for r in sends)
    assert saved_rowid(state_path) == 2


async def test_build_reply_says_what_changed_and_what_is_contested(relay, api, sender):
    linked(api)
    api.plan = PlanSummary(
        main_quests=2,
        side_quests=1,
        estimate=None,
        estimate_is_partial=False,
        changes=["Added Taco Bell as a side quest", "Moved Nepenthe to side quests", "Reordered"],
        contested=["McWay Falls"],
    )
    await relay.handle(row(1, text="@questline build"))
    await relay.wait_for_tasks()
    assert replies(sender)[-1] == (
        "Questline ready: 2 main quests + 1 side quest. Changed: added Taco Bell as a side "
        "quest; moved Nepenthe to side quests; and 1 more. Split votes: McWay Falls — resolve "
        "on the map. https://questline.test/t/abc123"
    )


async def test_build_reply_says_when_nothing_changed(relay, api, sender):
    linked(api)
    api.plan = PlanSummary(
        main_quests=2,
        estimate=None,
        estimate_is_partial=False,
        changes=["No changes from the previous questline"],
    )
    await relay.handle(row(1, text="@questline build"))
    await relay.wait_for_tasks()
    assert "No changes since the last build." in replies(sender)[-1]


def test_plan_summary_reads_changes_and_split_votes():
    content = {
        "graph": {
            "nodes": [
                {"id": "start", "role": "start", "quest": "main", "title": "A"},
                {"id": "p1", "role": "stop", "quest": "main", "title": "McWay Falls"},
                {"id": "p2", "role": "stop", "quest": "side", "title": "Taco Bell"},
            ]
        },
        "per_person_estimate": None,
        "changed_from_previous": ["Added Taco Bell as a side quest"],
        "conflicts": [
            {"node_id": "p1", "kind": "split_vote", "detail": "x"},
            {"node_id": "p2", "kind": "over_budget", "detail": "y"},
        ],
    }
    summary = PlanSummary.from_content(content)
    assert (summary.main_quests, summary.side_quests) == (1, 1)
    assert summary.contested == ["McWay Falls"]
    assert summary.changes == ["Added Taco Bell as a side quest"]
