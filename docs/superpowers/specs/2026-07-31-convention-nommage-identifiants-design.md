# Convention de nommage des identifiants backend — design

Issue : [#88](https://github.com/Triathlon-Club-Nantais/data-triathlon/issues/88)
(constat né de la revue de la PR #59).
Date : 2026-07-31.

## 1. Ce que la branche livre, et ce qu'elle ne livre pas

Cette branche livre **la règle et son outillage**. Elle ne renomme rien.

Les renommages partent ensuite en PRs distinctes, un lot par PR, selon les
lots de la §5. C'est le découpage que l'issue demande explicitement (« garder
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
contrat public — `athletes.nom` / `athletes.prenom`, première famille de (§4b).
**Soit ~172 symboles réellement à renommer**, avant retrait des quelques champs
de la seconde famille de (§4b) (`Reassignment.ancien/nouveau/fusion`,
`IdentiteReconciliee.ancien/nouveau/participations`), identifiée après ce
relevé : ils comptent dans les 184 mais n'en sont pas soustraits ici, `~172`
est donc une **borne haute**, pas le compte net final. Le lot I (§5) s'y
**ajoute** plutôt que de la recouper — son lexique n'a été identifié qu'après
ce relevé — donc `~172` n'en tient pas compte non plus. Le net final ne se lit
pas dans ce document : il s'établit **lot par lot**, aucun total consolidé
n'est promis ici. Les décomptes par module de la §5 sont donc des ordres de
grandeur : **chaque PR établit sa liste exacte**, elle ne la présume pas.

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
> DTO Pydantic, clé JSON d'une réponse d'API, clé de la charge `--json` de la
> CLI, paramètre de query — reste tel quel tant que le contrat n'est pas migré.

Aujourd'hui, cela vise **deux familles**, pas une seule. La première, trois
sites pour le même champ : `athletes.nom` / `athletes.prenom`
(`app/models/athlete.py`), leur écho DTO (`app/schemas/athlete.py`) et le
paramètre de repository (`app/repositories/athlete_repository.py`). Ces noms
traversent la DB, l'API et `frontend/lib/types.ts` : les renommer est un
chantier cross-stack (migration Alembic **plus** le front), sans commune
mesure avec le renommage mécanique de symboles privés. La seconde : les champs
`ancien` / `nouveau` / `fusion` de la dataclass `Reassignment`
(`app/services/import_service.py`), sérialisés verbatim dans la phase `done`
de la réponse SSE de `POST /api/v1/scrape/event/stream` et verrouillés par
`tests/test_api/test_scrape_api.py` ; et les champs `ancien` / `nouveau` /
`participations` de la dataclass `IdentiteReconciliee`
(`app/services/rescrape_service.py`), sérialisés dans la charge `--json` de
`rescrape-db` et documentés comme contractuels par `AGENTS.md`. Les deux
familles sont hors périmètre de cette règle, et hors périmètre de #88 : un lot
de la campagne peut toucher les modules qui les portent (`import_service.py`,
`rescrape_service.py` sont tous deux dans le lot A), mais jamais ces champs
eux-mêmes — cf. §5.1.

### (c) Dérogation bornée à la règle de transition

> Par dérogation à la règle de transition, la campagne de renommage de l'issue
> #88 est autorisée sur les lots ci-après, sous cinq critères **cumulatifs** :
>
> 1. **tout symbole interne au backend**, à l'exclusion de ceux gelés par un
>    contrat public au sens de (b) — la visibilité Python (`_` initial ou non)
>    n'a jamais été le critère, seule compte la traversée d'une frontière
>    (DB, HTTP, `--json`) ;
> 2. **zéro changement de comportement** — un lot qui corrige un bug au passage
>    est un lot mal découpé ;
> 3. les **tests suivent dans la même PR** que le module qu'ils couvrent ;
> 4. **un lot par PR** ;
> 5. les **mentions de symboles renommés dans `AGENTS.md` suivent dans la
>    même PR** — `specs/00*/` ne suit jamais, ce sont des artefacts
>    historiques de features livrées.
>
> La dérogation s'éteint quand `backend/app` ne porte plus d'identifiant
> français hors clause (b), vérifiable par re-scan — et non « quand les lots
> sont faits », un critère cochable mais aveugle à un module oublié au relevé
> ou ajouté entre-temps. Une fois éteinte, « on ne réécrit rien » reprend
> pleinement.

Le critère n°1 tel qu'initialement rédigé — « symboles privés, locaux ou
paramètres uniquement » — excluait littéralement de son propre périmètre les
tout premiers symboles de la campagne : `est_echec_total`, `IdentiteReconciliee`
(lot A), `charger_urls`, `valider_provider` (lot B) sont tous des symboles
**publics** de module, sans `_` initial. Le parenthétique disait la bonne
intention (exclure le gelé), l'énumération disait autre chose (exclure tout
symbole public). Le discriminant qui porte réellement la décision n'a jamais
été la visibilité Python, mais la traversée d'une frontière.

La liste des lots reste un **plan de découpage**, pas un périmètre ouvert :
l'ordre et le regroupement par module sont écrits, pas laissés à
l'appréciation de la prochaine session. Ce n'est en revanche plus elle qui
définit la fin de la dérogation — un relevé lexical n'est jamais garanti
exhaustif : le lexique du relevé initial (§2) ne contenait ni « espace », ni
« blanc », ni « normalise », ni « qualifiant », ni « sans_lien », ce qui a
laissé passer les ~7 symboles du lot I (§5) sous ce même relevé ; c'est
pourquoi l'extinction se vérifie sur l'état du code, pas sur une liste cochée.

## 5. Les lots (plan de découpage)

| # | Périmètre | Symboles (ordre de grandeur) |
| --- | --- | --- |
| **A** | **Transversal — deux familles.** `echec_total` / `est_echec_total` / `epreuves` dans `services/{batch,bulk_import_service,rescrape_service}.py` et les constantes de `cli/reports.py` ; et l'identité réconciliée — `_CLES_APPARIEMENT` / `_identite` et les variables locales de `_reconcile` dans `services/import_service.py`, plus les symboles homologues de `services/rescrape_service.py` et `cli/reports.py`. **Jamais** les champs `ancien` / `nouveau` / `fusion` / `participations` des dataclasses `Reassignment` et `IdentiteReconciliee`, gelés par (b) | ~18 |
| B | `app/cli/` — `reports`, `url_sources`, `progress`, `validators` | ~23 |
| C | `app/scrapers/raceresult.py` | ~42 |
| D | `app/scrapers/t2area.py` | ~34 |
| E | `app/scrapers/oktime.py` | ~21 |
| F | `app/scrapers/competitor.py` | ~14 |
| G | `app/scrapers/{chronoweb,chronoplace,sporthive}.py` | ~21 |
| H | Queue — `classify`, `wiclax`, `timepulse`, `klikego`, `klikego_platform` | ~11 |
| I | `app/core/club.py`, `app/scrapers/utils.py`, `app/services/sheet_source.py` | ~7 |

Les décomptes A à H reprennent le relevé **brut** de la §2, faux positifs
compris : leur somme vaut **~184**, soit le relevé brut lui-même — pas ~181
comme le calcul « 184 moins les 3 sites gelés de la première famille de (b) »
le suggérerait : les décomptes par lot sont des ordres de grandeur, pas une
partition exacte du relevé, et l'écart tient à cette imprécision plutôt qu'à
une mesure supplémentaire. Ce n'est en tout cas pas les ~172 nets. Les lots A
et B se recoupent nominalement sur `cli/reports.py`, et la §5.1 dit comment ce
recouvrement se
tranche. Le lot I n'est **pas** dans ces 184 : son lexique n'a été identifié
qu'après coup (§4c), il s'ajoute au décompte plutôt que de le recouper — c'est
la plus petite PR de la campagne, et la preuve que le relevé initial n'était
pas exhaustif.

Sont **hors liste** : `app/models/athlete.py`, `app/schemas/athlete.py`,
`app/repositories/athlete_repository.py` (gelés par (b), première famille).
La seconde famille de (b) — les champs `ancien` / `nouveau` / `fusion` /
`participations` — n'est en revanche **pas** hors liste au niveau fichier :
`import_service.py` et `rescrape_service.py` restent dans le lot A pour leurs
autres symboles, seuls ces champs de dataclass en sont exclus (§5.1).

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

`import_service.py` n'en fait **pas** partie — `echec_total` ne s'y trouve
nulle part. Il entre dans le lot A par la seconde famille : la réconciliation
d'identité. Ses seuls symboles français substantiels sont `_CLES_APPARIEMENT`,
`_identite`, et les variables locales de `_reconcile` (`ancien`, `nouveau`,
`athlete`, `cree`…) — jamais les champs `ancien` / `nouveau` / `fusion` de la
dataclass `Reassignment` qu'il définit, gelés par (b) parce qu'ils sont
sérialisés verbatim dans la réponse SSE de `POST /api/v1/scrape/event/stream`
et verrouillés par `tests/test_api/test_scrape_api.py`. Même partage sur
`rescrape_service.py` : ses symboles internes (résolution, appariement) sont
du lot A, les champs de `IdentiteReconciliee` n'en sont pas — ils partent dans
la charge `--json` de `rescrape-db`. Un exécutant qui ouvrirait `import_service.py` en cherchant `echec_total` ne
l'y trouverait pas, et renommer par réflexe les champs de `Reassignment`
casserait à la fois le critère n°2 de la dérogation (zéro changement de
comportement) et le Principe IV (contrats API et CLI stables).

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

**Glossaire de la campagne.** Le paragraphe précédent renvoie la frontière
épreuve / course à une vérification « lot par lot » — trop faible pour neuf PRs
successives, qui rejugeraient chacune la même question. La correspondance se
fixe donc une fois, ici, plutôt que de se rouvrir à chaque lot :
**`épreuve` → `event`**, **`course` → `race`**. `ScrapedResult.event_name` et
`Course.event_date` sont des noms **existants** que la campagne ne renomme
pas : `Course` est une table SQLAlchemy, gelée par (b) au même titre que
`athletes.nom` — les toucher est un chantier de migration, hors périmètre de
#88. C'est ce glossaire, et non une relecture au cas par cas, qui rend
praticable l'absence d'exception lexicale de la clause (b) : sans lui, chaque
lot devrait redécider si un `event` qu'il croise désigne l'épreuve ou la
course.

## 6. Outillage : `N` activé, et ce qu'il coûte

`select = ["E", "F", "I", "W", "UP", "B", "N"]`.

`N` ne couvre pas la clause (a) — il tient la **casse**, pas l'explicitness. On
l'active quand même parce qu'il est gratuit (3 violations sur tout le dépôt) et
qu'il ferme une porte voisine : `PAGE_SIZE` déclaré en local passait jusqu'ici.

| Règle | Site | Correction |
| --- | --- | --- |
| N818 | `app/scrapers/sporthive.py:222` | `_IncompleteRanking` → `_IncompleteRankingError` |
| N806 | `app/scrapers/sportinnovation.py:318` | `PAGE_SIZE` → `_PAGE_SIZE`, promue en **constante de module** (écart au texte ci-dessus : voir le plan, tâche 1) |
| N806 | `tests/conftest.py:26` | `TestingSessionLocal` → `session_factory` (écart au texte ci-dessus : `sessionmaker()` rend une fabrique, une translittération ne le dirait pas) |

`_IncompleteRanking` est documenté dans `AGENTS.md` (« type privé rattrapé par la
boucle ») : le suffixe `Error` ne change ni sa portée ni son rôle, seulement son
nom — et `AGENTS.md` le mentionne, donc la mention suit.

Le motif partagé par les trois scrapers paginés (`sporthive.py:77`,
`runnerbreizh.py:73`, `klikego_platform.py:27`) est la **constante de
module**, pas le commentaire qui l'accompagne : seuls `sporthive.py` et
`runnerbreizh.py` en portent un, `klikego_platform.py:27` n'en a aucun. Le
commentaire ajouté à `sportinnovation.py` (en anglais, cf. Principe I) le dit
en ces termes — « same pattern », pas « same comment ».

## 7. Ce qui ne change pas

Le point 3 de l'issue est **déjà** couvert par le Principe I dans sa version
actuelle et n'est pas retouché. Restent en français : l'UI, les docstrings et
commentaires **de règle métier**, les messages CLI, les libellés affichés, les
documents produit et les messages `DomainError` sérialisés vers le front. Les
docstrings **techniques** (contrats de fonction, effets de bord,
préconditions) et les commentaires purement techniques restent en anglais,
comme le Principe I le dit déjà : ce paragraphe ne le redit pas plus largement
qu'il ne le dit. La règle porte sur les **noms de symboles**, pas sur la
langue du produit ni sur celle de la documentation.

## 8. Vérification

- `uv run ruff check .` — vert avec `N` actif.
- `uv run pytest -m "not integration"` — vert (les 3 corrections touchent du code
  exécuté, dont `conftest.py`).
- La campagne n'étant pas dans cette branche, elle ne s'y vérifie pas. Chaque lot
  se vérifie sur son critère n°2 : la suite de tests passe **sans modification
  d'assertion de comportement**.
