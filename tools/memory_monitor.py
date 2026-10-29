#!/usr/bin/env python3
"""Record server tree, game and physical RAM as JSONL, without starting or changing the game.

python tools/memory_monitor.py --server-pid 1234 --samples 240 --interval 5 --output run.jsonl
No game PID: find BeamNG.drive processes by executable name. Use --game-pid for an explicit root.
"""
import argparse
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'server'))
import memstats


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--server-pid', type=int, required=True)
    ap.add_argument('--game-pid', type=int)
    ap.add_argument('--samples', type=int, default=240)
    ap.add_argument('--interval', type=float, default=5.0)
    ap.add_argument('--output', type=Path)
    args = ap.parse_args()
    if args.server_pid <= 0 or (args.game_pid is not None and args.game_pid <= 0):
        ap.error('PIDs must be positive')
    if args.samples < 1 or not 0.1 <= args.interval <= 3600:
        ap.error('samples >= 1 and interval between 0.1 and 3600 seconds required')
    stream = args.output.open('w', encoding='utf-8') if args.output else sys.stdout
    peak_server = peak_game = 0
    try:
        for i in range(args.samples):
            start = time.monotonic()
            data = memstats.collect(args.server_pid, args.game_pid)
            peak_server = max(peak_server, data['server_rss_bytes'] or 0)
            peak_game = max(peak_game, data['game_rss_bytes'] or 0)
            data['sampled_server_peak_rss_bytes'] = peak_server or None
            data['sampled_game_peak_rss_bytes'] = peak_game or None
            print(json.dumps(data, separators=(',', ':')), file=stream, flush=True)
            if i + 1 < args.samples:
                time.sleep(max(0, args.interval - (time.monotonic() - start)))
    except KeyboardInterrupt:
        pass
    finally:
        if args.output:
            stream.close()


if __name__ == '__main__':
    main()
