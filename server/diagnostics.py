"""Opt-in diagnostics, separate from the multiplayer/world protocol.

BNGE_MEMORY_DIAGNOSTICS=1 logs native process-tree readings and main-process cache/queue counters.
Cache bytes here are the mapdata LRU's accounting, not an estimate of all Python/native allocations.
"""
import asyncio
import json

import memstats


def runtime_snapshot(server):
    trackers = []
    for i, conn in enumerate(server.connections):
        for name in ('roads', 'veg', 'bldfar', 'bldsky', 'brfar'):
            tracker = getattr(conn, name, None)
            if tracker is None:
                continue
            pool = tracker.pool
            trackers.append(dict(connection=i, kind=name, loaded_tiles=len(tracker.sent),
                                 queue=pool.snapshot() if pool is not None else None))
    out = dict(trackers=trackers, connections=len(server.connections))
    for label, attr in (('loaded_far_tiles', 'tiles'), ('heightmaps_kept', 'hm'), ('anchors_kept', 'anchors'),
                        ('far_tasks_inflight', 'tile_inflight'), ('heightmap_tasks_inflight', 'hm_inflight')):
        out[label] = len(getattr(server, attr, ()))
    md = getattr(server, 'mapdata', None)
    if md is not None:
        with md._mem_lock:
            out.update(main_mapdata_cache_bytes=md._mem_bytes, main_mapdata_cache_layers=len(md._mem))
        out['main_mapdata_prefetch_tasks'] = len(md._warming)
    else:
        out.update(main_mapdata_cache_bytes=0, main_mapdata_cache_layers=0, main_mapdata_prefetch_tasks=0)
    for name in ('dem', 'imagery'):
        reader = getattr(server, name, None)
        out[f'main_{name}_cache_tiles'] = len(reader._lru) if reader is not None else 0
    return out


async def log_loop(server, log, interval=10.0):
    while True:
        try:
            # Process enumeration/OS calls must never stall pose handling or nearby road dispatch.
            memory = await asyncio.get_running_loop().run_in_executor(None, memstats.collect)
            memory['runtime'] = runtime_snapshot(server)
            log.info('memory diagnostics: %s', json.dumps(memory, separators=(',', ':')))
        except (OSError, ValueError) as exc:
            log.warning('memory diagnostics unavailable: %s', exc)
        await asyncio.sleep(interval)
