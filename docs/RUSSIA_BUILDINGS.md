# Russia buildings and infrastructure

## Manual height corrections

`server/building_overrides.json` is an optional, versioned list of exact building corrections. The packaged Windows
server includes this file. After changing it, restart the server process; corrections are loaded once per process.

```json
{
  "schema": 1,
  "buildings": {
    "gers:OVERTURE_FEATURE_ID": {"height": 21.0, "num_floors": 7},
    "source:OpenStreetMap:123456789": {"height": 12.0, "num_floors": 3}
  }
}
```

Use the feature's GERS ID when available. The source key is the exact Overture source dataset and record ID. Values are
explicit corrections and therefore replace the corresponding mapped value; omitted fields continue to use map data.
Accepted heights are 2–500 metres and floor counts are integers from 1–200. Unknown keys and invalid values are ignored.
The source Overture data is never edited.

## Mapped fences

Mapped Overture infrastructure barriers are rendered from line geometry and OSM `barrier`, `fence_type`, and
`material` tags. They use a small shared set of stock Forest models, are capped at 1,200 instances per tile, stay out
of a conservative road corridor, and inherit the mod's near-player collision and tile-unload behavior. Fence lines
are currently honored wherever the source maps them; the repository does not contain an authoritative country polygon
layer for safely gating additional procedural styles to Russia. No coordinate rectangle is used for that purpose.

## Commercial Places

Tiles with mapped commercial building candidates may also load the optional Overture Places layer. Specific open,
high-confidence categories within the footprint or 12 m of its outline inform the existing storefront style. Generic
POI categories and brand names are not used to fabricate shop signs. The Places layer is not requested on unrelated
residential tiles.
Car washes and auto/tire repair buildings use closed, low-poly bay panels in the shared building mesh; they do not add
one scene object per bay or generate invented shop/brand signs. Other commercial POIs use the existing generic
storefront architecture until more service-specific mapped geometry is available.
