"""Pending work is physically bounded, including cancelled tasks behind a blocked builder."""
import os
import sys
import threading
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import workqueue


class QueueTest(unittest.TestCase):
    def setUp(self):
        self.gate = threading.Event()
        self.entered = threading.Event()
        self.pool = workqueue.BoundedExecutor(1, 2, 'test-bounded')

    def tearDown(self):
        self.gate.set()
        self.pool.shutdown(wait=True, cancel_futures=True)

    def block(self):
        self.entered.set()
        self.gate.wait(10)

    def occupy(self):
        self.pool.submit(self.block)
        self.assertTrue(self.entered.wait(5))

    def test_capacity_does_not_block_producer(self):
        self.occupy()
        a = self.pool.submit(abs, -1)
        b = self.pool.submit(abs, -2)
        with self.assertRaises(workqueue.QueueFull):
            self.pool.submit(abs, -3)
        self.assertEqual(self.pool.snapshot()['queued'], 2)
        self.gate.set()
        self.assertEqual((a.result(5), b.result(5)), (1, 2))

    def test_retain_physically_removes_obsolete_tasks(self):
        self.occupy()
        old = self.pool.submit(abs, -1)
        current = self.pool.submit(abs, -2)
        self.assertEqual(self.pool.retain(lambda fn, args, kw: args == (-2,)), 1)
        self.assertTrue(old.cancelled())
        self.assertFalse(current.cancelled())
        self.assertEqual(self.pool.snapshot()['queued'], 1)
        for _ in range(1000):
            f = self.pool.submit(abs, -3)
            f.cancel()
        self.assertLessEqual(self.pool.snapshot()['queued'], 2)

    def test_latest_work_runs_after_current_job_without_old_backlog(self):
        self.occupy()
        ran = []
        for i in range(100):
            self.pool.retain(lambda *_: False)
            latest = self.pool.submit(ran.append, i)
        self.gate.set()
        latest.result(5)
        self.assertEqual(ran, [99])

    def test_fifo_and_exception_propagation(self):
        self.occupy()
        ran = []
        a = self.pool.submit(ran.append, 1)
        b = self.pool.submit(ran.append, 2)
        self.gate.set()
        a.result(5), b.result(5)
        self.assertEqual(ran, [1, 2])
        with self.assertRaises(ZeroDivisionError):
            self.pool.submit(lambda: 1 / 0).result(5)

    def test_shutdown_cancels_pending_and_rejects_new_work(self):
        self.occupy()
        f = self.pool.submit(abs, -1)
        self.pool.shutdown(wait=False, cancel_futures=True)
        self.assertTrue(f.cancelled())
        self.assertEqual(self.pool.snapshot()['queued'], 0)
        with self.assertRaises(RuntimeError):
            self.pool.submit(abs, -2)

    def test_reentrant_cancel_callback_does_not_deadlock(self):
        self.occupy()
        f = self.pool.submit(abs, -1)
        seen = []
        f.add_done_callback(lambda _: seen.append(self.pool.snapshot()['queued']))
        self.pool.retain(lambda *_: False)
        self.assertEqual(seen, [0])


if __name__ == '__main__':
    unittest.main()
