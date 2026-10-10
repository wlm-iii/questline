from questline.integrations.imessage.batcher import Batcher, Cursor


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def make_batcher(clock: Clock, flush_seconds: float = 15, flush_max: int = 3) -> Batcher[str]:
    return Batcher(flush_seconds=flush_seconds, flush_max=flush_max, clock=clock)


def test_nothing_is_ready_before_the_flush_interval():
    clock = Clock()
    batcher = make_batcher(clock)
    batcher.add("trip-a", 1, "hi")
    clock.now += 14.9
    assert batcher.ready() == []


def test_buffer_is_ready_after_the_flush_interval():
    clock = Clock()
    batcher = make_batcher(clock)
    batcher.add("trip-a", 1, "hi")
    batcher.add("trip-a", 2, "there")
    clock.now += 15
    [batch] = batcher.ready()
    assert (batch.key, batch.rowids, batch.items) == ("trip-a", [1, 2], ["hi", "there"])


def test_full_buffer_is_ready_immediately_and_capped_at_flush_max():
    clock = Clock()
    batcher = make_batcher(clock)
    for rowid in range(1, 5):
        batcher.add("trip-a", rowid, f"m{rowid}")
    [batch] = batcher.ready()
    assert batch.rowids == [1, 2, 3]


def test_buffers_are_kept_per_key():
    clock = Clock()
    batcher = make_batcher(clock)
    batcher.add("trip-a", 1, "a")
    batcher.add("trip-b", 2, "b")
    clock.now += 15
    assert sorted(batch.key for batch in batcher.ready()) == ["trip-a", "trip-b"]


def test_complete_removes_only_the_batch_rows():
    clock = Clock()
    batcher = make_batcher(clock)
    batcher.add("trip-a", 1, "a")
    clock.now += 15
    [batch] = batcher.ready()
    batcher.add("trip-a", 2, "b")  # arrives while the batch is being posted
    batcher.complete(batch)
    assert batcher.ready() == []
    clock.now += 15
    assert [b.rowids for b in batcher.ready()] == [[2]]


def test_retry_later_waits_another_flush_interval():
    clock = Clock()
    batcher = make_batcher(clock)
    batcher.add("trip-a", 1, "a")
    clock.now += 15
    [batch] = batcher.ready()
    batcher.retry_later(batch)
    assert batcher.ready() == []
    clock.now += 15
    assert [b.rowids for b in batcher.ready()] == [[1]]


def test_zero_interval_is_always_ready():
    batcher = make_batcher(Clock(), flush_seconds=0)
    batcher.add("trip-a", 1, "a")
    assert [b.rowids for b in batcher.ready()] == [[1]]


def test_cursor_starts_at_the_resume_point():
    assert Cursor(41).safe_rowid == 41


def test_cursor_advances_past_handled_rows():
    cursor = Cursor(0)
    cursor.begin(5)
    cursor.done(5)
    assert cursor.safe_rowid == 5


def test_cursor_stops_before_the_oldest_pending_row():
    cursor = Cursor(0)
    for rowid in (5, 6, 7):
        cursor.begin(rowid)
    cursor.done(5)
    cursor.done(7)
    assert cursor.safe_rowid == 5
    cursor.done(6)
    assert cursor.safe_rowid == 7


def test_cursor_ignores_rows_at_or_before_the_resume_point():
    cursor = Cursor(10)
    cursor.begin(9)
    assert cursor.safe_rowid == 10


def test_cursor_reports_whether_a_row_is_new():
    cursor = Cursor(10)
    assert cursor.begin(11) is True
    assert cursor.begin(11) is False
    assert cursor.begin(3) is False
