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

# Constitution — data-triathlon

Cette constitution fixe les règles **non-négociables** du projet. Elle est
injectée dans chaque commande `/speckit-*`. Elle prime sur toute autre pratique.
Le détail opérationnel (commandes, architecture) reste dans `AGENTS.md` ; la
constitution ne le duplique pas — elle en extrait les invariants.

## Core Principles

### I. Langue : français pour le métier, English pour la technique

La séparation est structurelle, pas stylistique.

**Français** — tout ce qui est visible par l'utilisateur ou qui porte du
vocabulaire métier : UI, libellés de champs, messages d'erreur rendus à
l'utilisateur (front, réponses API destinées à l'affichage), textes CLI vus
par un opérateur (rapports, résumés `emit_outcome`), documents produit
(`spec.md`, `README.md` d'accueil), commentaires de code qui expliquent une
règle métier (« un finisher RaceResult porte un suffixe », « TCN = liste
blanche de libellés »).

**English** — tout ce qui est technique et invisible à l'utilisateur : noms
d'identifiants (variables, fonctions, classes, modules, endpoints, colonnes
DB), noms de tests, docstrings **techniques** (contrats de fonction, effets
de bord, préconditions), messages de log techniques (`logger.info`,
`logger.error`) destinés à Sentry/Datadog, commits (Conventional Commits :
`feat:`, `fix:`, `refactor:` — le sujet peut ensuite être en anglais **ou**
français selon qu'il décrit une intention technique ou métier), messages
d'erreur d'exception interne (`raise ValueError("...")`), noms de branche,
titres et corps de PR à visée technique.

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
d'une réponse d'API, clé de la charge `--json` de la CLI (`emit_outcome`),
paramètre de query — reste tel quel tant que le contrat n'est pas migré.
Aujourd'hui cela vise deux familles, non une seule. La première :
`athletes.nom` / `athletes.prenom` (`backend/app/models/athlete.py`), leur
écho DTO (`backend/app/schemas/athlete.py`) et le paramètre de repository
(`backend/app/repositories/athlete_repository.py`) — ces noms traversent la
DB, l'API et `frontend/lib/types.ts` ; les renommer est un chantier cross-stack
(migration Alembic **plus** le front), sans commune mesure avec le renommage
d'un symbole privé. La seconde : les champs `ancien` / `nouveau` / `fusion` de
la dataclass `Reassignment` (`backend/app/services/import_service.py`),
sérialisés verbatim dans la phase `done` de la réponse SSE de
`POST /api/v1/scrape/event/stream` et verrouillés par
`backend/tests/test_api/test_scrape_api.py` ; et les champs `ancien` /
`nouveau` / `participations` de la dataclass `IdentiteReconciliee`
(`backend/app/services/rescrape_service.py`), sérialisés dans la charge
`--json` de `rescrape-db` et documentés comme contractuels par `AGENTS.md`.
Ces deux familles sont hors de ce principe au même titre : les renommer casse
un contrat verrouillé par test ou documenté comme stable, tout comme les
renommer casserait la DB et le front pour la première famille.

**Cas mixte — les `DomainError`** : les exceptions de
`backend/app/core/exceptions.py` (`InvalidUrlError`,
`ProviderNotSupportedError`, `ScraperError`, `NotFoundError`,
`DuplicateError`) sont **à la fois** des exceptions internes **et** du texte
utilisateur : leurs messages sont sérialisés dans `{"detail": ...}` par
`register_exception_handlers` et ré-affichés verbatim par le front
(`frontend/lib/api/client.ts`). Ces messages suivent la règle **« français
utilisateur »**, pas la règle « English technique ». Un nouveau
`raise ScraperError("...")` prend donc un message en français.

**Règle de transition** : le code et la doc existants sont en français
mélangé — `AGENTS.md`, docstrings, commits historiques. **On ne réécrit
rien**. La règle s'applique aux **nouveaux** ajouts et à toute réécriture
substantielle d'un fichier. Un fichier français touché pour un fix ciblé
reste français dans le patch.

**Dérogation bornée — campagne #88** : par dérogation à l'alinéa précédent, le
renommage des identifiants français de `backend/app` est autorisé sur les lots
ci-dessous, sous cinq critères **cumulatifs** : **tout symbole interne au
backend**, à l'exclusion de ceux gelés par un contrat public au sens de la
clause (b) — la visibilité Python (`_` initial ou non) n'a jamais été le
critère, seule compte la traversée d'une frontière (DB, HTTP, `--json`) ;
**zéro changement de comportement** ; les tests suivent dans la **même PR**
que le module qu'ils couvrent ; **un lot par PR** ; et **les mentions de
symboles renommés dans `AGENTS.md` suivent dans la même PR** — `specs/00*/`,
lui, ne suit jamais : ce sont des artefacts historiques de features livrées,
qu'on ne réécrit pas après coup.

| Lot | Périmètre |
| --- | --- |
| A | transversal — **deux familles** : `echec_total` (`services/{batch,bulk_import_service,rescrape_service}.py` et les constantes homonymes de `cli/reports.py`) et l'identité réconciliée (`_CLES_APPARIEMENT` / `_identite` et les variables locales de `_reconcile` dans `services/import_service.py`, plus les symboles homologues de `services/rescrape_service.py` et `cli/reports.py`) — **jamais** les champs `ancien` / `nouveau` / `fusion` / `participations` des dataclasses `Reassignment` et `IdentiteReconciliee`, gelés par (b) |
| B | `app/cli/` — `reports`, `url_sources`, `progress`, `validators` |
| C | `app/scrapers/raceresult.py` |
| D | `app/scrapers/t2area.py` |
| E | `app/scrapers/oktime.py` |
| F | `app/scrapers/competitor.py` |
| G | `app/scrapers/{chronoweb,chronoplace,sporthive}.py` |
| H | `app/scrapers/{classify,wiclax,timepulse,klikego,klikego_platform}.py` |
| I | `app/core/club.py`, `app/scrapers/utils.py`, `app/services/sheet_source.py` — angle mort du relevé initial, dont le lexique français ne couvrait ni « espace », ni « blanc », ni « normalise », ni « qualifiant », ni « sans_lien » (~7 symboles) |

Le lot **A passe avant B**, et ce n'est pas un détail d'ordonnancement :
`echec_total` traverse quatre modules d'`app` et cinq fichiers de test, dont
`cli/reports.py`. Pris après B, deux PRs se marcheraient dessus sur ce fichier.

Cette table est un **plan de découpage**, pas la définition de la fin : la
dérogation s'éteint quand `backend/app` ne porte plus d'identifiant français
hors clause (b) — un critère **vérifiable par re-scan**, et non « quand ces
lots sont faits », qui est cochable mais aveugle à un module oublié au relevé
ou ajouté entre-temps. C'est cet angle mort du relevé initial qui a produit le
lot I. Une fois éteinte, l'alinéa précédent reprend pleinement. Design et
relevé chiffré :
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

### II. Architecture en couches, sens unique du flux

Le backend respecte le sens unique **`api → services → repositories → DB`**.
Aucune couche ne saute la suivante et aucune ne remonte : un router n'ouvre
pas de session SQLAlchemy, un service ne construit pas de requête SQL, un
repository ne renvoie pas de DTO Pydantic. La **seule** couche autorisée à
toucher `Session` est `app/repositories/`. Une règle projet critique
— l'identification club (`is_tcn` / `tcn_clause`) — vit dans **un seul**
endroit : `app/core/club.py`. La réimplémenter ailleurs (front, scraper, autre
service) est interdit.

**Règle de transition** : deux services touchent aujourd'hui `Session` et
sont **exemptés nommément** — `app/services/cache.py` (`db.query(Participation.id)`
dans `is_fresh`) et `app/services/reclassify.py`
(`db.query(Course).options(load_only(...))`). Toute **nouvelle** occurrence
en dehors d'`app/repositories/` est interdite. La résorption de ces deux
exceptions (déplacement vers un repository dédié) est un chantier hors PR
courante, à ouvrir en ticket suiveur.

**Rationale** : trois listes divergentes du critère club ont fait compter tout
libellé « nantais » comme TCN (#76). La monogamie des responsabilités par
couche est la seule garde qui tienne dans la durée.

### III. TDD sans réseau (NON-NÉGOCIABLE)

Toute nouvelle logique métier est **précédée** d'un test qui échoue puis passe
au vert. Les tests unitaires n'appellent **jamais** le réseau réel : la
convention actuelle est un monkeypatch de `httpx.Client` (cf.
`backend/tests/test_klikego.py`) ou des helpers `_fetch_*`
(`backend/tests/test_raceresult.py`), avec les payloads capturés sous
`tests/fixtures/`. Le réseau réel est isolé derrière le marker `integration`
(déclaré dans `backend/pyproject.toml`), jamais lancé par défaut. Une PR
n'entre pas sans `uv run pytest -m "not integration"` vert.

**Rationale** : les scrapers dépendent de sites tiers instables ; sans mocks,
la suite devient un baromètre de disponibilité web plutôt qu'un filet de
sécurité pour le code. Cf. les fixtures existantes de chaque provider.

### IV. Contrats API et CLI stables

L'API HTTP est versionnée sous `/api/v1`. Un changement de contrat public
(champ retiré, sémantique inversée d'un paramètre, code de retour modifié)
motive une v2 — jamais une modification silencieuse de v1. La CLI (`app.cli`)
respecte deux contrats de sortie stables : **stdout parsable** (avec `--json`,
uniquement la ligne JSON ; sans, le rapport texte), **stderr pour la
progression et les logs**. Codes de sortie : `0` succès (même partiel ou « rien
à faire »), `1` échec total, `2` erreur d'usage, `130` Ctrl-C. Une commande qui
mélange rapport texte et JSON sur stdout casse ce contrat.

**Rationale** : la CLI est pipée dans des scripts (rejeu d'échecs, crons), et
l'API dans un front en prod. Un contrat implicite qui bouge à chaque commit
est plus coûteux qu'une v2 explicite.

### V. Neutralité par défaut des paramètres transverses

Les paramètres transverses aux endpoints de lecture (`scope`, `federal_only`,
`seasons`) ont un **défaut neutre côté API** — non filtré. Ce sont les
appelants (dashboard, page club) qui les activent explicitement, jamais l'API
qui les impose. Un défaut « intelligent » à `true` (ex : `federal_only=true`
par défaut) ampute silencieusement tout futur appelant et rompt l'orthogonalité
des filtres.

**Rationale** : la portée club **était** un texte libre passé en sous-chaîne,
et un `%nantais%` a compté tout Nantes comme TCN (#76). Le remède structurel
est un paramètre explicite avec un défaut neutre — pas un autre défaut
implicite.

### VI. Simplicité et YAGNI

Un fix ne traîne pas de refacto ; une feature n'ajoute pas d'abstraction
« au cas où ». Le code par défaut n'a **pas** de commentaires — un identifiant
bien nommé remplace un commentaire tautologique. Un commentaire n'est justifié
que par un « pourquoi » non-évident : contrainte cachée, invariant subtil,
contournement d'un bug tiers. Trois lignes similaires valent mieux qu'une
abstraction prématurée.

**Rationale** : le domaine (scraping de sites tiers hétérogènes) fabrique
naturellement des cas particuliers ; multiplier les abstractions rend chaque
correctif plus coûteux à ancrer. Cf. la trace de `AGENTS.md` sur `is_tcn`,
`build_splits`, la registre Protocol des scrapers — toutes des consolidations
faites *après* que les cas particuliers ont émergé, pas avant.

## Additional Constraints

- **Stack** : Python 3.13, uv, FastAPI, SQLAlchemy 2.0 (sync), Pydantic v2,
  Alembic ; côté front, Next.js 16 App Router, TypeScript strict, Tailwind,
  shadcn/ui. Ne pas dévier sans justification explicite dans `plan.md`.
- **Schéma DB** : toute modification de modèle passe par
  `uv run alembic revision --autogenerate` puis relecture manuelle de la
  révision générée. Jamais de `Base.metadata.create_all()` en dehors des
  fixtures de test (`backend/tests/conftest.py`,
  `backend/tests/test_cli/test_logging.py` ; cf. `tests/test_migrations.py`
  qui documente pourquoi les fixtures contournent Alembic). Le reset dev
  (`scripts/reset_db.py`) passe par `drop_all` puis `alembic upgrade head`.
- **Temps** : toujours des strings normalisées (`"01:23:45"`) via
  `app/scrapers/utils.py`. Pas de `timedelta` en base ni dans les DTO.
- **Modèle normalisé** : `Athlete` (unique par nom/prénom/DDN), `Course`
  (unique par name/event_date/event_type), `Participation` (unique par
  course_id/bib_number). Les splits sont un JSON, pas des colonnes figées.
- **Cache TTL** : jamais de re-scrape si `is_fresh(course)` renvoie `True`.
  Une commande qui court-circuite le cache doit le faire par `force=True`
  explicite, pas par contournement.

## Development Workflow

- **Cycle Speckit** pour les vraies features : `/speckit-specify` →
  `/speckit-clarify` → gate → `/speckit-plan` → gate → `/speckit-tasks` →
  `/speckit-analyze` → exécution.
- **Workflow vibe** pour bugfix / typo / 1-2 fichiers : pas de dossier
  `specs/`. Test rouge → correctif → vérification.
- **Commits** : Conventional Commits (`feat:`, `fix:`, `refactor:`, `docs:`,
  `test:`, `chore:`). Un commit = un changement cohérent. Pas d'`--amend` sur
  un commit poussé.
- **PR** : titre en Conventional Commits, description en français, section
  « Test plan » avec commandes de vérification (`uv run pytest -m "not
  integration"`, `npm test`, `task lint`).
- **CI** : les tests unitaires backend et frontend doivent être verts avant
  merge. Les tests `integration` (réseau réel) ne bloquent pas la PR mais sont
  lancés localement avant tout changement de scraper.

## Governance

Cette constitution prime sur toute autre pratique du dépôt. Les amendements
suivent la procédure suivante :

1. **Proposition** : ouverture d'une issue GitHub décrivant l'amendement, sa
   motivation, et l'impact attendu sur les principes existants.
2. **Approbation** : accord explicite d'au moins un mainteneur du projet.
3. **Version bump** selon SemVer :
   - **MAJOR** : retrait ou redéfinition incompatible d'un principe.
   - **MINOR** : ajout d'un principe ou d'une section, ou élargissement
     substantiel d'une règle existante.
   - **PATCH** : clarification, reformulation, correction typographique.
4. **Propagation** : mise à jour des templates `.specify/templates/*.md` si
   l'amendement change les gates ou les catégories de tâches ; mise à jour
   d'`AGENTS.md` si le détail opérationnel évolue.
5. **Sync Impact Report** ajouté en tête de ce fichier (bloc HTML commenté),
   documentant la version, les diffs et les templates touchés.

**Compliance review** : chaque `/speckit-plan` doit cocher explicitement la
section « Constitution Check » du plan-template, principe par principe. Une
violation doit être justifiée dans « Complexity Tracking » avec l'alternative
rejetée et la raison. Un principe violé sans justification bloque le passage à
`/speckit-tasks`.

**Runtime guidance** : `AGENTS.md` reste le document opérationnel de
référence (architecture détaillée, commandes, conventions de scraping). En cas
de divergence entre `AGENTS.md` et cette constitution, la constitution prime
et `AGENTS.md` doit être aligné.

**Version**: 1.1.0 | **Ratified**: 2026-07-27 | **Last Amended**: 2026-07-31
