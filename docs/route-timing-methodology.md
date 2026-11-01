# Socobuses — rijtijden en tijdcontrolepunten

Onderzocht: 2026-11-01. Bron: bestaande Socobuses `site/routes/getRouteById` API-export, 59 richtingsroutes, plus de timing-audit (GitHub Actions run 41326326014, artifact 13091730719).

## Vaststellingen

- 1.765 referentiepuntvermeldingen: type 1 = 428, type 2 = 746, type 3 = 591.
- 363 positieve `timeDifference`-waarden, **uitsluitend bij type 1**.
- `timeDifference=0` bij type 1/2/3 betekent **geen bruikbare tijdmeting**; het betekent niet nul minuten rijtijd.
- De routevisualisatie in `visualRoute.js` gebruikt positieve waarden van hoofdpunten en trekt een gekozen eerste hoofdpunt af om een relatieve tijd weer te geven. De API levert geen bevestigde dienstregeling of stop-times per halte.

## Beoordeling van de 59 routes

- **57 routes:** positieve type-1-controlepunten in niet-dalende volgorde. Geschikt als uitgangspunt voor **geschatte** reistijden, niet voor bevestigde `stop_times.txt`.
- **611r / bronroute-ID 52:** geen enkel positief controlepunt; niet automatisch interpoleren of fictieve rijtijd invullen.
- **615i / bronroute-ID 63:** eerste controlepunt op sequentie 1 is 45 minuten, gevolgd door sequentie 7 op 8 minuten; de tijdreeks is niet-monotoon. Niet automatisch corrigeren door 45 op 0 te zetten of de reeks te laten doorlopen; oorzaak nog onbekend.
- Van de 57 monotone routes hebben **55** een positief tijdcontrolepunt op het laatste referentiepunt. De overige **2** hebben geen bevestigd eindcontrolepunt. Ook bij de 55 zijn beginpunt en tussengelegen type-2-punten niet allemaal getimed.

## Afgesproken verwerking

1. Gebruik alleen positieve `timeDifference`-waarden van type-1-hoofdpunten als broncontrolepunten; behoud oorspronkelijke waarden en volgorde.
2. Neem type 3 niet op als kandidaat-boarding-stop. Type 1 en 2 zijn uitsluitend kandidaat-haltes, tot haltevalidatie.
3. Interpoleer uitsluitend als **geschatte** tussenliggende rijtijd tussen twee bruikbare controlepunten; markeer afgeleide tijden expliciet. Niet extrapoleren vóór het eerste of ná het laatste bevestigde controlepunt zonder afzonderlijke onderbouwing.
4. Markeer 611r en 615i als geblokkeerd voor automatische timing. Los de bronafwijkingen eerst op of sluit deze richtingen uit van experimentele tijdgeneratie.
5. `scripts/audit_timing_readiness.py` schrijft per bronroute een machineleesbare beoordeling. Het script genereert bewust geen `stop_times.txt`.
6. Officiële algemene diensturen (zie `docs/service-calendar-sources.md`) zijn **geen** bewijs van de eerste/laatste rit per richting.

**Conclusie:** de bronanalyse van de rijtijden is afgerond. Betrouwbare, publiceerbare haltepassagetijden ontbreken nog. Een volledige experimentele dienstregeling vereist expliciete aannames, geverifieerde haltevolgorde en een afzonderlijke validatie.
