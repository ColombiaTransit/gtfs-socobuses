# Analyse van zes uitgesloten Socobuses-richtingen (2026-11-01)

Bron: `route_details.json` uit API-probe-artifact 13087188371, vergeleken met GTFS-build-run [41332420828](https://github.com/ColombiaTransit/gtfs-socobuses/actions/runs/41332420828), artifact 13093434066. Dit zijn bronwaarnemingen, geen bevestigde dienstregelingen.

| Route | Bron-ID | Start → einde | Bronwaarneming | Behandeling |
|---|---:|---|---|---|
| 604i | 37 | Villa Pilar → Villaluz | 42 referenties; positie 41 is **Villaluz**, type 1, 55 min; positie 42 is **Ecoparque los Yarumos**, type 2, 0 min. 92 geometriepunten | Laatste punt ligt **ná het expliciet benoemde eindpunt**. Experimentele builder kapt alleen deze na-eindpuntreferentie af, mits de naam exact overeenkomt met `endControl`. Geen extrapolatie. |
| 611r | 52 | Barrio Palermo → Villa Pilar | 37 referenties, 69 geometriepunten; alle type-1-controles hebben tijd 0 | Geen onderbouwde totale reistijd. Blokkeren, niet vervangen door tijden van andere richting. |
| 615i | 63 | Villa Pilar → Bengala | 30 referenties, 87 geometriepunten; eerste type-1-punt op positie 1 heeft 45 min; latere waarden beginnen bij 8 min en eindigen bij 45 min | Eerste 45 min kan een invoerfout zijn, maar dat is niet bewezen. Blokkeren tot bronbevestiging; geen automatische correctie. |
| 625r | 82 | Estadio Palogrande → Puerta del sol | 13 referenties, 43 geometriepunten; laatste positieve controle op positie 11 (**Estación de Servicio los cedros**, 25 min); positie 13 is **Puerta del sol**, type 1, 0 min | Eindpunt heeft geen tijdcontrole. Blokkeren; extrapolatie zou een rijtijd verzinnen. |
| 627i | 89 | Puerta del sol → Malteria | 33 referenties, 8 positieve type-1-controles, laatste op positie 33 (55 min); **0 geometriepunten** | Tijdcontroles bruikbaar, maar shape ontbreekt. Geometrie uit onafhankelijke bron nodig. |
| 627r | 90 | Malteria → Puerta del sol | 28 referenties, 7 positieve type-1-controles, laatste op positie 28 (50 min); **0 geometriepunten** | Tijdcontroles bruikbaar, maar shape ontbreekt. Geometrie uit onafhankelijke bron nodig. |

## Implementatie

`scripts/build_experimental_gtfs.py` kan nu uitsluitend bij een **expliciet genoemde eindbestemming** met een positief type-1-controlepunt de **daarna** voorkomende ongetimede referenties negeren. Daarmee kan 604i weer een experimentele template krijgen, zonder een tijd voor Ecoparque los Yarumos te verzinnen. Deze ingreep is alleen voor de experimentele feed. Het oorspronkelijke bronbestand en de conservatieve export blijven intact.

**Open:** 611r, 615i en 625r vragen bronverificatie van reistijden. 627i/r vragen een routegeometrie uit een controleerbare bron; referentiepunten alleen zijn onvoldoende om een werkelijk wegtracé te reconstrueren. De geautomatiseerde build en MobilityData-validatie moeten opnieuw draaien om de wijziging te bevestigen. De haltes blijven ongevalideerd en de feed mag niet worden gepubliceerd.
