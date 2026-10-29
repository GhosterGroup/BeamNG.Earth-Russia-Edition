# Siberian Winter Map Design

## Intent

Give the existing M-key world map an optional winter-styled satellite layer for Siberian locations while keeping roads,
homes, labels, GPS, saved places, route display, and ordinary satellite tiles available. The layer must use a separate
disk cache and bounded tile workers so the existing memory-optimized pipeline remains in control.

## Approaches

- **CSS filter over the existing satellite tiles:** low implementation cost, but makes roads and roofs as pale as the
  land and has no independent generated-tile cache.
- **Server-generated winter satellite layer (chosen):** decode one source tile in the existing bounded worker, apply a
  deterministic pixel transform, and write its JPEG under a separate winter directory. This preserves the existing
  source and attribution, does not retain a second in-memory tile pyramid, and leaves labels/GPS as separate overlays.
- **A new winter imagery provider:** could supply actual snow imagery, but no suitable licensed global Siberian winter
  imagery source is already integrated; it would add network, attribution, and coverage dependencies.

## Goals

- Add a winter satellite choice to the current map without changing its controls or GPS behavior.
- Keep road and building contrast; keep labels as an independent overlay.
- Store generated tiles separately from original satellite tiles and apply the existing tile-count pruning policy.
- Gate the initial winter layer to Siberia using a Russia boundary source plus a documented regional envelope; elsewhere
  return the unmodified imagery.
- Keep transformation deterministic, bounded to one tile per active worker, and compatible with BeamMP clients.

## Non-goals for this first stage

- Changing in-world terrain, vegetation, road friction, or weather.
- Claiming photorealistic semantic snow segmentation from RGB satellite imagery.
- Replacing original imagery or changing its source attribution.

## Implementation calls

- Add a `winter` tile layer to the existing Lua/Python map tile protocol and a `Winter satellite` option to the current
  Layers panel.
- Reuse map math, tile request limits, callbacks, HTTP service, labels, and GPS unchanged.
- Generate cache files under `<user>/temp/beamngEarth/maptiles/winter/` and include them in existing bounded pruning.
- Test transform behavior, region gates, separate paths, fallback, and existing map protocol.
- Treat screenshots and in-game frame/RAM measurements as unavailable until BeamNG is run.
