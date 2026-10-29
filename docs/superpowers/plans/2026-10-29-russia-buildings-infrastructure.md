# Russia Buildings & Infrastructure — implementation plan

## Goal

Improve Russian building classification, height data, mapped residential fences, and commercial/service visuals while preserving the existing BeamNG.Earth generation pipeline, BeamMP determinism, and bounded memory use.

## Scope and constraints

- Base: repository branch `feature/russia-buildings-infrastructure`, based on the completed 1.7.1-beta integration and RAM work.
- Do not change `main`, upstream, or the existing stable branch; keep implementation commits separate on this feature branch.
- Preserve original behavior outside Russia. Apply new procedural Russian-specific behavior only where country membership is established from suitable geographic evidence; do not use rough coordinate rectangles.
- Prefer mapped Overture/OSM data. Never treat a building footprint as a land parcel.
- Preserve reliable mapped height/floor/part data. Building footprint area must not be the primary floor-count signal.
- Keep deterministic output for BeamMP; keep caches and any added geometry bounded. Reuse shared assets and existing tile lifecycle/unloading.
- No claim of game FPS, memory, or screenshot comparison without running the actual game on the target setup.

## Work sequence

### 0. Baseline and architecture

- Inspect `server/buildings.py`, Overture layer schemas, places loading, mesh/prop output and Lua tile consumption.
- Record test baseline and discover available offline/map fixtures for Irkutsk, Markova, Novosibirsk, and a rural settlement.
- Identify an authoritative, appropriately licensed country-boundary source or existing region classifier before enabling Russia-only procedural behavior.

### 1. Commercial versus industrial classification

- Add tests proving large `commercial` and retail buildings are not classified as warehouses solely due to area, while explicit warehouse/factory/industrial tags remain industrial.
- Use building class/subtype/name and nearby categorized Overture Places evidence with bounded spatial searches and stable tie-breaking.
- Keep ambiguous buildings conservative. Avoid assigning real brands absent reliable source data.
- Run the focused buildings suite and relevant mapdata/places tests; commit this behavior independently.

### 2. Height and floor inference

- Add precedence tests: building-part geometry/height and mapped height/floor values are preserved; derived values are conservative and type-aware.
- Remove area-only floor-count inference as the primary fallback. Use regional/type defaults only when source values are absent or invalid.
- Add an optional separate stable-ID overrides configuration, validated on load and applied without modifying source map data.
- Run focused tests; commit separately.

### 3. Russian residential fences

- Prefer mapped Overture infrastructure barriers (fence/gate/wall) and preserved OSM tags; avoid duplicate mapped/generated segments.
- Add Russia-scoped procedural fence behavior only where safe lot/road/driveway/neighbour clearances can be established. Never infer a parcel from the house polygon.
- Reuse a small shared set of fence styles/materials, deterministic variant choice, distance/LOD and existing tile eviction. Keep collision near-player if the current asset pipeline supports it without unbounded objects.
- Add geometry, clearance, determinism, and bounded-output tests; commit separately.

### 4. Commercial and service visuals

- Build on existing building mesh/material systems and Places data; map shops, supermarkets, malls, car washes, repair/tyre services, pharmacies and cafes only from reliable categories.
- Create visuals first, no interactive services. Do not place objects on roads or invent brands.
- Batch repeated geometry/materials and retain deterministic IDs/tile behavior.
- Add tests for category mapping, stable placement, and invalid/ambiguous POIs; commit separately.

### 5. Verification and reporting

- Run all available focused and full automated tests.
- Collect before/after code-level generation measurements only where reproducible fixtures and instrumentation exist. Report unavailable in-game RAM/FPS/screenshots as unmeasured and give exact manual scenarios for the four target areas plus outside-Russia regression.
- Review `git diff`, ensure no unrelated changes, and report each stage’s files, tests, limitations, and commit hash.

## Acceptance criteria

- Large commercial footprints no longer become industrial solely because of area.
- Reliable mapped height/floor data remains unchanged; fallback floors are not driven primarily by footprint area.
- Stable-ID overrides are optional, validated, deterministic, and separate from source data.
- Russian fences use mapped line data when present; no lot is derived from a house footprint; no known roads, sidewalks, driveways, or neighboring buildings are crossed by procedural segments.
- POI-driven commercial/service visuals are deterministic, non-interactive, use no fabricated real brands, and share bounded assets.
- Tests pass for implemented behavior; runtime/game performance claims are backed by measurements or explicitly marked unavailable.
