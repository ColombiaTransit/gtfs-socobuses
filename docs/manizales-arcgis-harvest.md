# Manizales ArcGIS harvest

Run the manual workflow [Harvest Manizales ArcGIS](../.github/workflows/harvest-manizales-arcgis.yml). It inventories all feature layers and tables from:

- Municipal Manizales `MOVILIDAD/appTuristica/MapServer`: https://sig.manizales.gov.co/wadmzl/rest/services/MOVILIDAD/appTuristica/MapServer
- Public `Rutas Servicio Publico` ArcGIS item `54eeb145d33a4033995bc61a0c35c436`, resolved via the ArcGIS Online item API to its actual service URL.

For every queryable layer the script stores source service metadata, layer schema and all features as WGS84 GeoJSON. The download uses object-ID batches and verifies that every advertised object ID was retrieved. `manifest.json` contains source URLs, layer names, geometry types, counts and errors. Failed layers are never silently treated as complete. The artifact is uploaded even when the job fails.

**Important:** A similarly named `MovilidadPublica/FeatureServer/2` layer discovered in web search belongs to **Sabaneta**, not Manizales. It is intentionally **excluded**.

Review the manifest for layers with `paradero`, `parada`, `bus`, `ruta` or `transporte` in their names, and compare route features against Socobuses route 627i/627r. This archive does **not** imply that municipal route records are current or that point features are validated boarding stops. No changes are made to the GTFS feed.

To run locally: `pip install requests && python scripts/harvest_manizales_arcgis.py --output output/arcgis`.
