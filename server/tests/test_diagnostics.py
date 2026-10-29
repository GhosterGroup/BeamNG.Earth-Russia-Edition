import asyncio
import json
import os
import sys
import threading
import unittest
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import diagnostics
import workqueue


class RuntimeTest(unittest.TestCase):
    def test_queue_and_cache_counts_have_explicit_scope(self):
        pool = workqueue.BoundedExecutor(1, 1)
        try:
            md = SimpleNamespace(_mem_lock=threading.Lock(), _mem_bytes=123, _warming={'one'}, _mem={'a': 1})
            tracker = SimpleNamespace(pool=pool, sent={'one', 'two'})
            server = SimpleNamespace(mapdata=md, connections=[SimpleNamespace(roads=tracker)],
                                     tiles={'one': 1}, hm={'two': 2}, anchors={1: None},
                                     tile_inflight={}, hm_inflight={}, dem=SimpleNamespace(_lru={}), imagery=None)
            got = diagnostics.runtime_snapshot(server)
            self.assertEqual(got['main_mapdata_cache_bytes'], 123)
            self.assertEqual(got['main_mapdata_prefetch_tasks'], 1)
            self.assertEqual(got['loaded_far_tiles'], 1)
            self.assertEqual(got['trackers'][0]['loaded_tiles'], 2)
            self.assertEqual(got['trackers'][0]['queue']['workers'], 1)
            json.dumps(got)
        finally:
            pool.shutdown()


class LoggingTest(unittest.IsolatedAsyncioTestCase):
    async def test_os_sampler_runs_off_loop_and_logs_json(self):
        done = asyncio.Event()
        rows = []
        class Log:
            def info(self, fmt, data):
                rows.append(json.loads(data))
                done.set()
        threads = []
        def collect():
            threads.append(threading.get_ident())
            return {'server_rss_bytes': 500}
        with mock.patch.object(diagnostics.memstats, 'collect', side_effect=collect):
            task = asyncio.create_task(diagnostics.log_loop(SimpleNamespace(connections=[]), Log()))
            try:
                await asyncio.wait_for(done.wait(), 5)
            finally:
                task.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await task
        self.assertEqual(rows[0]['server_rss_bytes'], 500)
        self.assertNotEqual(threads[0], threading.get_ident())


if __name__ == '__main__':
    unittest.main()
