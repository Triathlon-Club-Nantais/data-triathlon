# Convention de nommage des identifiants backend — plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Inscrire la convention de nommage des identifiants backend dans la
constitution (amendement v1.1.0), activer `pep8-naming` dans ruff, et propager la
nouvelle version partout où la constitution est référencée — **sans renommer
aucun identifiant français**.

**Architecture:** Trois tâches séquentielles et une de vérification. La tâche 1
touche du **code** (3 corrections mécaniques qu'exige l'activation de `N`) et
porte donc un vrai cycle de test. Les tâches 2 et 3 touchent des **documents de
règles** : leur vérification n'est pas un test unitaire mais une relecture
outillée (`grep` de cohérence des versions, absence de contradiction résiduelle).

**Tech Stack:** ruff 0.8.4+ (lint), pytest (suite existante ≈745 tests), uv,
Markdown (constitution, `AGENTS.md`, templates Spec Kit, skill `onboard`).

**Spec :** `docs/superpowers/specs/2026-07-31-convention-nommage-identifiants-design.md`
**Issue :** [#88](https://github.com/Triathlon-Club-Nantais/data-triathlon/issues/88)

## Global Constraints

- **Zéro renommage d'identifiant français dans cette branche.** La campagne part
  en PRs séparées, lot par lot. Un lot exécuté ici serait hors périmètre.
- **Zéro changement de comportement.** Les 3 corrections de la tâche 1 sont des
  renommages purs ; aucune assertion de test ne doit être modifiée.
- Toutes les commandes `uv run` s'exécutent **depuis `backend/`**.
- Langue : le contenu ajouté aux documents de règles est en **français** (ce sont
  des documents produit / process, Principe I). Les identifiants de code
  introduits sont en **anglais**.
- Commits : Conventional Commits, préfixe `chore:` ou `docs:`, suffixe `(#88)`.
- `specs/00*/` ne se touche **jamais** : ce sont des artefacts historiques de
  features livrées, ils enregistrent ce qui était vrai à leur date.

---

## File Structure

| Fichier | Rôle dans ce plan | Tâche |
| --- | --- | --- |
| `backend/pyproject.toml` | `[tool.ruff.lint] select` gagne `"N"` | 1 |
| `backend/app/scrapers/sporthive.py` | N818 — `_IncompleteRanking` → `_IncompleteRankingError` (6 sites) | 1 |
| `backend/app/scrapers/sportinnovation.py` | N806 — `PAGE_SIZE` local → `_PAGE_SIZE` module | 1 |
| `backend/tests/conftest.py` | N806 — `TestingSessionLocal` → `session_factory` | 1 |
| `AGENTS.md` | mention de `_IncompleteRanking` (l. 767) ; renvoi de version (l. 455) | 1, 3 |
| `.specify/memory/constitution.md` | Principe I amendé, footer version, Sync Impact Report | 2 |
| `.specify/templates/plan-template.md` | renvoi de version (l. 43) | 3 |
| `.specify/templates/tasks-template.md` | renvoi de version (l. 12) | 3 |
| `.claude/skills/onboard/SKILL.md` | renvoi de version (l. 399) | 3 |
| `.claude/skills/onboard/references/tour-backend.md` | renvoi de version (l. 37) | 3 |
| `.claude/skills/onboard/references/tour-fullstack.md` | renvoi de version (l. 26) | 3 |

---

## Task 1: Activer `pep8-naming` et corriger ses 3 violations

**Files:**
- Modify: `backend/pyproject.toml:50`
- Modify: `backend/app/scrapers/sporthive.py` (l. 34, 222, 546, 562, 584, 617)
- Modify: `backend/app/scrapers/sportinnovation.py:43-46, 318, 327`
- Modify: `backend/tests/conftest.py:26-27`
- Modify: `AGENTS.md:767`
- Test: la suite existante — `backend/tests/test_sporthive.py` couvre déjà
  `_IncompleteRanking` (rattrapé dans `scrape_event_all`), et
  `backend/tests/conftest.py` est la fixture de session de **toute** la suite.

**Interfaces:**
- Consumes: rien (première tâche).
- Produits: `_IncompleteRankingError` (exception privée de `sporthive.py`,
  signature inchangée : `(race_name: str, ordinal, read: int, announced: int)`) ;
  `sportinnovation._PAGE_SIZE: int = 250` (constante de module) ; `select` ruff
  incluant `"N"`. Aucune tâche ultérieure ne consomme ces symboles — la tâche 3
  ne touche que du Markdown.

**Note — deux écarts délibérés au texte du spec**, tous deux dans le sens de la
clause (a) que ce plan installe :
1. le spec écrivait `PAGE_SIZE` → `page_size` (local). Ce plan le **promeut en
   constante de module** `_PAGE_SIZE`, parce que c'est le motif déjà en place
   dans les trois autres scrapers paginés — `sporthive.py:77`,
   `runnerbreizh.py:73`, `klikego_platform.py:27` portent tous `_PAGE_SIZE` au
   niveau module. Le motif partagé est la **constante de module**, pas le
   commentaire qui l'accompagne : seuls `sporthive.py` et `runnerbreizh.py` en
   portent un, `klikego_platform.py:27` n'en a aucun — deux scrapers commentés
   sur trois. Même correction de N806, mais cohérente avec le dépôt.
2. le spec écrivait `TestingSessionLocal` → `testing_session_local`. Ce plan
   retient **`session_factory`** : `sessionmaker()` rend une fabrique, et
   `testing_session_local` est une translittération qui ne nomme pas ce que la
   variable porte — exactement ce que la clause (a) proscrit.

- [ ] **Step 1: Constater les 3 violations (le « test qui échoue »)**

```bash
cd backend && uv run ruff check --select N .
```

Attendu : **3 erreurs**, et exactement celles-ci —
`N818` sur `app/scrapers/sporthive.py:222`,
`N806` sur `app/scrapers/sportinnovation.py:318`,
`N806` sur `tests/conftest.py:26`.

Si le compte diffère, **arrêter** : le dépôt a bougé depuis le relevé, et la
liste des corrections ci-dessous n'est plus exhaustive.

- [ ] **Step 2: Établir la baseline verte de la suite**

```bash
cd backend && uv run pytest -m "not integration" -q
```

Attendu : vert. C'est la référence contre laquelle les renommages se vérifient ;
sans elle, un échec en Step 8 serait indiscernable d'un échec préexistant.

- [ ] **Step 3: N818 — renommer `_IncompleteRanking`**

Le nom apparaît 6 fois dans `sporthive.py` (une définition, une levée, un
`except`, trois mentions en docstring/commentaire) et une fois dans `AGENTS.md`.
Un seul passage `sed` avec `\b` : dans `_IncompleteRankingError`, le caractère
qui suit `Ranking` est `E` (un caractère de mot), donc `\b` ne matche pas et la
commande est idempotente.

```bash
cd /home/thomas_jarrier/Workspace/TCN/data-triathlon/.claude/worktrees/chore-backend-convention-de-nommage-identifiants
sed -i 's/_IncompleteRanking\b/_IncompleteRankingError/g' \
    backend/app/scrapers/sporthive.py AGENTS.md
grep -rn "_IncompleteRanking" backend/app backend/tests AGENTS.md
```

Attendu du `grep` : 7 lignes, **toutes** en `_IncompleteRankingError`, aucune en
`_IncompleteRanking` nu.

- [ ] **Step 4: N806 — promouvoir `PAGE_SIZE` en constante de module**

Dans `backend/app/scrapers/sportinnovation.py`, ajouter la constante sous
`API_BASE` (l. 43) :

```python
API_BASE = "https://sportinnovation.fr/api"
# Taille de page du format HTML. Motif partagé avec les autres scrapers paginés
# (sporthive, runnerbreizh, klikego_platform) : constante de module, pas locale.
_PAGE_SIZE = 250
```

Puis retirer la déclaration locale (l. 318) et pointer la constante (l. 327) :

```python
    all_rows: list[list[str]] = []
    race_name = ""
    col: dict[str, int] = {}

    for page in range(1, 20):  # safety cap at 20 pages = 5000 participants
        rn, rows, c = _fetch_html_results(event_id, client, search="", page=page)
        if not race_name:
            race_name, col = rn, c
        if not rows:
            break
        all_rows.extend(rows)
        if len(rows) < _PAGE_SIZE:
            break  # last page
```

- [ ] **Step 5: N806 — renommer `TestingSessionLocal`**

Dans `backend/tests/conftest.py`, l. 26-27 :

```python
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = session_factory()
```

- [ ] **Step 6: Activer `N` dans ruff**

Dans `backend/pyproject.toml`, l. 50 :

```toml
select = ["E", "F", "I", "W", "UP", "B", "N"]
```

- [ ] **Step 7: Vérifier que le lint passe (le « test qui passe »)**

```bash
cd backend && uv run ruff check .
```

Attendu : `All checks passed!`

- [ ] **Step 8: Vérifier que la suite est toujours verte**

```bash
cd backend && uv run pytest -m "not integration" -q
```

Attendu : vert, **avec le même décompte de tests qu'au Step 2**. Un décompte qui
change signale une collecte cassée, pas un renommage réussi.

- [ ] **Step 9: Commit**

```bash
cd /home/thomas_jarrier/Workspace/TCN/data-triathlon/.claude/worktrees/chore-backend-convention-de-nommage-identifiants
git add backend/pyproject.toml backend/app/scrapers/sporthive.py \
        backend/app/scrapers/sportinnovation.py backend/tests/conftest.py AGENTS.md
git commit -m "chore(backend): active pep8-naming dans ruff (#88)

Trois violations, toutes mécaniques : _IncompleteRanking gagne le suffixe
Error attendu par N818, PAGE_SIZE passe en constante de module _PAGE_SIZE
(le motif des trois autres scrapers paginés), et TestingSessionLocal devient
session_factory — sessionmaker rend une fabrique.

N ne couvre pas la clause d'explicitness du Principe I (ruff n'a aucune
règle de longueur) : il tient la casse, et c'est tout ce qu'on lui demande."
```

---

## Task 2: Amender le Principe I de la constitution (v1.1.0)

**Files:**
- Modify: `.specify/memory/constitution.md` — bloc Sync Impact Report (l. 1-46),
  Principe I (insertion après l. 77, réécriture l. 89-101), footer (l. 253)

**Interfaces:**
- Consumes: `_PAGE_SIZE` et `session_factory` de la tâche 1 n'apparaissent pas
  ici ; la tâche 2 est indépendante du code.
- Produces: la chaîne **`v1.1.0`** que la tâche 3 propage, et le nom de fichier
  de spec cité dans la dérogation.

**Procédure de gouvernance** (§Governance, l. 223-241) — les cinq étapes sont
satisfaites : proposition = issue #88 (ouverte par tjarrier) ; approbation =
accord explicite du mainteneur en session de brainstorming ; bump **MINOR** car
« élargissement substantiel d'une règle existante » ; propagation = tâche 3 ;
Sync Impact Report = Step 3 ci-dessous.

- [ ] **Step 1: Insérer les deux clauses de règle dans le Principe I**

Après le paragraphe `**English** — …` (qui se termine l. 77 par « titres et corps
de PR à visée technique. ») et **avant** `**Cas mixte — les \`DomainError\`**`,
insérer :

```markdown
**Explicitness des identifiants** : un identifiant nomme ce qu'il porte. Les
noms d'une ou deux lettres sont réservés aux liaisons dont la portée tient
sous les yeux — variable de compréhension, variable de boucle, paramètre de
lambda, et `db` (session SQLAlchemy, idiomatique dans tout le projet). Hors
de là, le nom est un mot.

Cette clause **n'est pas automatisable**, et le principe le dit plutôt que de
laisser croire à un filet qui n'existe pas. ruff n'a aucune règle de longueur
ou d'explicitness : `pep8-naming` (`N`, activé) ne contrôle que la **casse**,
et `E741` ne couvre que `l`, `O`, `I`. Un lint maison sur la seule longueur
marquerait **431 occurrences dans `backend/app`** (48 identifiants distincts,
dont `db` 83 fois, `i` 18 fois) — une majorité de cas que la clause autorise
explicitement. Elle s'applique donc **en revue de code**, et c'est assumé.

**Pas d'exception de vocabulaire métier** : l'anglais est la règle, sans liste
de termes français dérogatoires. Le domaine est déjà nommé en anglais partout
où il compte — `bib_number` et non `dossard`, `rank_overall` / `rank_category`
et non `rang`, `total_time` et non `temps`, `category`, `club`, `event_name` /
`event_date` / `event_type`. Réintroduire un de ces mots en local reviendrait
à défaire ce que le contrat public a déjà traduit.

La seule exception est **structurelle, pas lexicale** : un identifiant **gelé
par un contrat public** — colonne SQLAlchemy, champ de DTO Pydantic, clé JSON
d'une réponse d'API, paramètre de query — reste tel quel tant que le contrat
n'est pas migré. Aujourd'hui cela vise exactement un champ, à trois endroits :
`athletes.nom` / `athletes.prenom` (`backend/app/models/athlete.py`), leur
écho DTO (`backend/app/schemas/athlete.py`) et le paramètre de repository
(`backend/app/repositories/athlete_repository.py`) — ces noms traversent la
DB, l'API et `frontend/lib/types.ts`. Les renommer est un chantier cross-stack
(migration Alembic **plus** le front), sans commune mesure avec le renommage
d'un symbole privé, et hors de ce principe.
```

- [ ] **Step 2: Ajouter la dérogation bornée et compléter le Rationale**

Remplacer le bloc `**Règle de transition**` + `**Rationale**` (l. 89-101) par :

```markdown
**Règle de transition** : le code et la doc existants sont en français
mélangé — `AGENTS.md`, docstrings, commits historiques. **On ne réécrit
rien**. La règle s'applique aux **nouveaux** ajouts et à toute réécriture
substantielle d'un fichier. Un fichier français touché pour un fix ciblé
reste français dans le patch.

**Dérogation bornée — campagne #88** : par dérogation à l'alinéa précédent, le
renommage des identifiants français de `backend/app` est autorisé sur la
**liste close** de lots ci-dessous, sous quatre critères **cumulatifs** :
symboles **privés, locaux ou paramètres** uniquement (jamais un symbole gelé
par contrat public) ; **zéro changement de comportement** ; les tests suivent
dans la **même PR** que le module qu'ils couvrent ; **un lot par PR**.

| Lot | Périmètre |
| --- | --- |
| A | transversal — deux familles : `echec_total` (`batch`, `bulk_import_service`, `rescrape_service`, `cli/reports`) et l'identité réconciliée `ancien`/`nouveau`/`fusion` (`import_service`, `rescrape_service`, `cli/reports`), **hors** les champs de dataclass gelés par (b) |
| B | `app/cli/` — `reports`, `url_sources`, `progress`, `validators` |
| C | `app/scrapers/raceresult.py` |
| D | `app/scrapers/t2area.py` |
| E | `app/scrapers/oktime.py` |
| F | `app/scrapers/competitor.py` |
| G | `app/scrapers/{chronoweb,chronoplace,sporthive}.py` |
| H | `app/scrapers/{classify,wiclax,timepulse,klikego,klikego_platform}.py` |

Le lot **A passe avant B**, et ce n'est pas un détail d'ordonnancement :
`echec_total` traverse quatre modules d'`app` et cinq fichiers de test, dont
`cli/reports.py`. Pris après B, deux PRs se marcheraient dessus sur ce fichier.

Quand ces huit lots sont faits, la dérogation **s'éteint** et l'alinéa
précédent reprend pleinement. Design et relevé chiffré :
`docs/superpowers/specs/2026-07-31-convention-nommage-identifiants-design.md`.

**Rationale** : le projet sert un club francophone (le métier est en
français), mais son outillage est anglophone (framework docs, Sentry,
Copilot, revue de code par un LLM). Séparer les deux évite la traduction
implicite dans chaque commit et rend la recherche full-text (`grep`,
Sentry queries) prévisible. Ne pas migrer l'existant : le coût de la
réécriture massive dépasse le bénéfice, et le principe III (TDD) ne peut
tolérer un patch de 200 fichiers non testés. Le découpage en lots de la
dérogation ci-dessus **répond** précisément à cette objection plutôt que de
la contourner : aucun lot n'est un patch de 200 fichiers, et chacun se
vérifie sur la suite de tests existante, sans modification d'assertion de
comportement.
```

- [ ] **Step 3: Réécrire le Sync Impact Report**

Remplacer intégralement le bloc HTML commenté en tête de fichier (l. 1-46) par :

```markdown
<!--
Sync Impact Report — Constitution v1.1.0
========================================
Version change    : 1.0.0 → 1.1.0
Rationale         : MINOR — « élargissement substantiel d'une règle existante »
  (Governance §3). Le Principe I gagne trois clauses : explicitness des
  identifiants, absence d'exception de vocabulaire métier (l'exception est
  structurelle — contrat public gelé), et une dérogation bornée à la règle de
  transition autorisant la campagne de renommage de l'issue #88.
  Proposition : issue #88 (tjarrier). Approbation : mainteneur, 2026-07-31.
Modified principles : I. Langue — 3 clauses ajoutées, Rationale complété.
Added sections    : (aucune)
Removed sections  : (aucun)
Drafting notes :
  - La campagne #88 était en contradiction frontale avec la règle de transition
    du Principe I (« On ne réécrit rien »). Résolue par amendement de la
    constitution plutôt que par une règle concurrente dans AGENTS.md : la
    constitution prime, une règle concurrente aurait recréé la divergence que
    le rapport v1.0.0 signalait déjà.
  - La liste de « termes métier autorisés en français » demandée par #88 est
    close sur l'ensemble **vide**. Ce n'est pas un refus de trancher : le code
    a déjà tranché (bib_number, rank_overall, total_time, event_*).
  - La clause d'explicitness est déclarée non automatisable, mesures à l'appui
    (ruff n'a aucune règle de longueur ; 431 occurrences dans backend/app dont
    une majorité légitimes). Écrire un lint ici aurait produit du bruit.
Templates alignés :
  ✅ .specify/templates/plan-template.md   — la grille des 6 principes est en
     place (follow-up v1.0.0 résolu) ; seul le renvoi de version est à bumper.
  ✅ .specify/templates/spec-template.md   — aucun ajustement nécessaire.
  ✅ .specify/templates/tasks-template.md  — les 4 mentions "Tests are OPTIONAL"
     ont été retirées (follow-up v1.0.0 résolu) ; renvoi de version à bumper.
  ✅ AGENTS.md                              — la règle langue renvoie déjà au
     Principe I (follow-up v1.0.0 résolu). Renvoi de version à bumper, et la
     phrase de transition doit désormais nommer la dérogation.
Follow-up TODOs   : (aucun — les trois follow-ups de la v1.0.0 sont résolus)
-->
```

- [ ] **Step 4: Mettre à jour le footer de version**

Dernière ligne du fichier :

```markdown
**Version**: 1.1.0 | **Ratified**: 2026-07-27 | **Last Amended**: 2026-07-31
```

`Ratified` **ne change pas** : c'est la date de première ratification, pas celle
du dernier amendement.

- [ ] **Step 5: Vérifier la cohérence interne du fichier**

```bash
cd /home/thomas_jarrier/Workspace/TCN/data-triathlon/.claude/worktrees/chore-backend-convention-de-nommage-identifiants
grep -n "1\.0\.0\|1\.1\.0" .specify/memory/constitution.md
grep -c "Règle de transition" .specify/memory/constitution.md
```

Attendu du premier `grep` : les mentions `1.0.0` restantes ne doivent apparaître
que dans le Sync Impact Report **en tant qu'historique** (« Version change :
1.0.0 → 1.1.0 »). Le footer et toute règle active portent `1.1.0`.
Attendu du second : **2** — le Principe I et le Principe II en ont chacun une ;
la dérogation ne doit pas en avoir créé une troisième.

- [ ] **Step 6: Commit**

```bash
git add .specify/memory/constitution.md
git commit -m "docs(constitution): amende le Principe I en v1.1.0 (#88)

Trois clauses : explicitness des identifiants (déclarée non automatisable,
ruff n'ayant aucune règle de longueur), anglais sans exception lexicale
— la liste de termes métier FR demandée par #88 est vide, seule fait
exception un identifiant gelé par un contrat public —, et une dérogation
bornée à la règle de transition, sur une liste close de huit lots.

La campagne #88 contredisait frontalement « On ne réécrit rien ». On amende
la constitution plutôt que d'écrire une règle concurrente dans AGENTS.md :
la constitution prime, la contradiction aurait survécu."
```

---

## Task 3: Propager la version v1.1.0

**Files:**
- Modify: `AGENTS.md:455-462`
- Modify: `.specify/templates/plan-template.md:43`
- Modify: `.specify/templates/tasks-template.md:12`
- Modify: `.claude/skills/onboard/SKILL.md:399`
- Modify: `.claude/skills/onboard/references/tour-backend.md:37`
- Modify: `.claude/skills/onboard/references/tour-fullstack.md:26`

**Interfaces:**
- Consumes: la chaîne `v1.1.0` produite par la tâche 2.
- Produces: rien (tâche terminale sur le contenu).

**Ce qui ne se touche pas, et pourquoi :** `specs/001-onboard-skill/`,
`specs/003-dashboard-rank-selector/`, `specs/004-sporthive-scraper/` et
`specs/005-chronoweb-scraper/` citent aussi `v1.0.0`. Ce sont des **artefacts
historiques de features livrées** : ils enregistrent la version contre laquelle
la feature a été planifiée. Les réécrire falsifierait le dossier. Cette règle est
la même que celle qui interdit de renuméroter une feature après coup.

- [ ] **Step 1: Recenser les sites à corriger**

```bash
cd /home/thomas_jarrier/Workspace/TCN/data-triathlon/.claude/worktrees/chore-backend-convention-de-nommage-identifiants
grep -rn "v1\.0\.0\|constitution v1\.0\.0" --include='*.md' \
     AGENTS.md .specify/templates .claude/skills
```

Attendu : **6 lignes**, une par fichier — `AGENTS.md:455`,
`plan-template.md:43`, `tasks-template.md:12`, `SKILL.md:399`,
`tour-backend.md:37`, `tour-fullstack.md:26`. Si le compte diffère, corriger la
liste de cette tâche avant de continuer.

Vérifié au moment d'écrire ce plan : `v1.0.0` est **la seule** chaîne de version
sémantique présente dans ces six fichiers, à raison d'une occurrence chacun. Le
`sed` global du Step 3 est donc sans risque de dégât collatéral.

- [ ] **Step 2: `AGENTS.md` — version ET phrase de transition**

C'est le seul site où le changement n'est pas qu'un numéro : la phrase « on ne
réécrit pas l'existant » devient fausse telle quelle. Remplacer l. 455-462 par :

```markdown
- **Langue** : suit le Principe I de la constitution v1.1.0
  (`.specify/memory/constitution.md`) — **français** pour ce qui est
  visible utilisateur ou métier (UI, messages d'erreur affichés, docs
  produit, commentaires de règle métier, messages `DomainError`
  sérialisés vers le front) ; **English** pour la couche technique
  invisible (identifiants, tests, docstrings techniques, logs
  Sentry/Datadog, préfixes Conventional Commits). Un identifiant nomme
  ce qu'il porte : les noms d'une ou deux lettres sont réservés aux
  liaisons dont la portée tient sous les yeux (compréhension, boucle,
  lambda, `db`). Règle de transition : on ne réécrit pas l'existant, la
  règle s'applique aux nouveaux ajouts — **à une dérogation près**, la
  campagne de renommage de l'issue #88, bornée à une liste close de huit
  lots énumérée dans le Principe I.
```

- [ ] **Step 3: Les cinq renvois de version restants**

Un seul passage, sur les seuls fichiers listés — jamais `specs/` :

```bash
sed -i 's/v1\.0\.0/v1.1.0/g' \
    .specify/templates/plan-template.md \
    .specify/templates/tasks-template.md \
    .claude/skills/onboard/SKILL.md \
    .claude/skills/onboard/references/tour-backend.md \
    .claude/skills/onboard/references/tour-fullstack.md
```

- [ ] **Step 4: Vérifier qu'il ne reste aucun renvoi actif en v1.0.0**

```bash
grep -rn "v1\.0\.0" --include='*.md' AGENTS.md .specify .claude/skills
```

Attendu : **une seule ligne**, celle du Sync Impact Report de la constitution
(« Version change : 1.0.0 → 1.1.0 »), qui est de l'historique et doit rester.

- [ ] **Step 5: Vérifier qu'aucune contradiction ne subsiste**

```bash
grep -rn "on ne réécrit pas l'existant\|On ne réécrit" AGENTS.md .specify/memory/constitution.md
```

Attendu : **2 lignes**, l'une dans `AGENTS.md` et l'autre dans la constitution,
et **chacune** doit être suivie de la mention de la dérogation. Une occurrence
nue est la contradiction que ce plan existe pour fermer.

- [ ] **Step 6: Commit**

```bash
git add AGENTS.md .specify/templates .claude/skills
git commit -m "docs: propage la constitution v1.1.0 (#88)

Les cinq renvois actifs (deux templates Spec Kit, trois fichiers du skill
onboard) et AGENTS.md. Ce dernier n'est pas qu'un numéro : sa phrase « on
ne réécrit pas l'existant » devenait fausse sans la mention de la
dérogation, et c'est le fichier lu à chaque session.

specs/00*/ n'est pas touché : ces artefacts enregistrent la version contre
laquelle leur feature a été planifiée."
```

---

## Task 4: Vérification de fin de branche

**Files:** aucun (lecture seule).

**Interfaces:**
- Consumes: l'état final des tâches 1 à 3.
- Produces: rien.

- [ ] **Step 1: Lint et tests**

```bash
cd backend && uv run ruff check . && uv run pytest -m "not integration" -q
```

Attendu : `All checks passed!` puis suite verte, au même décompte qu'au Step 2 de
la tâche 1.

- [ ] **Step 2: Vérifier qu'aucun identifiant français n'a été renommé**

C'est la contrainte globale n°1 ; elle se vérifie, elle ne se suppose pas.

```bash
cd /home/thomas_jarrier/Workspace/TCN/data-triathlon/.claude/worktrees/chore-backend-convention-de-nommage-identifiants
git diff --stat main -- backend/app backend/tests
```

Attendu : **trois fichiers seulement** — `app/scrapers/sporthive.py`,
`app/scrapers/sportinnovation.py`, `tests/conftest.py`. Tout autre fichier de
`backend/app` ou `backend/tests` dans ce diff signale qu'un lot de la campagne a
fuité dans cette branche.

- [ ] **Step 3: Vérifier que les trois clauses sont bien dans la constitution**

```bash
grep -n "Explicitness des identifiants\|Pas d'exception de vocabulaire métier\|Dérogation bornée" \
     .specify/memory/constitution.md
```

Attendu : **3 lignes**, une par clause.

- [ ] **Step 4: Relire le diff complet**

```bash
git diff main --stat
```

Attendu : **13 fichiers** — 4 de code/config (`pyproject.toml`, `sporthive.py`,
`sportinnovation.py`, `conftest.py`), 7 de documentation (`AGENTS.md`,
`constitution.md`, les deux templates Spec Kit, les trois fichiers du skill
`onboard`), et les 2 fichiers `docs/superpowers/` (spec et plan) commités avant
la tâche 1.

---

## Suites — hors de cette branche

- **Les huit lots de la campagne** (A → H, dans cet ordre pour A et B), un par
  PR, sous les quatre critères de la dérogation. Le lot A demande une vigilance
  particulière : `est_echec_total(*, epreuves, errors)` devient
  `is_total_failure(*, events, errors)`, et la frontière épreuve / course est un
  point de vocabulaire que `AGENTS.md` documente longuement. À vérifier lot par
  lot, jamais à présumer.
- **Cocher la case n°1 de l'issue #88** (« trancher la liste des termes métier »)
  et y résumer la réponse : liste vide, exception structurelle. Action
  sortante — à faire valider avant émission.
