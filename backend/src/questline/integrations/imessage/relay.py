"""Silent iMessage bot relay (SPEC §11.1).

Run on the relay Mac: `uv run python -m questline.integrations.imessage.relay`
"""

import asyncio
import contextlib
import logging
import time
from collections.abc import Awaitable, Callable, Sequence
from pathlib import Path
from typing import Literal, Protocol
from uuid import UUID

from questline.integrations.imessage.api import (
    ApiError,
    BatchMessage,
    Conflict,
    Generation,
    NotFound,
    PlanSummary,
    QuestlineClient,
    Reaction,
    Trip,
    Unavailable,
)
from questline.integrations.imessage.batcher import Batch, Batcher, Cursor
from questline.integrations.imessage.commands import (
    Add,
    Build,
    Command,
    Help,
    Link,
    Preset,
    SetName,
    Unlink,
    parse_command,
)
from questline.integrations.imessage.imsg_rpc import ImsgClosed, ImsgError, ImsgRpc
from questline.integrations.imessage.models import ImsgMessage
from questline.integrations.imessage.settings import RelaySettings
from questline.integrations.imessage.state import RelayState

logger = logging.getLogger(__name__)

MAX_MESSAGE_CHARS = 10_000
UNLINKED_CACHE_SECONDS = 60
ECHO_SECONDS = 300
SELF_REPLY_PREFIX = "🧭 Questline: "
VOTE_TAPBACKS: dict[str, Literal["love", "like", "dislike"]] = {
    "love": "love",
    "like": "like",
    "dislike": "dislike",
}

USAGE = (
    "Questline commands: @questline build [shoestring|comfortable|treat] · "
    "@questline add <place> · @questline link · @questline I'm <name> · @questline unlink"
)
NOT_LINKED = "This chat isn't linked to a trip. Send @questline link <trip ID> from the share link."
UNREACHABLE = "Questline is unreachable right now — try again in a minute."


class RelayApi(Protocol):
    async def lookup_chat(self, chat_guid: str) -> str | None: ...
    async def link_chat(self, trip_id: str, chat_guid: str) -> Trip: ...
    async def unlink_chat(self, trip_id: str) -> None: ...
    async def post_batch(self, trip_id: str, messages: list[BatchMessage]) -> int: ...
    async def post_reactions(self, trip_id: str, reactions: list[Reaction]) -> None: ...
    async def add_place(self, trip_id: str, query: str) -> str: ...
    async def create_generation(
        self, trip_id: str, preset: Preset | None, *, idempotency_key: str
    ) -> Generation: ...
    async def get_generation(self, generation_id: UUID) -> Generation: ...
    async def get_plan(self, plan_id: UUID) -> PlanSummary: ...
    async def rename_member(self, trip_id: str, handle: str, name: str) -> None: ...


class Sender(Protocol):
    async def send(self, chat_guid: str, text: str) -> None: ...


class Relay:
    def __init__(
        self,
        *,
        api: RelayApi,
        sender: Sender | None,
        state: RelayState,
        state_path: Path,
        web_base_url: str,
        flush_seconds: float,
        flush_max: int,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        poll_interval: float = 2,
        poll_timeout: float = 180,
        self_handle: str | None = None,
    ) -> None:
        self.api = api
        self.sender = sender
        self.state = state
        self.sleep = sleep
        self._state_path = state_path
        self._web_base_url = web_base_url.rstrip("/")
        self._clock = clock
        self._poll_interval = poll_interval
        self._poll_timeout = poll_timeout
        self._cursor = Cursor(state.last_rowid)
        self._messages: Batcher[BatchMessage] = Batcher(flush_seconds, flush_max, clock)
        self._reactions: Batcher[Reaction] = Batcher(0, flush_max, clock)
        self._unlinked_until: dict[str, float] = {}
        self._retry: list[ImsgMessage] = []
        self._tasks: set[asyncio.Task[None]] = set()
        # Self-account mode: the relay shares a member's Apple ID, so "from me" rows are either
        # that member typing (forwarded as `self_handle`) or echoes of our replies (dropped).
        self._self_handle = self_handle
        self._sent: list[tuple[float, str, str]] = []  # (expires_at, chat_guid, text)

    # Inbound rows

    async def handle(self, message: ImsgMessage) -> None:
        """Route one watch row. Rows are handled at least once; never log message text."""
        if not self._cursor.begin(message.id):
            return
        await self._route(message)

    async def _route(self, message: ImsgMessage) -> None:
        buffered = False
        try:
            buffered = await self._route_row(message)
        except Unavailable:
            logger.warning("API unavailable; will retry row %s", message.id)
            self._retry.append(message)
            buffered = True
        finally:
            if not buffered:
                self._cursor.done(message.id)

    async def _route_row(self, message: ImsgMessage) -> bool:
        """Return True if the row is now buffered (handled later by `flush`)."""
        chat_guid = message.chat_guid
        if not message.is_group or not chat_guid:
            return False  # the bot only serves group chats
        if message.is_from_me:
            if self._self_handle is None or self._is_echo(chat_guid, message):
                return False  # echo guard
            message = message.model_copy(update={"sender": self._self_handle})
        text = (message.text or "").strip()
        command = None if message.is_reaction else parse_command(text)
        if command is not None:
            await self._run_command(message, chat_guid, command)
            return False
        trip_id = await self._trip_for(chat_guid)
        if trip_id is None:
            return False
        if message.is_reaction:
            kind = VOTE_TAPBACKS.get(message.reaction_type or "")
            if kind is None or not message.reacted_to_guid:
                return False
            added = message.is_reaction_add is not False
            reaction = Reaction(
                handle=message.sender, target_guid=message.reacted_to_guid, kind=kind, added=added
            )
            self._reactions.add(trip_id, message.id, reaction)
            return True
        if len(text) > MAX_MESSAGE_CHARS:
            logger.warning("Skipping row %s: over %d characters", message.id, MAX_MESSAGE_CHARS)
            return False
        if not text:
            return False
        self._messages.add(
            trip_id,
            message.id,
            BatchMessage(
                guid=message.guid,
                handle=message.sender,
                display_name=self.state.names.get(message.sender) or message.sender_name,
                sent_at=message.created_at,
                text=text,
                reply_to_guid=message.thread_originator_guid,
            ),
        )
        return True

    async def _trip_for(self, chat_guid: str) -> str | None:
        if trip_id := self.state.chats.get(chat_guid):
            return trip_id
        if self._unlinked_until.get(chat_guid, 0) > self._clock():
            return None
        trip_id = await self.api.lookup_chat(chat_guid)
        if trip_id is None:
            self._unlinked_until[chat_guid] = self._clock() + UNLINKED_CACHE_SECONDS
            return None
        self.state.chats[chat_guid] = trip_id
        self._save()
        return trip_id

    # Flushing

    async def flush(self) -> None:
        retry, self._retry = self._retry, []
        for message in retry:
            await self._route(message)
        for batch in self._messages.ready():
            await self._post(self._messages, batch, self.api.post_batch)
        for batch in self._reactions.ready():
            await self._post(self._reactions, batch, self.api.post_reactions)
        if self._cursor.safe_rowid != self.state.last_rowid:
            self.state.last_rowid = self._cursor.safe_rowid
            self._save()

    async def _post[T](
        self,
        batcher: Batcher[T],
        batch: Batch[T],
        post: Callable[[str, list[T]], Awaitable[object]],
    ) -> None:
        trip_id = str(batch.key)
        try:
            await post(trip_id, batch.items)
        except Unavailable:
            logger.warning(
                "API unavailable; keeping %d rows for trip %s", len(batch.items), trip_id
            )
            batcher.retry_later(batch)
            return
        except ApiError as exc:
            # Permanent rejection: drop it rather than blocking the cursor forever.
            logger.error("Dropping %d rows for trip %s: %s", len(batch.items), trip_id, exc)
        batcher.complete(batch)
        for rowid in batch.rowids:
            self._cursor.done(rowid)

    # Commands

    async def _run_command(self, message: ImsgMessage, chat_guid: str, command: Command) -> None:
        try:
            await self._command(message, chat_guid, command)
        except Unavailable:
            await self._reply(chat_guid, UNREACHABLE)
        except ApiError as exc:
            logger.error("Command %s failed: %s", type(command).__name__, exc)
            await self._reply(chat_guid, "Something went wrong — try again.")

    async def _command(self, message: ImsgMessage, chat_guid: str, command: Command) -> None:
        if isinstance(command, Link) and command.trip_id is not None:
            await self._link(chat_guid, command.trip_id)
            return
        trip_id = await self._trip_for(chat_guid)
        if trip_id is None:
            await self._reply(chat_guid, NOT_LINKED)
            return
        match command:
            case Link():
                await self._reply(chat_guid, self._trip_url(trip_id))
            case Unlink():
                await self.api.unlink_chat(trip_id)
                self.state.chats.pop(chat_guid, None)
                self._save()
                await self._reply(chat_guid, "Stopped reading this chat.")
            case Build(preset=preset):
                task = asyncio.create_task(self._build(chat_guid, trip_id, preset, message.guid))
                self._tasks.add(task)
                task.add_done_callback(self._tasks.discard)
            case Add(query=query):
                try:
                    name = await self.api.add_place(trip_id, query)
                except NotFound:
                    await self._reply(
                        chat_guid, "Couldn't find that place near this trip — try adding the city."
                    )
                    return
                await self._reply(chat_guid, f"Added {name} · {self._trip_url(trip_id)}")
            case SetName(name=name):
                self.state.names[message.sender] = name
                self._save()
                with contextlib.suppress(NotFound):  # no member yet; next batch carries the name
                    await self.api.rename_member(trip_id, message.sender, name)
                await self._reply(chat_guid, f"Got it, {name}.")
            case Help():
                await self._reply(chat_guid, USAGE)

    async def _link(self, chat_guid: str, trip_id: str) -> None:
        try:
            trip = await self.api.link_chat(trip_id, chat_guid)
        except Conflict:
            await self._reply(
                chat_guid,
                "This chat is already linked to another trip. Send @questline unlink first.",
            )
            return
        except NotFound:
            await self._reply(
                chat_guid, "Couldn't find that trip — check the ID in the share link."
            )
            return
        self.state.chats[chat_guid] = trip.id
        self._unlinked_until.pop(chat_guid, None)
        self._save()
        await self._reply(
            chat_guid,
            f"Questline is now reading this chat for “{trip.name}”. New messages are sent to "
            "Google Gemini to find places for the map. Send @questline unlink to stop. "
            f"{self._trip_url(trip.id)}",
        )

    async def _build(
        self, chat_guid: str, trip_id: str, preset: Preset | None, idempotency_key: str
    ) -> None:
        try:
            await self._reply(chat_guid, "Building your questline…")
            generation = await self.api.create_generation(
                trip_id, preset, idempotency_key=idempotency_key
            )
            deadline = self._clock() + self._poll_timeout
            while generation.status in ("queued", "running"):
                if self._clock() >= deadline:
                    await self._reply(
                        chat_guid,
                        f"Still building — the map will update: {self._trip_url(trip_id)}",
                    )
                    return
                await self.sleep(self._poll_interval)
                generation = await self.api.get_generation(generation.id)
            if generation.status == "failed" or generation.plan_id is None:
                await self._reply(chat_guid, f"Build failed: {generation.error or 'unknown error'}")
                return
            plan = await self.api.get_plan(generation.plan_id)
            await self._reply(chat_guid, self._ready_text(plan, trip_id))
        except Conflict as exc:
            await self._reply(chat_guid, f"Can't build right now: {exc.message}")
        except Unavailable as exc:
            # The backend is up but its planner isn't configured or built yet; not an outage.
            if exc.code == "provider_unavailable":
                await self._reply(
                    chat_guid,
                    "Plan building isn't available yet. Waypoints and votes are on the map: "
                    f"{self._trip_url(trip_id)}",
                )
            else:
                await self._reply(chat_guid, UNREACHABLE)
        except ApiError as exc:
            logger.error("Build failed for trip %s: %s", trip_id, exc)
            await self._reply(chat_guid, "Build failed — try again.")

    def _ready_text(self, plan: PlanSummary, trip_id: str) -> str:
        quests = f"{plan.main_quests} main quest{'' if plan.main_quests == 1 else 's'}"
        if plan.side_quests:
            quests += f" + {plan.side_quests} side quest{'' if plan.side_quests == 1 else 's'}"
        estimate = ""
        if plan.estimate is not None:
            low, high = plan.estimate
            scope = "food + activities"
            if plan.estimate_is_partial:
                scope += "; some stops unpriced"
            estimate = f", est. ${low:.0f}–{high:.0f}/person ({scope})"
        notes = ""
        if plan.changes:
            shown = [change[:1].lower() + change[1:] for change in plan.changes[:2]]
            more = len(plan.changes) - len(shown)
            text = "; ".join(shown) + (f"; and {more} more" if more else "")
            notes += (
                " No changes since the last build."
                if plan.changes == ["No changes from the previous questline"]
                else f" Changed: {text}."
            )
        if plan.contested:
            notes += f" Split votes: {', '.join(plan.contested)} — resolve on the map."
        return f"Questline ready: {quests}{estimate}.{notes} {self._trip_url(trip_id)}"

    async def wait_for_tasks(self) -> None:
        while self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)

    # Plumbing

    def _trip_url(self, trip_id: str) -> str:
        return f"{self._web_base_url}/t/{trip_id}"

    def _is_echo(self, chat_guid: str, message: ImsgMessage) -> bool:
        if message.is_reaction:
            return False  # the relay never sends tapbacks
        now = self._clock()
        self._sent = [sent for sent in self._sent if sent[0] > now]
        text = (message.text or "").strip()
        for _, sent_chat, sent_text in self._sent:
            if sent_chat != chat_guid:
                continue
            # Messages may split a link out of the reply into its own row.
            if text == sent_text or (text.startswith("http") and text in sent_text):
                return True
        return False

    async def _reply(self, chat_guid: str, text: str) -> None:
        if self.sender is None:
            logger.warning("imsg is not running; reply dropped")
            return
        if self._self_handle is not None:
            text = SELF_REPLY_PREFIX + text
            # Record before sending: the echo row can arrive before `send` returns.
            self._sent.append((self._clock() + ECHO_SECONDS, chat_guid, text))
        try:
            await self.sender.send(chat_guid, text)
        except (ImsgError, ImsgClosed) as exc:
            logger.error("Reply failed: %s", exc)

    def _save(self) -> None:
        self.state.save(self._state_path)

    # Supervisor

    async def run(self, imsg_command: Sequence[str], *, flush_interval: float = 1) -> None:
        """Watch forever, restarting `imsg rpc` with backoff when it exits."""
        backoff = 1.0
        while True:
            try:
                async with ImsgRpc(imsg_command) as rpc:
                    self.sender = rpc
                    await rpc.call("initialize", {"protocol_version": 1})
                    await rpc.subscribe(self._cursor.safe_rowid)
                    logger.info("Watching from rowid %d", self._cursor.safe_rowid)
                    backoff = 1.0
                    await self._consume(rpc, flush_interval)
            except (ImsgClosed, ImsgError, OSError) as exc:
                logger.error("imsg rpc stopped: %s", exc)
            finally:
                self.sender = None
            await self.flush()
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 60)

    async def _consume(self, rpc: ImsgRpc, flush_interval: float) -> None:
        flusher = asyncio.create_task(self._flush_forever(flush_interval))
        try:
            async for event in rpc.events():
                if event.message is not None:
                    await self.handle(event.message)
                elif event.method == "watch.overflow":
                    resume = int(event.params["resume_after_rowid"])
                    logger.warning("Watch overflow; resubscribing after rowid %d", resume)
                    await rpc.subscribe(resume)
        finally:
            flusher.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await flusher

    async def _flush_forever(self, interval: float) -> None:
        while True:
            await asyncio.sleep(interval)
            try:
                await self.flush()
            except Exception:
                logger.exception("Flush failed")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    settings = RelaySettings()  # pyright: ignore[reportCallIssue]  (read from env)
    asyncio.run(_serve(settings))


async def _serve(settings: RelaySettings) -> None:
    api = QuestlineClient(settings.questline_api_url, settings.api_token.get_secret_value())
    relay = Relay(
        api=api,
        sender=None,
        state=RelayState.load(settings.relay_state_path),
        state_path=settings.relay_state_path,
        web_base_url=settings.web_base_url,
        flush_seconds=settings.relay_flush_seconds,
        flush_max=settings.relay_flush_max,
        self_handle=settings.relay_self_handle,
    )
    try:
        await relay.run([settings.imsg_bin, "rpc"])
    finally:
        await api.aclose()


if __name__ == "__main__":
    main()
