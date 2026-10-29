# Siberian Winter implementation plan

## Stage 1: Winter satellite map

1. Add tests for the winter map layer, separate cache path, deterministic pixel transformation, source fallback, and
   Russia/Siberia coverage.
2. Add a compact licensed Russia boundary dataset and a memory-light point-in-polygon helper; gate Siberia within
   Russia so neighboring countries retain original imagery.
3. Generate winter JPEGs through the existing bounded `TileFiles` workers and prune them with the existing cap.
4. Add the layer to Lua tile requests and the M-map Layers panel, preserving labels, GPS, route, saved places, and map
   movement.
5. Run focused map and Lua/UI checks; commit the map stage separately.

## Stage 2: In-world winter visuals

1. Inspect surface-layer, groundcover, tree season, road material, and BeamMP session settings.
2. Add deterministic winter surface/material selection, reduce or hide green grass, and add snow roadside/terrain
   dressing using the existing shared-asset and LOD pipelines.
3. Add conifer snow appearance and leaf-off deciduous variants through existing seasonal tree materials/assets.
4. Add sparse ice road patches with BeamNG-supported friction materials, preserving the active road collision directly
   under the vehicle.
5. Add tests for deterministic cross-client selection and bounded object counts; verify the actual material schema from
   shipped game assets before applying friction values.

## Stage 3: Settings and verification

1. Add Winter Mode Auto/On/Off, Snow Coverage Low/Medium/High, Road Ice Off/Low/Medium/High, and Snowy Trees On/Off.
2. Persist settings and include shared winter state in the session protocol where it affects multiplayer visuals or
   physics.
3. Run relevant tests and packaging checks; record exact untested in-game scenarios and never report unmeasured RAM/FPS
   as improvements.

## Constraints

- Work only on `feature/siberian-winter`; do not change `main`, upstream, or the existing building branch.
- Preserve existing RAM queue limits, download caches, and stable deterministic world generation.
- Make each verified stage its own commit.
