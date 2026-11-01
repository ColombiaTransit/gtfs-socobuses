# Socobuses — dienstkalender en algemene diensturen

Laatst gecontroleerd: 2026-11-01.

## Primaire bron

Socobuses S.A., Engelstalige toeristenpagina, sectie **Service hours**:
https://socobuses.com/tourist?language=EN

De website vermeldt:
- Monday to Friday: **04:30 am at 10:30pm**.
- Saturday, Sunday and holidays: **06:00am at 09:00pm**.
- De website waarschuwt dat de geschatte frequentie op zaterdag, zondag en feestdagen kan variëren.

Dit zijn **officieel gepubliceerde algemene diensturen**. De bron specificeert niet per route of rijrichting een eerste of laatste vertrek. De grenzen zijn daarom niet zonder meer exacte vertrektijden voor iedere route.

## GTFS-interpretatie

| service_id | Weekdagen | Algemeen dienstvenster | Status |
| --- | --- | --- | --- |
| WEEKDAY | ma-vr | 04:30–22:30 | Bevestigd als algemeen venster |
| SATURDAY | za | 06:00–21:00 | Bevestigd als algemeen venster |
| SUNDAY_HOLIDAY | zo en Colombiaanse feestdagen | 06:00–21:00 | Bevestigd als algemeen venster |

De dagtypefrequenties worden per route gelezen uit de Socobuses-API:
`mondayToFridayTimeRoute`, `saturdayTimeRoute` en `sundayAndHolidaysTimeRoute`.
De routecontroller toont deze waarden als benaderde frequentie. Voor zondag/feestdagen is frequentie 0 bevestigd als geen dienst (zie hieronder).

`scripts/build_calendar.py` genereert de drie algemene GTFS-service-ID's en
`calendar_dates.txt` met nationale Colombiaanse feestdagen via `holidays`.
De keuze om op nationale feestdagen de zondagdienst te activeren sluit aan bij
het op de website genoemde dagtype, maar lokale afwijkingen en route-uitzonderingen
blijven te onderzoeken.

`scripts/build_service_matrix.py` legt het bronvenster en de per-route
frequentiegegevens vast. Het script genereert **geen** fictieve ritten.
Voor een definitieve `frequencies.txt` zijn per route/richting de werkelijke
eerste en laatste vertrektijden en de toepasbaarheid van de frequentie nodig.

## Aanvullende bron

Socobuses routepagina: https://socobuses.co/routes
API: `site/routes/getRouteById` (per-route frequentievelden).

Bronstatus: website geraadpleegd op 2026-11-01; deze documentatie bewaart de
bron-URL en de waargenomen tijdvensters, niet een onveranderlijke kopie van de pagina.

## Interpretatie van frequentie 0 — bevestigd op de website (2026-11-01)

De Socobuses-website toont bij de betrokken routes voor **zondag en feestdagen** eveneens frequentie **0**. Voor deze feed hanteren we daarom de expliciete operationele regel: **frequentie 0 betekent dat de route op zondag en feestdagen niet rijdt**. Dit vervangt de eerdere onderzoeksstatus `zero_unconfirmed` voor het zondag-/feestdagveld.

Het gaat om 12 richtingsroutes, gegroepeerd in zes routeparen: `602i/r`, `605i/r`, `609i/r`, `610i/r`, `613vi/vr` en `625i/r`. De overige 47 van de 59 routes hebben een positieve zondag-/feestdagfrequentie.

**Bronnen:** Socobuses routepagina https://socobuses.co/routes en de per-route weergave van de frequentie; Socobuses-API `site/routes/getRouteById`, veld `sundayAndHolidaysTimeRoute`. De overeenkomst tussen website en API is door de gebruiker bevestigd op 2026-11-01.

**GTFS-regel:** genereer voor deze 12 routes geen `trips.txt`-ritten met `service_id=SUNDAY_HOLIDAY`. De algemene kalender in `calendar.txt` blijft bestaan voor de 47 andere routes. De officiële algemene diensturen 06:00–21:00 zijn niet van toepassing als er voor de betreffende route geen dienst is.

## Richtingsvarianten ida/regreso en GTFS-mapping

De Socobuses-routecode met suffix `i` staat voor **ida** (heenrichting, GTFS `direction_id=0`) en suffix `r` voor **regreso** (terugrichting, `direction_id=1`). Verwijder alleen de laatste letter bij het bepalen van de GTFS-`route_id`: `602i` en `602r` worden lijn `602`; `613vi` en `613vr` worden lijnvariant `613v`, **niet** `613`. Niet-herkende codes blijven afzonderlijke lijnen zonder vastgestelde richting.

De bronroute-ID en volledige broncode blijven behouden in `research/route_directions.csv`, inclusief het kandidaat-`trip_headsign` (eindpunt) en de eigen `shape_id`. `routes.txt` bevat iedere gegroepeerde lijn eenmaal; de richtingsspecifieke geometrieën blijven afzonderlijk in `shapes.txt`.

Bij het bouwen van `trips.txt` moeten alle richtingsritten dezelfde gegroepeerde `route_id` krijgen, met hun eigen `direction_id`, `shape_id`, `trip_headsign` en toepasselijke `service_id`. De bronfrequentie 0 op zondag/feestdagen betekent **geen ritten** voor die richting op `SUNDAY_HOLIDAY`. De algemene diensturen en frequenties vormen geen bewijs voor exacte vertrektijden; de conservatieve builder genereert daarom nog geen ritten.
