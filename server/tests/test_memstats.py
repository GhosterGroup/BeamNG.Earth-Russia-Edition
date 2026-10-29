"""OS memory readings and tree accounting: missing readings are not zero."""
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import memstats


class MemoryStatsTest(unittest.TestCase):
    def test_live_current_process_has_nonzero_rss(self):
        got = memstats.process_memory(os.getpid())
        self.assertGreater(got['rss_bytes'], 0)
        self.assertGreaterEqual(got['peak_rss_bytes'], got['rss_bytes'])

    def test_unreadable_process_is_unknown(self):
        got = memstats.process_memory(2147483647)
        self.assertIsNone(got['rss_bytes'])
        self.assertTrue(got['error'])

    def test_server_tree_excludes_unrelated_process_and_game(self):
        processes = [{'pid': p, 'ppid': parent, 'name': name} for p, parent, name in
                     [(10, 1, 'earthd'), (11, 10, 'python'), (12, 11, 'python'),
                      (20, 10, 'BeamNG.drive.x64.exe'), (21, 20, 'game-child'), (30, 1, 'other')]]
        with mock.patch.object(memstats, 'processes', return_value=processes), \
                mock.patch.object(memstats, 'system_memory', return_value={}), \
                mock.patch.object(memstats, 'process_memory', side_effect=lambda p: {
                    'pid': p, 'rss_bytes': p * 100, 'peak_rss_bytes': p * 200,
                    'private_commit_bytes': p * 50, 'error': None}):
            got = memstats.collect(10, 20)
        self.assertEqual(got['server_rss_bytes'], 3300)
        self.assertEqual(got['server_private_commit_bytes'], 1650)
        self.assertEqual(got['game_rss_bytes'], 4100)
        self.assertEqual(got['server_process_count'], 3)

    def test_partial_readings_are_labelled_and_missing_root_is_unknown(self):
        procs = [{'pid': 10, 'ppid': 1, 'name': 'earthd'}, {'pid': 11, 'ppid': 10, 'name': 'python'}]
        def memory(p):
            return {'pid': p, 'rss_bytes': 100 if p == 10 else None, 'peak_rss_bytes': None,
                    'private_commit_bytes': None, 'error': None if p == 10 else 'access denied'}
        with mock.patch.object(memstats, 'processes', return_value=procs), \
                mock.patch.object(memstats, 'system_memory', return_value={}), \
                mock.patch.object(memstats, 'process_memory', side_effect=memory):
            got = memstats.collect(10)
            missing = memstats.collect(99)
        self.assertTrue(got['server_incomplete'])
        self.assertEqual(got['server_rss_bytes'], 100)
        self.assertIsNone(missing['server_rss_bytes'])
        self.assertIsNone(got['game_rss_bytes'])

    def test_live_system_memory_and_process_listing(self):
        system = memstats.system_memory()
        self.assertGreater(system['physical_total_bytes'], 0)
        self.assertGreaterEqual(system['physical_available_bytes'], 0)
        self.assertLessEqual(system['physical_available_bytes'], system['physical_total_bytes'])
        self.assertIn(os.getpid(), {p['pid'] for p in memstats.processes()})

    def test_cli_emits_json_and_exits_after_requested_samples(self):
        tool = Path(__file__).resolve().parents[2] / 'tools' / 'memory_monitor.py'
        r = subprocess.run([sys.executable, '-B', str(tool), '--server-pid', str(os.getpid()), '--samples', '1'],
                           capture_output=True, text=True, timeout=15)
        self.assertEqual(r.returncode, 0, r.stderr)
        got = json.loads(r.stdout)
        self.assertGreater(got['server_rss_bytes'], 0)
        self.assertEqual(got['server_pid'], os.getpid())


if __name__ == '__main__':
    unittest.main()
