"""Small nonblocking executors for replaceable background work.

ThreadPoolExecutor keeps cancelled work items in its unbounded queue until a worker dequeues them.
Here cancellation removes the pending record immediately. Running jobs are never interrupted: their
current road/collision data and disk writes can finish safely, within the original worker ceiling.
"""
from collections import deque
from concurrent.futures import Executor, Future
import threading


class QueueFull(RuntimeError):
    """No pending slot: the caller may retry on its next pose, never block the game loop."""


class BoundedExecutor(Executor):
    def __init__(self, max_workers, max_pending, thread_name_prefix='bounded'):
        if max_workers < 1 or max_pending < 1:
            raise ValueError('workers and pending capacity must be positive')
        self._workers, self._capacity = max_workers, max_pending
        self._cv = threading.Condition()
        self._pending = deque()
        self._waiting = set()      # includes records detached by retain/shutdown until cancel() notifies
        self._running = self._completed = self._cancelled = self._rejected = 0
        self._closed = False
        self._threads = [threading.Thread(target=self._run, name=f'{thread_name_prefix}_{i}', daemon=True)
                         for i in range(max_workers)]
        for thread in self._threads:
            thread.start()

    def submit(self, fn, /, *args, **kwargs):
        with self._cv:
            if self._closed:
                raise RuntimeError('cannot schedule new futures after shutdown')
            if len(self._pending) >= self._capacity:
                self._rejected += 1
                raise QueueFull('background queue full')
            future = Future()
            future.add_done_callback(self._discard_cancelled)
            self._pending.append((future, fn, args, kwargs))
            self._waiting.add(future)
            self._cv.notify()
            return future

    def _discard_cancelled(self, future):
        if future.cancelled():
            with self._cv:
                self._pending = deque(item for item in self._pending if item[0] is not future)
                if future in self._waiting:
                    self._waiting.remove(future)
                    # No worker will dequeue this record now. Notify wait()/as_completed() here,
                    # exactly once; a worker that already took it owns that transition instead.
                    future.set_running_or_notify_cancel()
                self._cancelled += 1

    def retain(self, predicate):
        """Keep waiting jobs for which predicate(fn, args, kwargs) is true. Running jobs keep going.
        Cancel outside the condition: Future callbacks may call this executor or the caller's locks."""
        with self._cv:
            keep, drop = deque(), []
            for item in self._pending:
                (keep if predicate(*item[1:]) else drop).append(item)
            self._pending = keep
        for future, *_ in drop:
            future.cancel()
        return len(drop)

    def snapshot(self):
        with self._cv:
            return dict(workers=self._workers, capacity=self._capacity, running=self._running,
                        queued=len(self._pending), completed=self._completed, cancelled=self._cancelled,
                        rejected=self._rejected)

    def _run(self):
        while True:
            with self._cv:
                self._cv.wait_for(lambda: self._pending or self._closed)
                if not self._pending:
                    return
                future, fn, args, kwargs = self._pending.popleft()
                self._waiting.remove(future)
                if not future.set_running_or_notify_cancel():
                    continue
                self._running += 1
            try:
                result = fn(*args, **kwargs)
            except BaseException as exc:
                future.set_exception(exc)
            else:
                future.set_result(result)
            finally:
                with self._cv:
                    self._running -= 1
                    self._completed += 1
                # A parked worker must not retain its last tile's arrays, traceback or callable.
                future = fn = args = kwargs = result = None

    def shutdown(self, wait=True, *, cancel_futures=False):
        with self._cv:
            self._closed = True
            drop = list(self._pending) if cancel_futures else []
            if cancel_futures:
                self._pending.clear()
            self._cv.notify_all()
        for future, *_ in drop:
            future.cancel()
        if wait:
            for thread in self._threads:
                if thread is not threading.current_thread():
                    thread.join()
