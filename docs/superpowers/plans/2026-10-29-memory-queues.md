# Russia Edition memory queues implementation plan

> **For agentic workers:** Use superpowers:executing-plans to implement task-by-task.

**Goal:** Bound obsolete generation work and measure Windows memory without delaying active road builders.

**Architecture:** Keep the original process pools, CPU rules, road priorities, collision retention and disk caches.
Replace the tile trackers' unbounded thread queues with a physically bounded pending deque. Running jobs finish;
pending jobs outside the current view/anchor are removed. Bound map-data prefetch separately. Add native OS memory
sampling, periodic server diagnostics, and repeatable offline pressure experiments.

**Tech Stack:** Python 3.10+, standard library ctypes/concurrent.futures/threading/asyncio; existing numpy/Pillow.

**Spec:** User's Russia Edition specification, stage 1; 2026-10-29 refinement: queues, cancellation and diagnostics
first; independent technical decisions authorized. Winter/regions/quality UI remain subsequent stages.

## Global constraints

- Base `v1.7.0-beta`, branch `feature/russia-edition`, origin GhosterGroup fork only.
- 16 GB Windows / i3-10100F first. No extra mandatory dependencies.
- Preserve nearest-road worker counts, priorities and collision foci; do not clear useful disk caches.
- Preserve protocol 4 and BeamMP world-generation output.
- Distinguish synthetic queue measurements from actual in-game performance and report unavailable checks.

## Component map

- `server/earthd.py`: per-lane physics/road/far process pools, connection trackers, status/logging.
- `server/roads.py`, `server/vegetation.py`: per-connection trackers; vegetation tracker also streams distant buildings.
- `server/mapdata.py`: decoded-layer LRU, disk mirrors, optional parallel prefetch.
- `server/budget.py`: existing <20 GB small-machine profile; retain initial budgets until game measurements justify changes.
- `server/cache.py`, `server/terraincache.py`: existing download LRU and packed game textures; no cache format changes.
- `server/blockworker.py`: per-process state and memory log; Windows RSS currently reports zero.
- `mod/.../trees.lua`, `groundcover.lua`, `weather.lua`, `settings.lua`: later regional winter and settings integration.
- `native/earthfast`, `beammp`, `tools/package.py`: native generation and distribution; preserve output/protocol.

## Review focus

- Repeated anchor changes while workers block: actual pending records stay bounded, latest view wins.
- Running jobs cannot be killed safely: keep worker ceiling across anchors and ignore obsolete results.
- Camera and remote vehicles: keep their requested collision tiles.
- Shutdown/cancellation races: no orphan accounting or callbacks deleting replacement jobs.
- Windows process access errors: report unknown/null, never mislabel failures as zero usage.

## Task 1: Bounded generation queues

Files: new `server/workqueue.py`, `server/tests/test_workqueue.py`, `server/tests/test_memory_queues.py`;
modify `server/roads.py`, `server/vegetation.py`, `server/mapdata.py`.

- [ ] Write failing behavioral tests for capacity, physical removal, FIFO priority, cancellation, shutdown and tracker teleport churn.
- [ ] Run targeted unittest modules and observe failure.
- [ ] Implement `BoundedExecutor(max_workers, max_pending, thread_name_prefix)`, `retain(predicate)` and `snapshot()`;
  use a condition and fixed workers, remove pending work physically, never interrupt running jobs.
- [ ] Keep at most one worker-wave waiting per tracker; retain car/camera/other-vehicle work on each pose.
- [ ] Limit prefetch to two worker-waves (running plus waiting); completion callbacks clear accounting even on cancellation.
- [ ] Run queue/road/vegetation/mapdata regression tests and repeat pressure measurements; commit.

## Task 2: Real memory diagnostics

Files: new `server/memstats.py`, `tools/memory_monitor.py`, tests; modify worker RSS and earthd logging.

- [x] Write failing tests for current-process RSS, child-tree aggregation, PID/access failure handling and JSON CLI output.
- [x] Implement Windows Toolhelp32 + GetProcessMemoryInfo + GlobalMemoryStatusEx, Linux /proc fallback.
- [x] Report server tree and game separately; RSS sums explicitly include shared-page double counting; private commit separate.
- [x] Expose periodic opt-in diagnostics with process/queue/tile/cache counts; monitor accepts explicit server/game PIDs.
- [x] Run live OS sampler plus unit/integration/protocol regressions; commit.

## Task 3: Reproducible evidence and manual game checks

Files: benchmark tool, `docs/RUSSIA_EDITION_MEMORY.md`, portable JSON measurements and test results.

- [x] Run the same isolated benchmark against baseline and modified source, with worker limits held constant.
- [x] Record hardware, versions, scenario, tracemalloc, RSS, peak, pending jobs and limitations.
- [x] Run available full suite with bounded parallelism/timeouts; report all skips/failures.
- [x] Document memory/FPS, cold/warm disk cache, 20-minute route, teleport, slow network and BeamMP checks; game execution remains unverified.
- [x] Review changes, run diff checks, commit evidence; show branch/status/main refs.

## Baseline evidence

Host: i3-10100F, 4C/8T, 17,072,508,928 physical bytes. BeamNG not running.
Original 67 selected tests: OK, 33 skips (DuckDB/fsspec unavailable).
Blocked optional map prefetch (forced 2 threads): 10,000 jobs, 21,136,465 traced bytes, RSS 46,653,440 -> 89,604,096;
6,609 stale `_warming` entries after close. This prefetch is disabled by default on <=8 CPU threads.
Blocked vegetation tracker (2 workers), 1,000 anchor changes: 1,998 pending executor records, 6,835,586 traced bytes.
These are synthetic reproductions, not proof of in-game RAM/FPS improvement or a general leak fix.


## Results (2026-10-29)

See docs/benchmarks/Russia-Edition-stage1-memory-report.md and adjacent raw JSON/manual checklist. Focused new tests 18/18 pass; server imports pass; test_protocol_agreement 32/32 passes when given a 420-second module budget. The broad 114-module run finished with 105 OK; 3 Windows platform failures reproduce on baseline and 6 modules exceeded 120 seconds (protocol later passed in isolation). No game-world/BeamMP drive was measured. Stage-1 implementation is saved in commits before beginning the upstream 1.7.1 integration.
