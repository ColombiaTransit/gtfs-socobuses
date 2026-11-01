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

## Experimentele frequentieplanning (2026-11-01)

`scripts/build_experimental_gtfs.py` gebruikt nu per dagtype de op de officiële Socobuses-pagina gepubliceerde **algemene** dienstvensters: WEEKDAY 04:30–22:30, SATURDAY 06:00–21:00 en SUNDAY_HOLIDAY 06:00–21:00. De bron-URL wordt meegeleverd in `research/frequency_windows.json`.

Per bronrichting wordt de positieve API-frequentie in minuten omgezet naar `frequencies.txt.headway_secs` (minuten × 60), met `exact_times=0`. Bij frequentie 0 of een ongeldige waarde wordt voor die richting en dat dagtype geen template-trip of frequentie gemaakt. Het bijbehorende `trips.txt`-record gebruikt de gegroepeerde lijncode en de eigen `direction_id` en `shape_id`.

**Publicatiebeperking:** dit is uitsluitend een experimentele planning. De algemene uren zijn niet bevestigd als exacte vertrekvensters per route. De bijbehorende `stop_times.txt` bevat geschatte tijden en geometrisch geschatte haltes; dit is geen officiële, publiceerbare dienstregeling. Routes met onvoldoende of tegenstrijdige tijdcontrolepunten worden uitgesloten. De GitHub Actions-workflow moet nog worden uitgevoerd om de aangepaste output te toetsen.

## Controle volledige experimentele feed (2026-11-01)

GitHub Actions-run [41332081262](https://github.com/ColombiaTransit/gtfs-socobuses/actions/runs/41332081262) is geslaagd. Het artifact bevat **geen** bewaard validatorrapport, zodat de inhoudelijke MobilityData-meldingen uit die run niet zijn vastgesteld.

Het artifact toont: 30 lijnen in de conservatieve feed, 29 lijnen in de experimentele feed, 148 template-trips, 148 frequenties en 4.437 stop-times. De uitsluitingslijst bevat 17 regels: 10 ontbrekende zondagfrequenties, 2 ontbrekende eindcontrolepunten (bronroute-ID 37 en 82), 1 zonder positieve tijdcontrolepunten (52), 1 niet-monotone tijdreeks (63) en 2 zonder voldoende geometrie (89, 90). Dit zijn **meldingen**, geen 17 verschillende uitgesloten routes; de zondagmeldingen betreffen alleen die dagsoort.

`scripts/validate_experimental_gtfs.py` voert nu een structurele controle uit op verwijzingen, tijdvolgorde, frequentie-/templatekoppelingen, dagtypevensters, uitgesloten timingroutes en afwezige zondagtemplates. Het resultaat wordt `output/validation/gtfs-consistency.json`. De workflow bewaart daarnaast de uitvoer van de MobilityData-validator als `output/validation/validator.log`, naast eventuele rapportbestanden.

Deze controles kunnen geen werkelijke halteposities, rijtijden of vertrektijden bevestigen. De feed blijft **EXPERIMENTAL ONLY — DO NOT PUBLISH**. Voer de workflow opnieuw uit om de nieuwe controles en het validatorrapport te beoordelen.
