import time
from collections.abc import Callable, Hashable
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Batch[T]:
    key: Hashable
    rowids: list[int]
    items: list[T]


@dataclass
class _Buffer[T]:
    started_at: float
    rows: list[tuple[int, T]] = field(default_factory=list)


class Batcher[T]:
    """Buffers rows per key; a buffer is ready when full or `flush_seconds` old."""

    def __init__(
        self,
        flush_seconds: float,
        flush_max: int,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._flush_seconds = flush_seconds
        self._flush_max = flush_max
        self._clock = clock
        self._buffers: dict[Hashable, _Buffer[T]] = {}

    def add(self, key: Hashable, rowid: int, item: T) -> None:
        buffer = self._buffers.setdefault(key, _Buffer(started_at=self._clock()))
        buffer.rows.append((rowid, item))

    def ready(self) -> list[Batch[T]]:
        now = self._clock()
        batches = []
        for key, buffer in self._buffers.items():
            if (
                len(buffer.rows) >= self._flush_max
                or now - buffer.started_at >= self._flush_seconds
            ):
                rows = buffer.rows[: self._flush_max]
                batches.append(Batch(key, [r for r, _ in rows], [item for _, item in rows]))
        return batches

    def complete(self, batch: Batch[T]) -> None:
        buffer = self._buffers[batch.key]
        sent = set(batch.rowids)
        buffer.rows = [row for row in buffer.rows if row[0] not in sent]
        if buffer.rows:
            buffer.started_at = self._clock()
        else:
            del self._buffers[batch.key]

    def retry_later(self, batch: Batch[T]) -> None:
        self._buffers[batch.key].started_at = self._clock()


class Cursor:
    """Highest watch rowid such that every row at or before it has been handled.

    Persisting this (not the last row seen) makes a restart replay unfinished rows; the
    backend dedupes redelivered messages by guid.
    """

    def __init__(self, resume_rowid: int) -> None:
        self._seen = resume_rowid
        self._pending: set[int] = set()

    def begin(self, rowid: int) -> bool:
        """Start tracking a row; False if it was already seen (a watch replay)."""
        if rowid <= self._seen:
            return False
        self._seen = rowid
        self._pending.add(rowid)
        return True

    def done(self, rowid: int) -> None:
        self._pending.discard(rowid)

    @property
    def safe_rowid(self) -> int:
        return min(self._pending) - 1 if self._pending else self._seen
