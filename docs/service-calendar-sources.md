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
De routecontroller toont deze waarden als benaderde frequentie; nulwaarden zijn **geen bewezen dienstuitval**.

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
