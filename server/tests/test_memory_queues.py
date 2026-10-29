"""Generation scheduling under teleport churn; uses real blocked threads, never the network."""
import asyncio
import os
import sys
import tempfile
import threading
import unittest
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import mapcells
import mapdata
import roads
import vegetation


class TrackerPressureTest(unittest.IsolatedAsyncioTestCase):
    async def check_tracker(self, tracker):
        gate = threading.Event()
        started = threading.Event()
        messages = []
        conn = SimpleNamespace(send=messages.append)
        def build(aid, tx, ty):
            started.set()
            gate.wait(10)
            return f'/tile/{aid}/{tx}/{ty}', 1
        loop = asyncio.get_running_loop()
        try:
            tracker.on_pose(conn, 1, 128, 128, loop, build)
            self.assertTrue(await asyncio.to_thread(started.wait, 5))
            for aid in range(2, 102):
                tracker.on_pose(conn, aid, 128, 128, loop, build)
                await asyncio.sleep(0)
            state = tracker.pool.snapshot()
            self.assertLessEqual(state['queued'], state['capacity'])
            self.assertLessEqual(state['running'], state['workers'])
            gate.set()
            await asyncio.to_thread(tracker.pool.shutdown, True)
            for _ in range(5):
                await asyncio.sleep(0)
            self.assertTrue(messages)
            self.assertTrue(all(m['anchorId'] == 101 for m in messages))
        finally:
            gate.set()
            tracker.close()

    async def test_vegetation_and_far_buildings_keep_a_bounded_backlog(self):
        await self.check_tracker(vegetation.Tracker(send_m=256, per_pose=2))

    async def test_roads_keep_a_bounded_backlog_after_anchor_changes(self):
        await self.check_tracker(roads.Tracker())


class WarmPressureTest(unittest.TestCase):
    def test_blocked_prefetch_has_a_bound_and_close_clears_accounting(self):
        gate, entered = threading.Event(), threading.Event()
        with tempfile.TemporaryDirectory() as d, mock.patch.object(mapdata, 'WARM_THREADS', 2):
            md = mapdata.MapData(d)
            md.has = lambda *_: False
            def read(*_):
                entered.set()
                gate.wait(10)
            md.layer_arrays = read
            try:
                n = md.warm((mapcells.CellKey(14, i, 0), 'roads') for i in range(1000))
                self.assertLessEqual(n, 4, 'two waves, running plus waiting')
                self.assertTrue(entered.wait(5))
                self.assertLessEqual(len(md._warming), 4)
                md.close()
                gate.set()
                md._warm_ex.shutdown(wait=True, cancel_futures=True)
                self.assertEqual(md._warming, set())
                self.assertEqual(md.warm([(mapcells.CellKey(14, 1001, 0), 'roads')]), 0)
            finally:
                gate.set()
                md.close()


if __name__ == '__main__':
    unittest.main()
