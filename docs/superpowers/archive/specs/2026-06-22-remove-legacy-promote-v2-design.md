# Suppression du legacy & promotion de la v2 — design

**Date** : 2026-06-22
**Statut** : validé, prêt pour plan d'implémentation
**Branche cible** : `chore/remove-v1-promote-v2` (nouvelle, depuis `feat/refactor-backend-architecture`) → PR vers `feat/refactor-backend-architecture`

## Objectif

Supprimer les deux briques legacy (`backend/` v1 déployé Render, `frontend/` v1
déployé Vercel — toutes deux dépréciées) et promouvoir la v2 comme **seule**
génération, avec des noms de répertoires canoniques. Les configs de déploiement
sont mises à jour pour pointer sur la v2 ; **aucun déploiement n'est déclenché**
dans le cadre de ce travail (l'agent modifie les fichiers, l'utilisateur déploie).

## Décisions actées

| Décision | Choix |
|----------|-------|
| Nommage répertoires | Renommer `backend-v2/`→`backend/`, `frontend-v2/`→`frontend/` (noms canoniques, le suffixe `-v2` n'a plus de sens sans v1) |
| Configs déploiement | Mises à jour pour cibler la v2 (render.yaml, docker-compose) |
| docker-compose | **Porté** vers la v2 (ajout d'un Dockerfile Next.js), pas supprimé |
| Workflow | Nouvelle branche depuis `feat/refactor-backend-architecture`, PR vers cette même branche — c'est la branche d'intégration où vit la v2 ; `master` ne contient **que** la v1 (cibler `master` afficherait 123 commits sans rapport). La bascule `refactor → master/main` se fera séparément. |
| Branche distante existante | `origin/chore/remove-v1-promote-v2` **non reprise** (embarque PR #10 non mergée) — sert seulement de référence |

## Périmètre — modifications

### 1. Renommage & suppression (préserver l'historique git)

1. `git rm -r backend/` (legacy v1 supprimé).
2. `git rm -r frontend/` (legacy v1 supprimé).
3. `git mv backend-v2 backend`.
4. `git mv frontend-v2 frontend`.
5. `frontend/package.json` : `"name": "frontend-v2"` → `"frontend"`.
6. Nettoyer les fichiers de DB de dev présents dans `backend-v2/`
   (`_alembic_tmp.db`, `_fresh_check.db`, `_smoke.db`, `_verify.db`,
   `triathlon.db`) : ne pas les versionner dans le nouveau `backend/` ; vérifier
   que `.gitignore` les couvre.

### 2. Configs de déploiement

- **`render.yaml`** : `rootDir` reste `backend` (après renommage) ;
  `startCommand` → `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT`
  (la v1 utilisait `uvicorn main:app` sans migration ; la v2 a Alembic et
  l'entrée `app.main:app`). `buildCommand` inchangé (`pip install -r requirements.txt`).
- **`docker-compose.yml`** : `build: ./backend` et `build: ./frontend` (chemins
  inchangés après renommage) ; service frontend en `3000:3000` avec
  `BACKEND_URL=http://backend:8000`.
- **`frontend/Dockerfile`** (nouveau) : image Next.js (build standalone). Ajouter
  `output: "standalone"` dans `frontend/next.config.ts` pour produire une image
  autonome. C'est le seul véritable ajout de code de ce chantier.

### 3. Outillage & CI

- **`Taskfile.yml`** : supprimer les tâches `b1:*` et `f1:*` (legacy) ; renommer
  `bv2:*`→`b:*` et `fv2:*`→`f:*` ; mettre à jour les chemins `dir:` et l'en-tête
  de convention de nommage. Les tâches `docker:*` restent (docker-compose porté).
  Les raccourcis sans préfixe (`install`, `dev`, `test`, `lint`, `build`) restent
  et continuent d'agir sur l'unique pile.
- **`.github/workflows/ci.yml`** : remplacer `backend-v2` par `backend` dans
  `paths:` et `working-directory:` ; ajuster le nom du workflow (« CI backend »).

### 4. Documentation

- **`AGENTS.md`** : retirer le tableau « deux générations » et toutes les sections
  « v1 déprécié » (architecture v1, commandes v1). Réécrire pour décrire une seule
  pile aux chemins `backend/` et `frontend/`. Plus gros morceau rédactionnel.
- **`README.md`** : retirer les sections v1 (install, architecture, arbo) ; mettre
  à jour l'arborescence projet et la note sur `render.yaml`.
- **`CLAUDE.md`** : inchangé (contient seulement `@AGENTS.md`).
- **Mémoire** (`~/.claude/.../memory/`) : mettre à jour `backend-v2-refactor.md`,
  `frontend-v2-plan.md` et `MEMORY.md` pour refléter que la v2 est la pile unique
  aux chemins `backend/`/`frontend/`.

## Vérification (critères de succès)

- `cd backend && pytest -m "not integration"` → ~130 tests verts.
- `cd backend && ruff check .` → propre.
- `cd frontend && npm test` → 33 tests verts.
- `cd frontend && npm run build` → build prod OK.
- `cd frontend && npm run lint` → propre.
- `grep -rn "backend-v2\|frontend-v2"` sur le code et les configs actifs
  (`backend/ frontend/ render.yaml docker-compose.yml Taskfile.yml
  .github/ README.md AGENTS.md`) → aucun résultat. Les anciennes specs de
  `docs/superpowers/specs/` ne sont volontairement pas réécrites (références
  historiques).
- `docker compose build` (optionnel, si Docker disponible) → backend + frontend
  se construisent.

## Hors périmètre (actions manuelles de l'utilisateur)

- Régler le **Root Directory** du projet Vercel : `frontend-v2` → `frontend`
  (configuration dashboard, pas dans le repo).
- Déclencher effectivement les déploiements Render / Vercel après merge.
- Décider du sort de la branche distante `origin/chore/remove-v1-promote-v2`
  (la supprimer ou l'ignorer) — non reprise ici.

## Notes

- Les références aux chemins `backend-v2/`/`frontend-v2/` dans les anciennes specs
  de `docs/superpowers/specs/` sont **historiques** et ne sont pas réécrites
  (elles documentent l'état au moment de leur rédaction).
- La branche de référence `origin/chore/remove-v1-promote-v2` confirme l'approche
  render.yaml/docker-compose retenue ci-dessus ; elle n'est pas réutilisée car
  elle est basée sur la branche event-type-normalisation (PR #10 non mergée dans
  `master`), ce qui mélangerait suppression et fonctionnalité.
