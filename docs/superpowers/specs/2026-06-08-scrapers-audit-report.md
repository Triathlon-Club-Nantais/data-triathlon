# Rapport d'audit des scrapers — 2026-06-08

Généré via `backend-v2/scripts/audit_scrapers.py` (appels réseau réels sur une
épreuve par provider, voie unique `scrape_event_all`). URLs de référence fournies
par @tjarrier.

## Résultats

| Provider | Statut | Participants | Nom% | Temps% | Splits% | Rang% | Type(s) détecté(s) | Durée |
|---|:--:|--:|--:|--:|--:|--:|---|--:|
| klikego | ✅ | 17 | 100 | 100 | 0* | 100 | duathlon | 0.3 s |
| breizhchrono | ✅ | 302 | 100 | 100 | 1* | 100 | triathlon-m | 0.5 s |
| wiclax / chronosmetron | ✅ | 1911 | 100 | 88 | 84 | 100 | triathlon (s/m/l) | 0.6 s |
| timepulse | ✅ | 593 | 100 | 100 | 99 | 96 | triathlon | 3.8 s |
| prolivesport | ❌ | 0 | — | — | — | — | — | — |
| sportinnovation | ✅ | 541 | 100 | 100 | 100 | 100 | triathlon (s/m), aquathlon | 1.4 s |

`*` **Splits 0/1 % = comportement attendu, pas un défaut.** klikego et breizhchrono
ne récupèrent les splits détaillés (page `resultat-participant.jsp`) **que pour les
athlètes Nantais/TCN** (filtre `city=nantais` + mots-clés club). Une épreuve sans
licencié TCN affiche donc ~0 % de splits ; c'est voulu (le club ne veut enrichir
que ses membres). La métrique « Splits% » n'est pertinente que pour les providers
qui exposent les splits pour tous (wiclax, timepulse, sportinnovation).

## Verdict par provider

- **klikego** — ✅ fonctionnel. Nom/temps/rangs à 100 %. Splits gatés Nantais (OK).
- **breizhchrono** — ✅ fonctionnel (302 participants, multi-heats). Splits gatés Nantais.
- **wiclax / chronosmetron** — ✅ fonctionnel et robuste (1911 résultats, splits 84 %).
  Les 12 % sans temps = DNF/DNS. Le domaine `chronosmetron.wiclax-results.com` est
  bien routé vers le provider wiclax.
- **timepulse** — ✅ excellent (splits 99 %, rangs 96 %). Le plus lent (3.8 s) car le
  classement est recalculé par athlète. L'URL `…/resultats/live/3232` est gérée
  (extraction de l'id depuis le chemin).
- **prolivesport** — ❌ **échoue sur l'URL fournie**, mais **l'API fonctionne
  parfaitement** (cf. ci-dessous). Cause : format d'URL non géré, pas l'API.
- **sportinnovation** — ✅ via l'URL HTML `…/Evenements/Resultats/7031` (541 résultats,
  tout à 100 %). ⚠️ La 2ᵉ forme d'URL fournie, `results.sportinnovation.fr/race/{slug}`
  (nouvel affichage 2026), **n'a pas été testée** et n'est probablement pas gérée par
  `scrape_event_all` (qui attend `path_parts[0]` = codeUrl, or le chemin commence par
  `/race/`). À vérifier en Phase 2.

## Détail prolivesport (faux négatif d'URL)

L'URL front `prolivesport.fr/result/1082/6` utilise un **index positionnel** de
course, pas un code. Le scraper, lui, n'accepte que `?eventId=…&race=<code>`.

Vérifié sur l'API (`api.prolivesport.fr/apiws`, token `AUTH_PLSWS_V2`) :
- `result/raceList/1082/` → 11 courses, codes nommés : `PO-PU, BE-MI, S_Light,
  Challenge, TREP, TRGP, S, M, M_relay, SUPP2, SUPP`.
- L'index **6** (0-based) de cette liste = **`S`**.
- `result/indiv/1082/S/` → **1188 athlètes**. `result/indiv/1082/6/` → 0.

→ L'API et le parsing sont sains. **Correctif Phase 2 :** parser la forme
`/result/{eventId}/{raceIndex}` et résoudre `raceIndex` → code course via
`raceList` avant l'appel `indiv`.

## Backlog Phase 2 (priorisé par les faits)

1. **prolivesport — adaptateur d'URL** (gain immédiat, API déjà OK) : gérer
   `prolivesport.fr/result/{eventId}/{raceIndex}` ; résoudre l'index via `raceList`.
   Sans race → déjà géré (1ʳᵉ course). *Touche `app/scrapers/prolivesport.py`.*
2. **sportinnovation — forme 2026** : supporter `results.sportinnovation.fr/race/{slug}`
   dans `scrape_event_all` (le chemin `/race/…` casse l'hypothèse actuelle).
3. **Excel xlsx (optionnel)** : breizhchrono et chronosmetron exposent un export
   Excel. Les scrapers HTML/XML actuels **fonctionnent déjà** → migration Excel = pari
   robustesse/simplicité, pas une nécessité. À évaluer si le HTML/XML casse.
4. **klikego/timepulse** : aucun correctif requis (fonctionnels).

## Reproduire

```bash
cd backend-v2 && source .venv/bin/activate
python scripts/audit_scrapers.py --provider all --json   # rapport + JSON
python scripts/audit_scrapers.py --provider timepulse    # un seul provider
```
