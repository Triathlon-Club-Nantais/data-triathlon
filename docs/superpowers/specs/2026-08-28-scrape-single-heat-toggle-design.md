# Choisir entre import unique et fanout complet à l'ajout d'une course

Issue #698.

## Contexte

Le fanout est aujourd'hui automatique et non désactivable sur le chemin
d'import public (`/ajouter`). Dès qu'une URL matche un `FanoutProvider`
(Klikego, Wiclax, RaceResult, Chronoplace, OkTime, Sporthive, ChronoWeb,
ProLiveSport — `backend/app/scrapers/registry.py:130-482`),
`import_service._scrape_all` appelle systématiquement le fan-out complet, sans
jamais passer `single_heat`.

Constat clé, découvert pendant le brainstorming : la mécanique existe déjà
presque entièrement. `import_event`, `iter_import_event` et `_scrape_all`
(`backend/app/services/import_service.py`) acceptent et propagent un paramètre
`single_heat: bool` depuis longtemps — seul le CLI (`rescrape-db
--single-heat`) l'atteint aujourd'hui. Sept des huit providers fan-out ont déjà
une sémantique sensée pour `single_heat=True` (import de l'URL telle quelle,
sans fan-out). Seul `ChronoplaceProvider.scrape_event_all` n'accepte pas ce
paramètre dans sa signature, alors que `chronoplace.scrape_event_all(url)` —
le contrat historique pré-fanout — existe toujours et n'est simplement plus
appelé par la classe.

## Décisions

1. **Périmètre** : le choix est proposé pour les 8 providers fan-out, pas
   seulement Klikego/BreizhChrono. Justification : ne demande qu'un petit
   ajout (Chronoplace) pour uniformiser un comportement déjà présent partout
   ailleurs.
2. **Défaut** : « import unique » est le choix par défaut (opt-in vers le
   fanout, pas l'inverse) — moins de surprise sur le volume importé pour un
   visiteur qui colle une URL sans réfléchir au fanout.
3. **Exception au défaut** : pour Klikego et BreizhChrono, `single_heat=True`
   sur une URL **sans sélecteur de heat** (`?heat=X` absent) est un chemin non
   testé en production — le CLI l'interdit aujourd'hui explicitement
   (`valider_single_heat` exige `heat=` dans l'URL). Pour ces deux providers,
   le défaut proposé à l'utilisateur suit ce que l'URL cible déjà : « unique »
   pré-coché seulement si l'URL porte déjà un sélecteur de heat, sinon
   « fanout » pré-coché. L'utilisateur peut toujours choisir « unique » à la
   main pour ces URLs — voir Risques.

## Backend

- `FanoutProvider` gagne une méthode `targets_single_heat(url: str) -> bool`,
  par défaut `False`. `KlikegoProvider` la surcharge : vrai si `?heat=`
  présent et non vide dans l'URL (réutilise `_parse_url`).
  `BreizhChronoProvider` la surcharge : vrai si un heat est déjà présent dans
  le chemin (`_parse_bc_url`) ou dans `?heat=` côté live
  (`_parse_live_url`). Les 6 autres providers fan-out gardent le défaut
  `False` — sans objet pour eux (voir Décision 3, qui ne s'applique qu'à ces
  deux providers).
- `ChronoplaceProvider.scrape_event_all` gagne le paramètre
  `single_heat: bool = False` ; `True` délègue à
  `chronoplace.scrape_event_all(url)` — même patron que
  `ChronoWebProvider.scrape_event_all`, qui fait déjà exactement ça.
- `GET /scrape/detect` (`backend/app/api/v1/scrape.py`) renvoie deux clés
  supplémentaires, dérivées du registre (même principe que `supported` —
  source de vérité unique, pas de liste dupliquée côté front) :
  - `fanout: bool` — `isinstance(provider, FanoutProvider)`.
  - `default_single_heat: bool` — `True` si `fanout` est faux (sans objet) ou
    si le provider n'est ni Klikego ni BreizhChrono ; sinon
    `provider.targets_single_heat(url)`.
- `ScrapeRequest` (`backend/app/schemas/scrape.py`) gagne `single_heat: bool =
  True`.
- `scrape_event` et `scrape_event_stream`
  (`backend/app/api/v1/scrape.py`) passent `single_heat=body.single_heat` à
  `import_service.import_event` / `iter_import_event`. Aucun autre appelant
  (CLI `import-sheet`/`rescrape-db`, `batch`, re-scrape admin #118) n'est
  touché : ils gardent leur propre valeur explicite ou leur défaut `False`
  actuel du service, inchangé.

## Frontend

- `apiClient.detectProvider` (`frontend/lib/api/client.ts`) : le type de
  retour s'élargit à `{provider, supported, fanout, default_single_heat}`.
- `TcnScrapeForm` (`frontend/components/scrape/TcnScrapeForm.tsx`) : nouvel
  état `singleHeat: boolean`, réinitialisé à `detected.default_single_heat`
  à chaque détection reportée par `ProviderDetector` (`onDetected`). Un
  contrôle à deux options (paire de radios) s'affiche uniquement quand
  `detected?.fanout === true`, sous le champ URL, près de la ligne de verdict
  existante :
  - « Importer uniquement cette page »
  - « Importer tout l'événement (toutes les courses) »

  Formulation volontairement générique : elle reste vraie que « cette page »
  désigne un heat Klikego, un contest RaceResult, ou (Wiclax et apparentés)
  l'événement entier non découpé.
- `useImportStream.start` (`frontend/hooks/useImportStream.ts`) prend un
  second argument `singleHeat: boolean`, propagé à `importEventStream`
  (`frontend/lib/api/sse.ts`), qui l'inclut dans le corps POST sous
  `single_heat`.

## Erreurs et cas limites

- Provider non fan-out (Timepulse, Competitor, T2Area, RunnerBreizh,
  SportInnovation) : `fanout=false`, le contrôle ne s'affiche pas,
  `single_heat` est envoyé à `true` par défaut du schéma mais ignoré par ces
  providers (leur `scrape_event_all(url)` n'a jamais accepté ce paramètre —
  inchangé).
- Chronoplace : jusqu'ici seul provider fan-out sans échappatoire du tout ;
  après ce lot, `single_heat=True` importe l'épreuve visée par l'URL sans
  ses onglets sœurs, comme les 7 autres.
- Klikego/BreizhChrono sur URL sans sélecteur, utilisateur forçant quand même
  « unique » à la main : chemin `heat=""` non testé en amont de ce lot —
  accepté comme risque connu (l'utilisateur a explicitement outrepassé le
  défaut sûr), à couvrir par un test dédié qui documente le comportement réel
  plutôt que de l'interdire côté API.

## Tests

- Backend (pytest, non-`integration`) :
  - `ChronoplaceProvider.scrape_event_all(url, single_heat=True)` délègue à
    `chronoplace.scrape_event_all` et pas au fan-out.
  - `targets_single_heat` : Klikego avec/sans `?heat=`, BreizhChrono avec/sans
    heat (chemin classique et live).
  - `/scrape/detect` : `fanout` et `default_single_heat` corrects sur un
    échantillon couvrant les 8 providers fan-out, un provider non fan-out, et
    une URL non reconnue.
  - `/scrape/event` et `/scrape/event/stream` : `single_heat` du corps de
    requête atteint bien `import_service` (mock/spy), défaut `true` si omis.
- Frontend (vitest) :
  - Le contrôle n'apparaît que si `detected.fanout === true`.
  - Son état initial suit `detected.default_single_heat` et se réinitialise à
    chaque nouvelle détection.
  - `useImportStream.start` et `sse.ts` propagent `singleHeat` dans le corps
    POST.

## Hors périmètre

- Pas de changement au CLI (`rescrape-db --single-heat` garde sa propre
  validation, inchangée), au `batch`, ni au re-scrape admin (#118).
- Pas de migration DB.
- Pas de nouvelle capacité de ciblage de sous-unité par URL pour les
  providers qui n'en ont pas (Wiclax, RaceResult, OkTime, Sporthive,
  ChronoWeb, ProLiveSport) : leur « unique » reste « tout ce que rend l'URL,
  sans fan-out », comme aujourd'hui via l'échappatoire CLI.
