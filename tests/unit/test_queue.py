import logging
import threading
import time
from collections.abc import Generator

import pytest

from bridge.core.contracts import SceneSnapshot, SnapshotInvalidated
from bridge.core.queue import MAX_SCENE_SUMMARY_TASKS, QueueFull, TaskQueue
from bridge.core.router import BridgeMeta, Router
from protocol import envelope


class FakeClock:
    def __init__(self) -> None:
        self.now = 100.0

    def monotonic(self) -> float:
        return self.now


def req(method: str = "ping") -> envelope.Request:
    return envelope.Request.new(token="t", method=method, params={})


def make(handler=None, capacity=64):
    clock = FakeClock()
    q = TaskQueue(handler or (lambda r: envelope.ok_frame(r.id, {})), clock,
                  capacity=capacity, diag=logging.getLogger("test"))
    return q, clock


def test_batch_processes_within_budget_and_reports_idle_interval():
    q, clock = make()
    got: list[bytes] = []
    for _ in range(5):
        q.submit(req(), got.append, deadline=clock.now + 2.0)
    assert q.tick() == 0.02
    assert len(got) == 5


def test_budget_exhaustion_leaves_remainder_and_reports_busy():
    q, clock = make(handler=lambda r: (_advance(clock, 0.030), envelope.ok_frame(r.id, {}))[1])
    for _ in range(3):
        q.submit(req(), lambda b: None, deadline=clock.now + 2.0)
    assert q.tick(budget_ms=50) == 0.01
    assert q.pending == 1


def _advance(clock: FakeClock, dt: float) -> None:
    clock.now += dt


def test_expired_task_dropped_without_handler_call():
    calls = []
    q, clock = make(handler=lambda r: (calls.append(r), envelope.ok_frame(r.id, {}))[1])
    q.submit(req(), lambda b: None, deadline=clock.now - 0.001)
    q.tick()
    assert calls == []


def test_task_at_exact_deadline_is_dropped_without_handler_call():
    calls = []
    q, clock = make(handler=lambda r: (calls.append(r), envelope.ok_frame(r.id, {}))[1])
    q.submit(req(), lambda _body: None, deadline=clock.now)

    q.tick()

    assert calls == [] and q.pending == 0


@pytest.mark.parametrize("failure", [BrokenPipeError, RuntimeError])
def test_reply_failure_swallowed_and_next_task_processed(failure):
    q, clock = make()

    def broken(_: bytes) -> None:
        raise failure()

    got: list[bytes] = []
    q.submit(req(), broken, deadline=clock.now + 2.0)
    q.submit(req(), got.append, deadline=clock.now + 2.0)
    q.tick()
    assert len(got) == 1


def test_handler_exception_becomes_scene_query_failed_frame():
    import json

    from protocol import framing

    q, clock = make(handler=lambda r: (_ for _ in ()).throw(RuntimeError("boom")))
    got: list[bytes] = []
    q.submit(req("scene_summary"), got.append, deadline=clock.now + 2.0)
    q.tick()
    err = json.loads(framing.FrameBuffer().feed(got[0])[0])
    assert err["error"]["code"] == envelope.SCENE_QUERY_FAILED
    assert "RuntimeError" in err["error"]["message"]
    assert "boom" not in err["error"]["message"]


def test_capacity_overflow_raises():
    q, clock = make(capacity=2)
    q.submit(req(), lambda b: None, deadline=clock.now + 2.0)
    q.submit(req(), lambda b: None, deadline=clock.now + 2.0)
    with pytest.raises(QueueFull):
        q.submit(req(), lambda b: None, deadline=clock.now + 2.0)


def test_scene_summary_admission_bounds_64_request_flood_without_starving_quick_calls():
    q, clock = make(capacity=64)
    accepted = rejected = 0
    for _ in range(64):
        try:
            q.submit(req("scene_summary"), lambda _body: None,
                     deadline=clock.now + 2.0)
        except QueueFull:
            rejected += 1
        else:
            accepted += 1
    assert (accepted, rejected) == (MAX_SCENE_SUMMARY_TASKS,
                                    64 - MAX_SCENE_SUMMARY_TASKS)

    for index in range(64 - MAX_SCENE_SUMMARY_TASKS):
        method = "ping" if index % 2 == 0 else "status"
        q.submit(req(method), lambda _body: None, deadline=clock.now + 2.0)
    assert q.pending == 64


@pytest.mark.parametrize("release_path", ["complete", "deadline", "drain", "exception"])
def test_scene_summary_admission_releases_on_every_terminal_path(release_path):
    def fail(_request):
        raise RuntimeError("boom")

    handler = fail if release_path == "exception" else None
    q, clock = make(handler=handler)
    deadline = clock.now if release_path == "deadline" else clock.now + 2.0
    for _ in range(MAX_SCENE_SUMMARY_TASKS):
        q.submit(req("scene_summary"), lambda _body: None, deadline=deadline)
    with pytest.raises(QueueFull):
        q.submit(req("scene_summary"), lambda _body: None, deadline=clock.now + 2.0)

    if release_path == "drain":
        assert q.drain() == MAX_SCENE_SUMMARY_TASKS
    else:
        q.tick()
    for _ in range(MAX_SCENE_SUMMARY_TASKS):
        q.submit(req("scene_summary"), lambda _body: None, deadline=clock.now + 2.0)


def test_drain_clears_without_reply():
    q, clock = make()
    got: list[bytes] = []
    q.submit(req(), got.append, deadline=clock.now + 2.0)
    assert q.drain() == 1
    assert q.pending == 0 and got == []


class _RealClock:
    @staticmethod
    def monotonic() -> float:
        return time.monotonic()


class _SlowLargeSceneReader:
    """旧 Router 会走 snapshot() 并一次阻塞约 0.5s；新路径逐对象让出。"""

    def __init__(self, object_count: int = 200, step_s: float = 0.0025,
                 collection_count: int = 1_100_000) -> None:
        self.object_count = object_count
        self.step_s = step_s
        self.collections = tuple(f"C{i:07d}" for i in range(collection_count))
        self.sync_snapshot_called = False

    @staticmethod
    def blender_version() -> str:
        return "5.2.0"

    @staticmethod
    def status_info() -> tuple[None, int]:
        return (None, 0)

    def _result(self) -> SceneSnapshot:
        return SceneSnapshot(
            scene_revision=0, scene_hash="sha256:slow", scene_name="Large",
            scene_path=None, units_system="NONE", units_scale_length=1.0,
            object_count=self.object_count, mesh_count=self.object_count,
            camera_count=0, light_count=0, collections=self.collections,
        )

    def snapshot(self) -> SceneSnapshot:
        """仅用于证明旧同步实现会失败；新 Router 不得调用。"""
        self.sync_snapshot_called = True
        for _ in range(self.object_count):
            time.sleep(self.step_s)
        return self._result()

    def snapshot_steps(self, *, include_collections: bool = True,
                       include_managed_objects: bool = True
                       ) -> Generator[None, None, SceneSnapshot]:
        for _ in range(self.object_count):
            time.sleep(self.step_s)
            yield
        return self._result()


def test_scene_summary_large_scene_yields_before_tick_budget_wall_clock():
    reader = _SlowLargeSceneReader()
    router = Router(reader, BridgeMeta("gui-1-aa", 1, "0.1.0", "5.2.0"))
    q = TaskQueue(router.handle, _RealClock())
    got: list[bytes] = []
    request = req("scene_summary")
    deadline = time.monotonic() + 5.0
    q.submit(request, got.append, deadline=deadline)

    tick_durations: list[float] = []
    while not got and time.monotonic() < deadline:
        started = time.monotonic()
        q.tick(budget_ms=50)
        tick_durations.append(time.monotonic() - started)

    assert got
    assert len(tick_durations) > 1
    assert max(tick_durations) < 0.12
    assert reader.sync_snapshot_called is False
    assert q.pending == 0


def test_continuation_requeues_fairly_behind_quick_request():
    q, clock = make()
    replies: list[str] = []

    def steps(request: envelope.Request) -> Generator[None, None, bytes]:
        for _ in range(4):
            clock.now += 0.02
            yield
        return envelope.ok_frame(request.id, {})

    def handler(request: envelope.Request):
        return steps(request) if request.method == "scene_summary" \
            else envelope.ok_frame(request.id, {})

    q = TaskQueue(handler, clock)
    q.submit(req("scene_summary"), lambda _: replies.append("summary"), clock.now + 2.0)
    q.submit(req("ping"), lambda _: replies.append("ping"), clock.now + 2.0)
    q.tick(50)

    assert replies == ["ping"]
    assert q.pending == 1


def test_scene_summary_admission_is_not_recounted_when_continuation_requeues():
    q, clock = make()

    def steps(request: envelope.Request) -> Generator[None, None, bytes]:
        clock.now += 0.06
        yield
        clock.now += 0.06
        return envelope.ok_frame(request.id, {})

    q = TaskQueue(lambda request: steps(request), clock)
    for _ in range(MAX_SCENE_SUMMARY_TASKS):
        q.submit(req("scene_summary"), lambda _body: None, clock.now + 2.0)
    q.tick(50)
    with pytest.raises(QueueFull):
        q.submit(req("scene_summary"), lambda _body: None, clock.now + 2.0)

    q.tick(50)
    with pytest.raises(QueueFull):
        q.submit(req("scene_summary"), lambda _body: None, clock.now + 2.0)

    q.tick(50)
    q.submit(req("scene_summary"), lambda _body: None, clock.now + 2.0)
    with pytest.raises(QueueFull):
        q.submit(req("scene_summary"), lambda _body: None, clock.now + 2.0)


def test_drain_closes_started_continuation():
    q, clock = make()
    closed: list[bool] = []

    def steps(request: envelope.Request) -> Generator[None, None, bytes]:
        try:
            clock.now += 0.02
            yield
            return envelope.ok_frame(request.id, {})
        finally:
            closed.append(True)

    q = TaskQueue(lambda request: steps(request), clock)
    q.submit(req("scene_summary"), lambda _: None, clock.now + 2.0)
    q.tick(10)
    assert q.drain() == 1
    assert closed == [True]


def test_active_continuation_keeps_capacity_slot_during_concurrent_submit():
    clock = FakeClock()
    entered = threading.Event()
    release = threading.Event()

    def steps(request: envelope.Request) -> Generator[None, None, bytes]:
        entered.set()
        assert release.wait(2.0)
        clock.now += 0.1
        yield
        return envelope.ok_frame(request.id, {})

    q = TaskQueue(lambda request: steps(request), clock, capacity=1)
    q.submit(req("scene_summary"), lambda _: None, clock.now + 2.0)
    worker = threading.Thread(target=lambda: q.tick(50), daemon=True)
    worker.start()
    assert entered.wait(1.0)
    with pytest.raises(QueueFull):
        q.submit(req("ping"), lambda _: None, clock.now + 2.0)
    release.set()
    worker.join(timeout=2.0)

    assert not worker.is_alive()
    assert q.pending == 1


def test_continuation_exception_after_yield_is_structured_error():
    import json

    from protocol import framing

    q, clock = make()
    got: list[bytes] = []

    def steps(request: envelope.Request) -> Generator[None, None, bytes]:
        clock.now += 0.06
        yield
        raise SnapshotInvalidated("reloaded")

    q = TaskQueue(lambda request: steps(request), clock)
    q.submit(req("scene_summary"), got.append, clock.now + 2.0)
    q.tick(50)
    assert got == [] and q.pending == 1
    q.tick(50)

    body = json.loads(framing.FrameBuffer().feed(got[0])[0])
    assert body["error"]["code"] == envelope.SCENE_QUERY_FAILED
    assert body["error"]["message"] == "SnapshotInvalidated"


def test_new_continuation_rechecks_budget_and_deadline_before_first_step():
    q, clock = make()
    got: list[bytes] = []
    advanced: list[bool] = []

    def steps(request: envelope.Request) -> Generator[None, None, bytes]:
        advanced.append(True)
        yield
        return envelope.ok_frame(request.id, {})

    def consumes_budget(request: envelope.Request) -> Generator[None, None, bytes]:
        clock.now += 0.06
        return steps(request)

    q = TaskQueue(consumes_budget, clock)
    q.submit(req("scene_summary"), got.append, clock.now + 2.0)
    q.tick(50)
    assert advanced == [] and q.pending == 1
    assert q.drain() == 1

    clock = FakeClock()
    advanced = []

    def passes_deadline(request: envelope.Request) -> Generator[None, None, bytes]:
        clock.now += 3.0
        return steps(request)

    q = TaskQueue(passes_deadline, clock)
    q.submit(req("scene_summary"), got.append, clock.now + 1.0)
    q.tick(50)
    assert advanced == [] and got == [] and q.pending == 0
