<!--
Sync Impact Report — Constitution v1.0.0
========================================
Version change    : (initial) → 1.0.0
Rationale         : Première ratification. Aucune ancienne version à comparer.
Modified principles : (aucun — création)
Added sections    : Core Principles (I–VI), Additional Constraints, Development Workflow, Governance
Removed sections  : (aucun)
Drafting notes    :
  - Principle I raffiné pendant la rédaction initiale : séparation explicite
    entre couche technique (English) et couche métier / user-visible (français).
    Version conservée à 1.0.0 — l'amendement a eu lieu avant ratification en git.
  - Corrections v1.0.0 suite à la review de la PR #107 (tjarrier) : Principe III
    aligné sur la convention réelle (monkeypatch httpx, pas respx) ; dérogation
    `create_all` recentrée sur les fixtures de test ; Principe II doté d'une
    règle de transition nommant les deux exceptions actuelles (`cache.py`,
    `reclassify.py`) ; Principe I complété d'une clause `DomainError`
    (messages français, ré-affichés par le front). 3 templates repassés en ⚠.
Templates alignés :
  ⚠ .specify/templates/plan-template.md   — la section "Constitution Check" ne
     contient qu'un placeholder `[Gates determined based on constitution file]`.
     La Gouvernance impose une revue « principe par principe » : sans énumération
     des 6 principes dans le template, la revue repose sur la mémoire de l'agent.
     Follow-up : ajouter la grille des 6 principes dans le template (voir TODO ci-dessous).
  ✅ .specify/templates/spec-template.md   — pas d'ajustement nécessaire (les Success Criteria
     restent techno-agnostiques, conformes au principe I).
  ⚠ .specify/templates/tasks-template.md  — la mention "Tests are OPTIONAL"
     apparaît 4 fois (l. 12, 83, 109, 131). Comportement typique de `/speckit-tasks`
     avec ce template : omettre les tâches de test « puisque non explicitement demandées ».
     Principe III est NON-NÉGOCIABLE — pas d'override silencieux acceptable.
     Follow-up : retirer les 4 mentions "OPTIONAL" (voir TODO ci-dessous).
  ⚠ AGENTS.md                              — la règle « **Langue** : UI, commentaires
     et messages en **français** (avec accents) » (AGENTS.md:258) contredit frontalement
     le Principe I sur les docstrings techniques, `logger.*`, noms de tests et identifiants.
     `AGENTS.md` est chargé à chaque session via `CLAUDE.md`, la constitution seulement
     par `/speckit-*` — c'est la règle contradictoire qui est lue le plus souvent.
     Follow-up : aligner AGENTS.md:258 sur Principe I (voir TODO ci-dessous).
Follow-up TODOs   :
  - TODO(plan-template) : énumérer les 6 principes dans « Constitution Check »
    pour donner à `/speckit-plan` une grille à cocher, principe par principe.
  - TODO(tasks-template) : retirer les 4 mentions "Tests are OPTIONAL" (l. 12,
    83, 109, 131) pour aligner sur Principe III (non-négociable).
  - TODO(AGENTS.md) : remplacer la règle langue générale (l. 258) par un renvoi
    au Principe I de la constitution, avec la séparation « métier / user-visible
    en français ; technique invisible en anglais ».
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

**Rationale** : le projet sert un club francophone (le métier est en
français), mais son outillage est anglophone (framework docs, Sentry,
Copilot, revue de code par un LLM). Séparer les deux évite la traduction
implicite dans chaque commit et rend la recherche full-text (`grep`,
Sentry queries) prévisible. Ne pas migrer l'existant : le coût de la
réécriture massive dépasse le bénéfice, et le principe III (TDD) ne peut
tolérer un patch de 200 fichiers non testés.

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

**Version**: 1.0.0 | **Ratified**: 2026-07-27 | **Last Amended**: 2026-07-27
