import asyncio
import contextlib
import itertools
import json
import logging
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from types import TracebackType
from typing import Any

from pydantic import ValidationError

from questline.integrations.imessage.models import ImsgMessage

logger = logging.getLogger(__name__)

# One JSON object per line; rows with attachment metadata can be long.
_LINE_LIMIT = 16 * 1024 * 1024


class ImsgError(Exception):
    def __init__(self, code: int, message: str, data: Any = None) -> None:
        super().__init__(f"imsg error {code}: {message}")
        self.code = code
        self.data = data


class ImsgClosed(Exception):
    """The `imsg rpc` child exited; start a new session to continue."""


@dataclass(frozen=True)
class WatchEvent:
    method: str  # "message", "watch.overflow", ...
    params: dict[str, Any]
    message: ImsgMessage | None = None


class ImsgRpc:
    """One `imsg rpc` child speaking JSON-RPC 2.0 over stdio (imsg docs/rpc.md).

    A session ends when the child exits: pending calls raise `ImsgClosed` and `events()`
    finishes. Restarting is the caller's job.
    """

    def __init__(self, command: Sequence[str]) -> None:
        self._command = list(command)
        self._process: asyncio.subprocess.Process | None = None
        self._ids = itertools.count(1)
        self._pending: dict[int, asyncio.Future[Any]] = {}
        self._events: asyncio.Queue[WatchEvent | None] = asyncio.Queue()
        self._write_lock = asyncio.Lock()
        self._tasks: list[asyncio.Task[None]] = []

    async def __aenter__(self) -> "ImsgRpc":
        self._process = await asyncio.create_subprocess_exec(
            *self._command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            limit=_LINE_LIMIT,
        )
        self._tasks = [
            asyncio.create_task(self._read_stdout()),
            asyncio.create_task(self._read_stderr()),
        ]
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        process = self._process
        if process is not None and process.returncode is None:
            if process.stdin is not None:
                process.stdin.close()  # EOF: imsg drains accepted work and exits
            try:
                await asyncio.wait_for(process.wait(), timeout=5)
            except TimeoutError:
                process.kill()
                await process.wait()
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)

    async def call(self, method: str, params: dict[str, Any] | None = None) -> Any:
        process = self._process
        if process is None or process.stdin is None or process.returncode is not None:
            raise ImsgClosed("imsg rpc is not running")
        request_id = next(self._ids)
        future: asyncio.Future[Any] = asyncio.get_running_loop().create_future()
        self._pending[request_id] = future
        request: dict[str, Any] = {"jsonrpc": "2.0", "id": request_id, "method": method}
        if params is not None:
            request["params"] = params
        try:
            async with self._write_lock:
                process.stdin.write((json.dumps(request) + "\n").encode())
                await process.stdin.drain()
        except (BrokenPipeError, ConnectionResetError) as exc:
            self._pending.pop(request_id, None)
            raise ImsgClosed("imsg rpc stdin closed") from exc
        return await future

    async def events(self) -> AsyncIterator[WatchEvent]:
        while (event := await self._events.get()) is not None:
            yield event
        self._events.put_nowait(None)  # later readers also see the end

    async def subscribe(self, since_rowid: int) -> str:
        result = await self.call(
            "watch.subscribe", {"since_rowid": since_rowid, "include_reactions": True}
        )
        return result["subscription"]

    async def send(self, chat_guid: str, text: str) -> None:
        await self.call("send", {"chat_guid": chat_guid, "text": text})

    async def history(self, chat_id: int, limit: int) -> list[ImsgMessage]:
        result = await self.call("messages.history", {"chat_id": chat_id, "limit": limit})
        return [ImsgMessage.model_validate(row) for row in result["messages"]]

    async def _read_stdout(self) -> None:
        assert self._process is not None and self._process.stdout is not None
        try:
            async for line in self._process.stdout:
                self._dispatch(line)
        finally:
            for future in self._pending.values():
                if not future.done():
                    future.set_exception(ImsgClosed("imsg rpc exited"))
            self._pending.clear()
            self._events.put_nowait(None)

    def _dispatch(self, line: bytes) -> None:
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            logger.warning("imsg rpc wrote a non-JSON line; ignoring it")
            return
        if "method" in payload and "id" not in payload:
            self._notify(payload["method"], payload.get("params") or {})
            return
        future = self._pending.pop(payload.get("id"), None)
        if future is None or future.done():
            return
        if "error" in payload:
            error = payload["error"]
            future.set_exception(ImsgError(error["code"], error["message"], error.get("data")))
        else:
            future.set_result(payload.get("result"))

    def _notify(self, method: str, params: dict[str, Any]) -> None:
        message = None
        if method == "message":
            try:
                message = ImsgMessage.model_validate(params["message"])
            except (KeyError, ValidationError):
                logger.warning("Skipping an imsg message row that failed validation")
                return
        self._events.put_nowait(WatchEvent(method, params, message))

    async def _read_stderr(self) -> None:
        assert self._process is not None and self._process.stderr is not None
        with contextlib.suppress(ValueError):  # over-long diagnostic line
            async for line in self._process.stderr:
                logger.info("imsg: %s", line.decode(errors="replace").rstrip())
