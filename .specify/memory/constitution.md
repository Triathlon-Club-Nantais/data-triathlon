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
Templates alignés :
  ✅ .specify/templates/plan-template.md   — la section "Constitution Check" est laissée
     ouverte par le template ; les gates ci-dessous (§Governance) sont à cocher lors du /speckit-plan.
  ✅ .specify/templates/spec-template.md   — pas d'ajustement nécessaire (les Success Criteria
     restent techno-agnostiques, conformes au principe I).
  ✅ .specify/templates/tasks-template.md  — la mention "Tests are OPTIONAL" du template reste,
     mais le principe III MUST override : les tâches doivent inclure les tests unitaires sans réseau.
  ✅ AGENTS.md                              — source vérité opérationnelle ; la constitution en
     extrait les invariants non-négociables. Existant en français conservé (voir Principle I,
     règle de transition) ; aucune divergence de fond.
Follow-up TODOs   : (aucun)
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

**Rationale** : trois listes divergentes du critère club ont fait compter tout
libellé « nantais » comme TCN (#76). La monogamie des responsabilités par
couche est la seule garde qui tienne dans la durée.

### III. TDD sans réseau (NON-NÉGOCIABLE)

Toute nouvelle logique métier est **précédée** d'un test qui échoue puis passe
au vert. Les tests unitaires n'appellent **jamais** le réseau réel : httpx est
mocké avec `respx`, les payloads capturés sont dans `tests/fixtures/`. Le
réseau réel est isolé derrière le marker `integration` (déclaré dans
`backend/pyproject.toml`), jamais lancé par défaut. Une PR n'entre pas sans
`uv run pytest -m "not integration"` vert.

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
  révision générée. Jamais de `Base.metadata.create_all()` en dehors de
  `scripts/reset_db.py`.
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
