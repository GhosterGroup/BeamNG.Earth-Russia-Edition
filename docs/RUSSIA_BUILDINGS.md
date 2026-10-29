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
