# Rapport d'audit des scrapers — 2026-06-08

Généré via `backend-v2/scripts/audit_scrapers.py` (appels réseau réels sur une
épreuve par provider, voie unique `scrape_event_all`). URLs de référence fournies
par @tjarrier.

> **Mise à jour (même jour) :** prolivesport **corrigé** (commit `fix(prolivesport)`).
> Les 6 providers sont désormais fonctionnels. Détail du correctif plus bas.

## Résultats

| Provider | Statut | Participants | Nom% | Temps% | Splits% | Rang% | Type(s) détecté(s) | Durée |
|---|:--:|--:|--:|--:|--:|--:|---|--:|
| klikego | ✅ | 17 | 100 | 100 | 0* | 100 | duathlon | 0.3 s |
| breizhchrono | ✅ | 302 | 100 | 100 | 1* | 100 | triathlon-m | 0.5 s |
| wiclax / chronosmetron | ✅ | 1911 | 100 | 88 | 84 | 100 | triathlon (s/m/l) | 0.6 s |
| timepulse | ✅ | 593 | 100 | 100 | 99 | 96 | triathlon | 3.8 s |
| prolivesport | ✅ | 1080 | 100 | 100 | 99 | 100 | triathlon | 0.5 s |
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
- **prolivesport** — ✅ **corrigé** (1080 finishers, splits 99 %). Auparavant KO pour
  deux raisons (format d'URL + filtre DNS inversé) — détail et correctif ci-dessous.
- **sportinnovation** — ✅ via l'URL HTML `…/Evenements/Resultats/7031` (541 résultats)
  **et** via la forme 2026 `results.sportinnovation.fr/race/{slug}` (✅ ajoutée — 696
  résultats avec métadonnées complètes, cf. Phase 2 #2).

## Détail prolivesport — DEUX bugs (✅ corrigés)

> **Correctif appliqué.** Trois helpers purs ajoutés à `prolivesport.py` (testés
> offline) : `_parse_url` (gère les deux formes d'URL), `_resolve_race` (résout
> l'index positionnel via raceList) et `_is_finisher` (filtre sur la présence d'un
> temps, plus sur `dns`). Vérifié en réel : 1080 finishers sur les deux formes d'URL.

L'API est saine (token `AUTH_PLSWS_V2`), mais `scrape_event_all` ne renvoyait
**jamais** de résultat sur cet événement, pour deux raisons cumulées :

**Bug A — forme d'URL non gérée.** L'URL front `prolivesport.fr/result/1082/6`
utilise un **index positionnel** de course, pas un code. Le scraper n'accepte que
`?eventId=…&race=<code>`.
- `result/raceList/1082/` → 11 courses : `PO-PU, BE-MI, S_Light, Challenge, TREP,
  TRGP, S, M, M_relay, SUPP2, SUPP`. L'index **6** (0-based) = **`S`**.
- *Correctif :* parser `/result/{eventId}/{raceIndex}` et résoudre l'index → code
  via `raceList` avant l'appel `indiv`.

**Bug B — filtre DNS inversé (le plus grave).** Même avec une URL valide
(`?eventId=1082&race=S`), `scrape_event_all` renvoie **0**. `_fetch_indiv` ramène
pourtant bien **1188 athlètes**, mais le filtre final les supprime tous :
```python
[... for a in athletes if a.get("dns", "N") != "O"]  # exclut les "DNS"
```
Or sur ces données **les 1188 finishers ont `dns="O"`** (et tous ont un temps).
Le champ `"O"` ne signifie donc pas « non-partant » ici → le filtre vide la liste.
- *Correctif :* ne plus exclure sur `dns=="O"`. Filtrer les vrais abandons via la
  présence d'un `time` (ou recouper `dnf`/`dns`/`dsq`, qui sont des champs distincts).

→ Les deux sont désormais corrigés (cf. encart en tête de section).

## Backlog Phase 2 (priorisé par les faits)

1. ~~**prolivesport — débloquer `scrape_event_all`**~~ ✅ **FAIT** (bugs A + B corrigés,
   tests offline + integration verts).
2. ~~**sportinnovation — forme 2026** `results.sportinnovation.fr/race/{slug}`~~ ✅
   **FAIT** : branche API JSON (slug → `raceId` → résultats), helpers
   `_classify_results_url` / `_parse_api_athlete` / `_scrape_results_race`.
3. ~~**Excel (optionnel)**~~ ❌ **ABANDONNÉ** (décision @tjarrier, 2026-06-08) après
   investigation :
   - **breizhchrono** : l'export `…/{heat}/export` est un **`.xls` legacy** (BIFF/OLE2,
     pas `.xlsx`) → imposerait la dépendance `xlrd` + un parsing de colonnes dynamiques
     (`Dossard, Nom, Prénom, Sexe, Club, Temps Officiel, Classement T1, T2 + CAP…`),
     pour **remplacer un scraper qui marche** (302 participants, splits TCN déjà
     récupérés). Bénéfice marginal, coût (dépendance + format legacy) trop élevé.
   - **chronosmetron** : **aucun export Excel exposé** ; les données sont dans le XML
     `.clax` déjà exploité par le scraper wiclax (1911 résultats, 84 % splits).
   - *Réévaluable uniquement si le HTML/XML casse un jour.*
4. **klikego/timepulse** : aucun correctif requis (fonctionnels).

## Reproduire

```bash
cd backend-v2 && source .venv/bin/activate
python scripts/audit_scrapers.py --provider all --json   # rapport + JSON
python scripts/audit_scrapers.py --provider timepulse    # un seul provider
```
