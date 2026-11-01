# Route 627 — onderzoek ontbrekende geometrieën (2026-11-01)

## Probleem
In de bestaande `getRouteById`-export zijn `locations` voor bronroute-ID 89 (`627i`) en 90 (`627r`) leeg. Beide richtingen bevatten wel geordende referentiepunten en positieve tijdcontrolepunten. Een GTFS `shape_id` kan daardoor niet betrouwbaar worden gegenereerd.

## Bevestigde brongegevens

- Socobuses' [officiële despacho-lijst](https://socobuses.com/users) noemt `627 I` bij **Puerta del Sol** (Calle 32C – Carrera 2F) en `627R` bij **Maltería** (nabij restaurante Las Delicias, km 14 Vía al Magdalena). Dit bevestigt de beginlocaties, **niet** het precieze wegtracé.
- De [officiële toeristische routelijst](https://socobuses.co/tourist) koppelt `627i` en `627r` aan **Bosque Popular el Prado**. Dit is een extra route-indicatie, geen geometrie.
- De [gemeente Manizales](https://www.ventanilla.manizales.gov.co/ver-tramite/eyJpdiI6IlZ5YVc3RUtQdGpST3hhSE5uV2s0d0E9PSIsInZhbHVlIjoiNlRRNndZQUZtRUtmeVVqbTEzQm4wUT09IiwibWFjIjoiNDViOTVjODliYmJiNWJjMjMyOWY0YzU1MWFmNmMxMGIxM2U4NjViZjQ0YzBhNzhkNjY5MDg2Y2IxMDUwNGM4NyIsInRhZyI6IiJ9) verwijst voor stedelijke OV-routes naar de publieke [ArcGIS-dataset Rutas Servicio Público](https://geodata-manizales-sigalcmzl.opendata.arcgis.com/datasets/54eeb145d33a4033995bc61a0c35c436/explore).

## Kandidaten en verificatie

1. Download de **originele** ArcGIS-routegeometrieën met routecode, vervoerder, naam, bronlaag en peildatum.
2. Filter op `SOCOBUSES`, `627`, `PUERTA DEL SOL`, `MALTERIA` en alternatieve spellingen. **Een andere gemeentelijke routecode mag niet automatisch als 627 worden beschouwd.**
3. Vergelijk beide richtingvarianten met de volgorde van de 33 respectievelijk 28 Socobuses-referenties, Bosque Popular el Prado en de expliciete eindpunten.
4. Controleer of het GIS-record richtinggevoelig is. Een gedeeld tracé mag niet zonder bewijs omgekeerd worden voor de tegenrichting: eenrichtingsstraten en omwegen kunnen verschillen.
5. Alleen bij voldoende overeenstemming: bewaar originele GeoJSON, URL, datum, matchargumenten en afwijkingen in `research`; voeg vervolgens expliciet goedgekeurde `shape_89` en `shape_90` toe via een **aparte** overridebron.
6. Als de bron geen voldoende betrouwbare overeenkomst oplevert, blijven 627i/r uitgesloten van de experimentele feed.

## Status

**Onderzoek gestart, geometrieën niet bevestigd.** Er is nog geen GIS-match aangetoond en geen routevorm aangepast. Het samenvoegen van referentiepunten met een routeringsdienst zou een nieuwe schatting opleveren, geen officieel vastgesteld wegtracé.
