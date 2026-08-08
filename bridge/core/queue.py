"""主线程任务队列：deadline、cooperative continuation、reply 失败隔离。

budget 在 handler/continuation step 之间检查；Python 无法抢占正在执行的单个 step。
因此可能超预算的主线程工作必须拆成 ResponseSteps，且每个 step 自身应当很小。
"""
from __future__ import annotations

import logging
import threading
from collections import deque
from collections.abc import Callable, Generator
from dataclasses import dataclass

from ._proto import envelope
from .contracts import Clock

# 往返延迟几乎全部是「等下一次 tick」，不是代码效率问题。本机预检（Apple M4）：
# IDLE=0.1 时 p50 约 60 ms，IDLE=0.02 时 p50 约 12 ms；代价是空转唤醒约增 4.4×。
# CPU/电量影响依 workload 与电源状态而变，不能从一次空队列样本外推电池结论。
# 更省电的迟滞方案已否决——见 docs/measurements/2026-08-07-macos-platform-optimization.md §3.1。
IDLE_INTERVAL = 0.02
BUSY_INTERVAL = 0.01
MAX_SCENE_SUMMARY_TASKS = 2
ResponseSteps = Generator[None, None, bytes]


class QueueFull(Exception):
    pass


@dataclass(frozen=True)
class _Task:
    request: envelope.Request
    reply: Callable[[bytes], None]
    deadline: float
    continuation: ResponseSteps | None = None


class TaskQueue:
    def __init__(self, handler: Callable[[envelope.Request], bytes | ResponseSteps], clock: Clock,
                 capacity: int = 64, diag: logging.Logger | None = None) -> None:
        self._handler = handler
        self._clock = clock
        self._capacity = capacity
        self._diag = diag or logging.getLogger("bcx.bridge")
        self._lock = threading.Lock()
        self._tasks: deque[_Task] = deque()
        self._active = 0
        self._scene_summaries = 0

    @property
    def pending(self) -> int:
        with self._lock:
            return len(self._tasks) + self._active

    def submit(self, request: envelope.Request, reply: Callable[[bytes], None],
               deadline: float) -> None:
        with self._lock:
            if len(self._tasks) + self._active >= self._capacity:
                raise QueueFull(request.id)
            if (request.method == "scene_summary"
                    and self._scene_summaries >= MAX_SCENE_SUMMARY_TASKS):
                raise QueueFull(request.id)
            self._tasks.append(_Task(request, reply, deadline))
            if request.method == "scene_summary":
                self._scene_summaries += 1

    def drain(self) -> int:
        with self._lock:
            tasks = list(self._tasks)
            self._tasks.clear()
            self._scene_summaries -= sum(
                task.request.method == "scene_summary" for task in tasks)
        for task in tasks:
            if task.continuation is not None:
                self._close_continuation(task.request.id, task.continuation)
        return len(tasks)

    def _close_continuation(self, request_id: str, continuation: ResponseSteps) -> None:
        try:
            continuation.close()
        except Exception:
            self._diag.exception("continuation close failed for %s", request_id)

    def _complete_active(self, task: _Task) -> None:
        with self._lock:
            self._active -= 1
            if task.request.method == "scene_summary":
                self._scene_summaries -= 1

    def tick(self, budget_ms: int = 50) -> float:
        end = self._clock.monotonic() + budget_ms / 1000.0
        while self._clock.monotonic() < end:
            with self._lock:
                if not self._tasks:
                    return IDLE_INTERVAL
                task = self._tasks.popleft()
                self._active += 1
            if self._clock.monotonic() >= task.deadline:
                self._diag.info("drop expired request %s", task.request.id)
                if task.continuation is not None:
                    self._close_continuation(task.request.id, task.continuation)
                self._complete_active(task)
                continue
            continuation = task.continuation
            try:
                result: bytes | ResponseSteps = (
                    self._handler(task.request) if continuation is None else continuation
                )
                if isinstance(result, bytes):
                    frame = result
                else:
                    continuation = result
                    if self._clock.monotonic() >= task.deadline:
                        self._diag.info("drop expired continuation %s", task.request.id)
                        self._close_continuation(task.request.id, continuation)
                        self._complete_active(task)
                        continue
                    if self._clock.monotonic() >= end:
                        with self._lock:
                            self._tasks.append(_Task(task.request, task.reply, task.deadline,
                                                     continuation))
                            self._active -= 1
                        return BUSY_INTERVAL
                    try:
                        next(continuation)
                    except StopIteration as done:
                        if not isinstance(done.value, bytes):
                            raise TypeError("continuation must return bytes")
                        frame = done.value
                    else:
                        with self._lock:
                            self._tasks.append(_Task(task.request, task.reply, task.deadline,
                                                     continuation))
                            self._active -= 1
                        continue
            except Exception as e:
                self._diag.exception("handler failed for %s", task.request.id)
                if continuation is not None:
                    self._close_continuation(task.request.id, continuation)
                frame = envelope.error_frame(task.request.id, envelope.SCENE_QUERY_FAILED,
                                             type(e).__name__)
            if self._clock.monotonic() >= task.deadline:
                self._diag.info("drop late response %s", task.request.id)
                self._complete_active(task)
                continue
            try:
                task.reply(frame)
            except Exception:
                self._diag.info("reply failed for %s (peer gone)", task.request.id)
            finally:
                self._complete_active(task)
        return BUSY_INTERVAL if self.pending else IDLE_INTERVAL
