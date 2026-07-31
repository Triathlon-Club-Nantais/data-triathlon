# Convention de nommage des identifiants backend — design

Issue : [#88](https://github.com/Triathlon-Club-Nantais/data-triathlon/issues/88)
(constat né de la revue de la PR #59).
Date : 2026-07-31.

## 1. Ce que la branche livre, et ce qu'elle ne livre pas

Cette branche livre **la règle et son outillage**. Elle ne renomme rien.

Les renommages partent ensuite en PRs distinctes, un lot par PR, selon la liste
close de la §5. C'est le découpage que l'issue demande explicitement (« garder
des diffs relisibles ») et il a une seconde vertu : la convention existe **avant**
qu'on renomme, donc chaque lot se relit contre un texte, pas contre l'intuition
du relecteur.

| Fichier | Changement |
| --- | --- |
| `.specify/memory/constitution.md` | Principe I amendé → **v1.1.0** (bump MINOR, Sync Impact Report réécrit) |
| `AGENTS.md` § Conventions générales | Renvoi mis à jour v1.0.0 → v1.1.0 ; la phrase « on ne réécrit pas l'existant » nomme désormais la dérogation |
| `backend/pyproject.toml` | `[tool.ruff.lint] select` gagne `"N"` |
| 3 sites de code | les 3 violations `N` qu'active ce `select` |

## 2. Le constat, mesuré

Relevé sur `backend/app` par parcours AST (fonctions, classes, constantes de
module, variables locales, paramètres), filtré sur un lexique français :

**184 identifiants français sur 23 modules.** Dont une marge à retrancher :
~9 faux positifs (des mots anglais que le lexique attrape : `ranges`,
`is_cumulative`, `_RELAY_CATEGORIES`, `_reconcile`, `reconciliations`,
`_CELL_CUMULATIVE`, `_TEAM_CATEGORIES`, `cumulative`, `Passage`) et 3 gelés par
contrat public (§4). **Soit ~172 symboles réellement à renommer.** Les décomptes
par module de la §5 sont donc des ordres de grandeur : **chaque PR établit sa
liste exacte**, elle ne la présume pas.

Le cas le plus net du constat de l'issue tient en une signature :

```python
def est_echec_total(*, epreuves: int, errors: int) -> bool:   # app/services/batch.py
```

Français et anglais dans les paramètres d'une même fonction.

## 3. Ce que la constitution disait déjà — et le blocage

Le Principe I **tranche déjà le point 2 de l'issue** :

> **English** — tout ce qui est technique et invisible à l'utilisateur : noms
> d'identifiants (variables, fonctions, classes, modules, endpoints, colonnes DB)…

Il n'y avait donc rien à décider sur la langue par défaut. Mais le même principe
porte une **règle de transition qui interdit le travail que l'issue propose** :

> **Règle de transition** : […] **On ne réécrit rien**. La règle s'applique aux
> **nouveaux** ajouts […] *Rationale* : Ne pas migrer l'existant : le coût de la
> réécriture massive dépasse le bénéfice, et le principe III (TDD) ne peut
> tolérer un patch de 200 fichiers non testés.

La campagne « renommer par lots, un module ou un paquet par PR » **est** la
réécriture de l'existant que ce paragraphe décline. Et la constitution prime sur
`AGENTS.md`. Inscrire la campagne dans `AGENTS.md` seul aurait recréé exactement
la contradiction que le Sync Impact Report avait relevée à la ratification —
deux documents qui se contredisent, dont le plus souvent lu est le subordonné.

D'où le choix : **on amende la constitution**, et `AGENTS.md` continue de
renvoyer sans dupliquer.

Le rationale de la règle de transition n'est d'ailleurs pas contredit par la
campagne, il est *satisfait* par elle : « un patch de 200 fichiers non testés »
est précisément ce que le découpage en lots évite.

## 4. Les trois clauses ajoutées au Principe I

### (a) Explicitness — et son honnêteté sur l'automatisation

> Un identifiant nomme ce qu'il porte. Les noms d'une ou deux lettres sont
> réservés aux liaisons dont la portée tient sous les yeux : variable de
> compréhension, variable de boucle, paramètre de lambda, et `db` (session
> SQLAlchemy, idiomatique dans tout le projet). Hors de là, le nom est un mot.

Cette clause **n'est pas automatisable**, et le principe doit le dire plutôt que
de laisser croire à un filet qui n'existe pas :

- ruff n'a **aucune** règle de longueur ou d'explicitness. `pep8-naming` (N801 à
  N818) ne contrôle que la **casse**. Le seul filet existant est `E741`
  (`l`, `O`, `I`), déjà actif via le `"E"` du `select`.
- un lint maison sur la seule longueur marquerait **431 occurrences dans `app/`**
  (48 identifiants distincts) et **591 dans `tests/`**. En tête : `db` (83),
  `m` (41), `r` (39), `q` (34), `p` (33), `i` (18) — c'est-à-dire une majorité de
  cas que la clause autorise explicitement. Le rapport signal/bruit condamne
  l'approche.

La clause est donc écrite **pour être citée en revue**. C'est son unique mode
d'application, et c'est assumé.

### (b) L'anglais sans exception de vocabulaire

La case à cocher n°1 de l'issue — « trancher la liste des termes métier
autorisés en français » — se referme sur une **liste vide**.

Le domaine est déjà nommé en anglais partout où il compte, et le code a tranché
depuis longtemps : `bib_number` (et non `dossard`), `rank_overall` /
`rank_category` (et non `rang`), `total_time` (et non `temps`), `category`,
`club`, `event_name` / `event_date` / `event_type`. Retenir `dossard` ou
`epreuve` comme « termes métier sans équivalent naturel » reviendrait à
réintroduire en local un mot que le contrat public a déjà traduit.

La seule exception est **structurelle, pas lexicale** :

> Un identifiant **gelé par un contrat public** — colonne SQLAlchemy, champ de
> DTO Pydantic, clé JSON d'une réponse d'API, paramètre de query — reste tel quel
> tant que le contrat n'est pas migré.

Aujourd'hui, cela vise exactement trois sites, tous le même champ :
`athletes.nom` / `athletes.prenom` (`app/models/athlete.py`), leur écho DTO
(`app/schemas/athlete.py`) et le paramètre de repository
(`app/repositories/athlete_repository.py`). Ces noms traversent la DB, l'API et
`frontend/lib/types.ts` : les renommer est un chantier cross-stack (migration
Alembic **plus** le front), sans commune mesure avec le renommage mécanique de
symboles privés. Hors périmètre de cette règle, et hors périmètre de #88.

### (c) Dérogation bornée à la règle de transition

> Par dérogation à la règle de transition, la campagne de renommage de l'issue
> #88 est autorisée sur la liste close de lots ci-après, sous quatre critères
> **cumulatifs** :
>
> 1. **symboles privés, locaux ou paramètres uniquement** — jamais un symbole
>    gelé au titre de (b) ;
> 2. **zéro changement de comportement** — un lot qui corrige un bug au passage
>    est un lot mal découpé ;
> 3. les **tests suivent dans la même PR** que le module qu'ils couvrent ;
> 4. **un lot par PR**.
>
> Quand les lots sont faits, la dérogation s'éteint et « on ne réécrit rien »
> reprend pleinement.

Une liste close plutôt qu'un périmètre ouvert : le critère d'arrêt de la campagne
est ainsi **écrit**, pas laissé à l'appréciation de la prochaine session.

## 5. Les lots (liste close)

| # | Périmètre | Symboles (ordre de grandeur) |
| --- | --- | --- |
| **A** | **Transversal** — `echec_total` / `est_echec_total` / `epreuves` dans `services/{batch,rescrape_service,bulk_import_service,import_service}.py` et les constantes de `cli/reports.py` | ~18 |
| B | `app/cli/` — `reports`, `url_sources`, `progress`, `validators` | ~23 |
| C | `app/scrapers/raceresult.py` | ~42 |
| D | `app/scrapers/t2area.py` | ~34 |
| E | `app/scrapers/oktime.py` | ~21 |
| F | `app/scrapers/competitor.py` | ~14 |
| G | `app/scrapers/{chronoweb,chronoplace,sporthive}.py` | ~21 |
| H | Queue — `classify`, `wiclax`, `timepulse`, `klikego`, `klikego_platform` | ~11 |

Les décomptes ci-dessus reprennent le relevé **brut** de la §2, faux positifs
compris : la somme des lots vaut donc ~181 (les 184 relevés moins les 3 gelés),
non les ~172 nets. Les lots A et B se recoupent nominalement sur
`cli/reports.py`, et la §5.1 dit comment ce recouvrement se tranche.

Sont **hors liste** : `app/models/athlete.py`, `app/schemas/athlete.py`,
`app/repositories/athlete_repository.py` (gelés par (b)).

### 5.1 Pourquoi le lot A passe en premier

Ce n'est pas un détail d'ordonnancement. `echec_total` traverse **4 modules
d'`app` et 5 fichiers de test** :

```
app/services/rescrape_service.py       app/cli/reports.py
app/services/bulk_import_service.py    app/services/batch.py
tests/test_cli/test_commands.py        tests/test_services/test_rescrape_service.py
tests/test_services/test_batch.py      tests/test_services/test_bulk_import_service.py
tests/test_sporthive.py
```

Le prendre après le lot B ferait que deux PRs se marchent dessus sur
`cli/reports.py`. C'est précisément pourquoi l'issue écrit « un module **ou un
paquet** par PR » : certains symboles n'ont pas de module.

Partage exact entre A et B sur `cli/reports.py` : le lot **A** emporte les seuls
symboles de la famille `echec_total` (`EXIT_ECHEC_TOTAL`, `_LIGNE_ECHEC_TOTAL`),
le lot **B** prend tout le reste du module (`_ligne`, `_titre`,
`_lignes_compteurs`, `_lignes_echecs`, `_lignes_reconciliation`, `libelle`,
`lignes`, `rapport`, `valeur`).

### 5.2 Le lot A n'est pas purement mécanique

`est_echec_total(*, epreuves, errors)` devient `is_total_failure(*, events, errors)`
— et `event` est **déjà** employé dans le code pour ce que la CLI appelle
« épreuve » (`import_service.import_event`, `iter_import_event`,
`ScrapedResult.event_name`). Le vocabulaire tient donc, mais il se **vérifie**
lot par lot, il ne se présume pas : `Course` occupe déjà « course », et la
frontière épreuve / course est un point de vocabulaire que `AGENTS.md` documente
longuement (« la CLI compte des épreuves, jamais des courses »).

Corollaire pour chaque PR de la campagne : les **libellés affichés** de
`cli/reports.py` (« Épreuves ciblées », « Participants ajoutés ») restent en
français — c'est le point 3 de l'issue, et il est déjà couvert par le Principe I.
Le lot A ne touche que les **noms de symboles** qui les portent.

## 6. Outillage : `N` activé, et ce qu'il coûte

`select = ["E", "F", "I", "W", "UP", "B", "N"]`.

`N` ne couvre pas la clause (a) — il tient la **casse**, pas l'explicitness. On
l'active quand même parce qu'il est gratuit (3 violations sur tout le dépôt) et
qu'il ferme une porte voisine : `PAGE_SIZE` déclaré en local passait jusqu'ici.

| Règle | Site | Correction |
| --- | --- | --- |
| N818 | `app/scrapers/sporthive.py:222` | `_IncompleteRanking` → `_IncompleteRankingError` |
| N806 | `app/scrapers/sportinnovation.py:318` | `PAGE_SIZE` → `page_size` (variable locale) |
| N806 | `tests/conftest.py:26` | `TestingSessionLocal` → `testing_session_local` |

`_IncompleteRanking` est documenté dans `AGENTS.md` (« type privé rattrapé par la
boucle ») : le suffixe `Error` ne change ni sa portée ni son rôle, seulement son
nom — et `AGENTS.md` le mentionne, donc la mention suit.

## 7. Ce qui ne change pas

Le point 3 de l'issue est **déjà** couvert par le Principe I dans sa version
actuelle et n'est pas retouché. Restent en français : l'UI, les docstrings et
commentaires, les messages CLI, les libellés affichés, les documents produit et
les messages `DomainError` sérialisés vers le front. La règle porte sur les
**noms de symboles**, pas sur la langue du produit ni sur celle de la
documentation.

## 8. Vérification

- `uv run ruff check .` — vert avec `N` actif.
- `uv run pytest -m "not integration"` — vert (les 3 corrections touchent du code
  exécuté, dont `conftest.py`).
- La campagne n'étant pas dans cette branche, elle ne s'y vérifie pas. Chaque lot
  se vérifie sur son critère n°2 : la suite de tests passe **sans modification
  d'assertion de comportement**.
