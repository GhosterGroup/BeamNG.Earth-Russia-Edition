#!/usr/bin/env python3
"""Offline generation-queue pressure measurements; never claims to measure in-game performance.

Run this SAME tool against original/modified source via --source-root, in fresh processes:
  python tools/benchmark_queues.py --source-root ../baseline-v1.7.0-beta --output baseline.json
  python tools/benchmark_queues.py --output optimized.json
Prefetch forces two threads (stock prefetch is off on <=8 CPU threads). No downloads or disk-cache deletion.
"""
import argparse
import asyncio
import importlib.util
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import tempfile
import threading
import time
import tracemalloc
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('benchmark_memstats', ROOT / 'server' / 'memstats.py')
memory = importlib.util.module_from_spec(spec)
spec.loader.exec_module(memory)


def point(**fields):
    current, peak = tracemalloc.get_traced_memory()
    return dict(fields, traced_bytes=current, traced_peak_bytes=peak,
                **{k: v for k, v in memory.process_memory(os.getpid()).items() if k != 'pid'})


def warm():
    import mapdata
    import mapcells
    gate = threading.Event()
    entered = threading.Event()
    def read(*_):
        entered.set()
        gate.wait(60)
    with tempfile.TemporaryDirectory() as d, mock.patch.object(mapdata, 'WARM_THREADS', 2):
        md = mapdata.MapData(d)
        md.has, md.layer_arrays = lambda *_: False, read
        rows = []
        tracemalloc.start(1)
        previous = 0
        try:
            for total in (0, 1000, 5000, 10000):
                started = time.perf_counter()
                queued = md.warm((mapcells.CellKey(14, i % 16384, i // 16384), 'roads')
                                 for i in range(previous, total))
                rows.append(point(requested_total=total, warming=len(md._warming), newly_queued=queued,
                                  enqueue_seconds=time.perf_counter() - started))
                previous = total
        finally:
            # Close while the read is blocked, exercising cancellation bookkeeping too.
            md.close()
            gate.set()
            md._warm_ex.shutdown(wait=True, cancel_futures=True)
        return dict(rows=rows, warming_after_close=len(md._warming), forced_prefetch_threads=2)


async def tracker(kind):
    import roads
    import vegetation
    workers = roads.BUILD_PER_POSE if kind == 'roads' else 2
    tr = roads.Tracker() if kind == 'roads' else vegetation.Tracker(send_m=256, per_pose=workers, kind=kind)
    gate, entered = threading.Event(), threading.Event()
    lock = threading.Lock()
    active = 0
    messages = []
    def build(aid, tx, ty):
        nonlocal active
        with lock:
            active += 1
            if active == workers:
                entered.set()
        gate.wait(60)
        return f'/fake/{aid}/{tx}/{ty}', 1
    conn = SimpleNamespace(send=messages.append)
    loop = asyncio.get_running_loop()
    # Warm up geographic imports before tracing. No data service or game is involved.
    roads.view_key(conn, 1, 128, 128)
    rows = []
    tracemalloc.start(1)
    try:
        for i in range(1001):
            if i:
                tr.on_pose(conn, i, 128, 128, loop, build)
                await asyncio.sleep(0)
                if i == 1:
                    if not await asyncio.to_thread(entered.wait, 5):
                        raise RuntimeError('builders did not enter the controlled wait')
            if i in (0, 10, 100, 1000):
                q = tr.pool.snapshot()['queued'] if tr.pool and hasattr(tr.pool, 'snapshot') else (
                    tr.pool._work_queue.qsize() if tr.pool else 0)
                rows.append(point(anchor_changes=i, pending_records=q))
        release = time.perf_counter()
        gate.set()
        await asyncio.to_thread(tr.pool.shutdown, True)
        for _ in range(5):
            await asyncio.sleep(0)
        return dict(rows=rows, worker_limit=workers, latest_anchor=1000,
                    delivered_anchor_ids=sorted({m['anchorId'] for m in messages}),
                    release_to_drained_seconds=time.perf_counter() - release)
    finally:
        gate.set()
        tr.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source-root', type=Path, default=ROOT)
    ap.add_argument('--output', type=Path)
    ap.add_argument('--repeats', type=int, default=3)
    ap.add_argument('--scenario', choices=('mapdata', 'roads', 'veg', 'bldfar'))
    args = ap.parse_args()
    sys.path.insert(0, str(args.source_root.resolve() / 'server'))
    if args.scenario:
        result = warm() if args.scenario == 'mapdata' else asyncio.run(tracker(args.scenario))
        print(json.dumps(result))
        return
    if args.repeats < 1:
        ap.error('repeats must be positive')
    results = {}
    for name in ('mapdata', 'roads', 'veg', 'bldfar'):
        runs = []
        for _ in range(args.repeats):
            p = subprocess.run([sys.executable, '-B', str(Path(__file__).resolve()), '--source-root',
                                str(args.source_root.resolve()), '--scenario', name],
                               capture_output=True, text=True, timeout=90)
            if p.returncode:
                raise RuntimeError(p.stderr)
            runs.append(json.loads(p.stdout))
        results[name] = dict(runs=runs, median_final_traced_bytes=statistics.median(
            r['rows'][-1]['traced_bytes'] for r in runs), median_final_rss_bytes=statistics.median(
            r['rows'][-1]['rss_bytes'] for r in runs), max_pending_or_warming=max(
            r['rows'][-1].get('pending_records', r['rows'][-1].get('warming')) for r in runs))
    out = dict(source_version=(args.source_root / 'VERSION').read_text().strip(),
               python=platform.python_version(), platform=platform.platform(), logical_cpus=os.cpu_count(),
               system=memory.system_memory(), repeats=args.repeats,
               limitations=['Synthetic offline blocked-reader workload, not an in-game drive.',
                            'RSS includes tracer overhead; shared pages may be counted more than once.',
                            'No FPS, game RAM, cache-hit performance or BeamMP play test measured.'],
               scenarios=results)
    data = json.dumps(out, indent=2)
    if args.output:
        args.output.write_text(data, encoding='utf-8')
    else:
        print(data)


if __name__ == '__main__':
    main()
