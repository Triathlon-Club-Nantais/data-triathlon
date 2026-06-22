# Suppression du legacy & promotion de la v2 — plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Supprimer les briques legacy `backend/` (v1) et `frontend/` (v1), renommer `backend-v2/`→`backend/` et `frontend-v2/`→`frontend/`, et mettre à jour toutes les configs/docs pour que la v2 soit la seule génération.

**Architecture:** Migration mécanique en deux temps par brique (`git rm` du legacy puis `git mv` de la v2), suivie de la mise à jour des configs de déploiement (render.yaml, docker-compose + Dockerfile Next.js), de l'outillage (Taskfile, CI) et de la documentation. Validation = suites de tests existantes (≈130 backend, 33 frontend) qui doivent rester vertes.

**Tech Stack:** Python 3.11 / FastAPI / Alembic (backend), Next.js 16 / TypeScript (frontend), Render + Vercel + Docker Compose (déploiement), Taskfile + GitHub Actions (outillage).

## Global Constraints

- Branche `chore/remove-v1-promote-v2`, déjà créée depuis `feat/refactor-backend-architecture` (HEAD a6410e1). PR cible : `feat/refactor-backend-architecture` (la v2 n'existe pas dans `master`).
- Préserver l'historique git : `git mv` pour renommer, `git rm` pour supprimer.
- Commits en français, Conventional Commits (`chore:`, `docs:`, `feat:`…), terminés par `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
- UI, commentaires et messages en français avec accents.
- Ne **pas** versionner les fichiers de DB de dev (`*.db`).
- **Aucun déploiement déclenché** : on modifie les fichiers uniquement.
- Après chaque tâche : la suite de tests concernée doit rester verte avant commit.

---

### Task 1: Migration du backend (suppression v1 + renommage v2)

**Files:**
- Delete: `backend/` (legacy v1 entier)
- Rename: `backend-v2/` → `backend/`
- Delete (non versionnés) : `backend-v2/*.db` (`_alembic_tmp.db`, `_fresh_check.db`, `_smoke.db`, `_verify.db`, `triathlon.db`)

**Interfaces:**
- Produces: répertoire `backend/` contenant la v2 (FastAPI `app.main:app`, Alembic, ~130 tests). Les tâches suivantes (render.yaml, CI, docs) référencent ce chemin.

- [ ] **Step 1: Supprimer le backend legacy v1**

```bash
git rm -r backend
```

- [ ] **Step 2: Renommer backend-v2 en backend**

```bash
git mv backend-v2 backend
```

- [ ] **Step 3: Retirer les fichiers de DB de dev du suivi git (s'ils étaient suivis)**

```bash
cd /home/thomas_jarrier/Workspace/TCN/data-triathlon
git rm --cached --ignore-unmatch backend/_alembic_tmp.db backend/_fresh_check.db backend/_smoke.db backend/_verify.db backend/triathlon.db
rm -f backend/_alembic_tmp.db backend/_fresh_check.db backend/_smoke.db backend/_verify.db backend/triathlon.db
```

- [ ] **Step 4: Vérifier que `*.db` est bien ignoré**

Run: `grep -n "db" .gitignore`
Expected: une règle couvrant `*.db` (ex. `*.db`). Si absente, l'ajouter :

```bash
printf '\n# Bases SQLite de dev\n*.db\n' >> .gitignore
```

- [ ] **Step 5: Lancer les tests backend (sans réseau) + lint**

Run: `cd backend && pytest -m "not integration" && ruff check .`
Expected: ~130 tests PASS, ruff « All checks passed! ». (venv Python activé requis ; si `alembic`/`pytest` introuvables : `pip install -r requirements-dev.txt`.)

- [ ] **Step 6: Commit**

```bash
cd /home/thomas_jarrier/Workspace/TCN/data-triathlon
git add -A backend .gitignore
git commit -m "chore(backend): supprime la v1 et promeut backend-v2 en backend/

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Migration du frontend (suppression v1 + renommage v2)

**Files:**
- Delete: `frontend/` (legacy v1 entier)
- Rename: `frontend-v2/` → `frontend/`
- Modify: `frontend/package.json` (champ `name`)

**Interfaces:**
- Produces: répertoire `frontend/` contenant la v2 (Next.js 16, 33 tests Vitest). Les tâches docker-compose/Dockerfile et docs référencent ce chemin.

- [ ] **Step 1: Supprimer le frontend legacy v1**

```bash
git rm -r frontend
```

- [ ] **Step 2: Renommer frontend-v2 en frontend**

```bash
git mv frontend-v2 frontend
```

- [ ] **Step 3: Corriger le nom du paquet**

Modifier `frontend/package.json` : remplacer `"name": "frontend-v2"` par `"name": "frontend"`.

- [ ] **Step 4: Lancer les tests frontend + build + lint**

Run: `cd frontend && npm test && npm run lint && npm run build`
Expected: 33 tests Vitest PASS, ESLint propre, build prod « Compiled successfully ». (Si `node_modules` absent après le `git mv` : `npm install` d'abord.)

- [ ] **Step 5: Commit**

```bash
cd /home/thomas_jarrier/Workspace/TCN/data-triathlon
git add -A frontend
git commit -m "chore(frontend): supprime la v1 et promeut frontend-v2 en frontend/

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Configs de déploiement (Render + Docker + Dockerfile Next.js)

**Files:**
- Modify: `render.yaml`
- Modify: `docker-compose.yml`
- Modify: `frontend/next.config.ts` (ajout `output: "standalone"`)
- Create: `frontend/Dockerfile`
- Create: `frontend/.dockerignore`

**Interfaces:**
- Consumes: répertoires `backend/` et `frontend/` (Tasks 1 & 2).
- Produces: pile déployable v2 (Render → backend, docker-compose → full-stack local).

- [ ] **Step 1: Mettre à jour `render.yaml`**

Remplacer entièrement le contenu par :

```yaml
services:
  - type: web
    name: triathlon-backend
    runtime: python
    rootDir: backend
    pythonVersion: "3.11.0"
    buildCommand: pip install -r requirements.txt
    startCommand: alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT
    envVars:
      - key: DATABASE_URL
        sync: false
```

- [ ] **Step 2: Mettre à jour `docker-compose.yml`**

Remplacer entièrement le contenu par :

```yaml
services:
  backend:
    build:
      context: ./backend
    container_name: triathlon_backend
    restart: unless-stopped
    volumes:
      - db_data:/app/triathlon.db
    environment:
      - DATABASE_URL=sqlite:///./triathlon.db
    ports:
      - "8000:8000"

  frontend:
    build: ./frontend
    container_name: triathlon_frontend
    restart: unless-stopped
    environment:
      - BACKEND_URL=http://backend:8000
    ports:
      - "3000:3000"
    depends_on:
      - backend

volumes:
  db_data:
```

- [ ] **Step 3: Activer la sortie standalone dans `frontend/next.config.ts`**

Remplacer entièrement le contenu par :

```typescript
import type { NextConfig } from "next";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8001";

const nextConfig: NextConfig = {
  // Build autonome pour l'image Docker (copie `.next/standalone` → `node server.js`).
  output: "standalone",
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${BACKEND_URL}/api/:path*` },
    ];
  },
};

export default nextConfig;
```

- [ ] **Step 4: Créer `frontend/Dockerfile`**

```dockerfile
# Image Next.js (App Router) en sortie « standalone ».
# Build multi-stage : deps → build → runner minimal (node server.js).

FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:22-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV PORT=3000
ENV HOSTNAME=0.0.0.0

RUN addgroup -S nodejs && adduser -S nextjs -G nodejs

# Sortie standalone : serveur + node_modules minimal, assets statiques, public/.
COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs
EXPOSE 3000

# BACKEND_URL injecté à l'exécution (rewrites /api → backend).
CMD ["node", "server.js"]
```

- [ ] **Step 5: Créer `frontend/.dockerignore`**

```
node_modules
.next
npm-debug.log
.git
.env*.local
.vercel
coverage
```

- [ ] **Step 6: Vérifier que le build standalone fonctionne**

Run: `cd frontend && npm run build`
Expected: build OK ; le dossier `.next/standalone/` est généré (confirme `output: "standalone"`). Vérifier : `ls .next/standalone/server.js`.

- [ ] **Step 7: (Optionnel, si Docker disponible) build des images**

Run: `cd /home/thomas_jarrier/Workspace/TCN/data-triathlon && docker compose build`
Expected: les images `backend` et `frontend` se construisent sans erreur. Si Docker indisponible, ignorer cette étape.

- [ ] **Step 8: Commit**

```bash
cd /home/thomas_jarrier/Workspace/TCN/data-triathlon
git add render.yaml docker-compose.yml frontend/next.config.ts frontend/Dockerfile frontend/.dockerignore
git commit -m "feat(deploy): cible la v2 (render alembic+app.main, docker-compose, Dockerfile Next.js)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Outillage Taskfile (suppression des tâches v1, renommage v2)

**Files:**
- Modify: `Taskfile.yml`

**Interfaces:**
- Consumes: répertoires `backend/`, `frontend/`.
- Produces: tâches `b:*` (backend) et `f:*` (frontend) ; tâches `b1:*`/`f1:*` supprimées.

- [ ] **Step 1: Réécrire l'en-tête de convention de nommage**

Dans le bloc de commentaire d'en-tête de `Taskfile.yml`, remplacer le paragraphe « Convention de nommage » par :

```
# Convention de nommage :
#   b:*  → backend/   (FastAPI + SQLAlchemy + Alembic)
#   f:*  → frontend/  (Next.js + TypeScript + Tailwind)
#   docker:* → docker-compose (pile full-stack locale)
# Les tâches sans préfixe sont des raccourcis qui agissent sur l'ensemble de la pile.
```

- [ ] **Step 2: Renommer le préfixe `bv2:` en `b:` et `dir: backend-v2` en `dir: backend`**

Dans tout `Taskfile.yml` : remplacer chaque occurrence de `bv2:` par `b:`, et chaque `dir: backend-v2` par `dir: backend`. Mettre à jour les `task: bv2:...` dans les `deps`/`cmds` des raccourcis (`install`, `dev`, `test`, `lint`, `build`) en `task: b:...`. Retirer la mention « CIBLE » dans les `desc` (il n'y a plus qu'une pile).

- [ ] **Step 3: Renommer le préfixe `fv2:` en `f:` et `dir: frontend-v2` en `dir: frontend`**

Dans tout `Taskfile.yml` : remplacer chaque `fv2:` par `f:`, chaque `dir: frontend-v2` par `dir: frontend`, et les `task: fv2:...` par `task: f:...`.

- [ ] **Step 4: Supprimer les tâches legacy `b1:*` et `f1:*`**

Supprimer entièrement les deux blocs de tâches `b1:install`, `b1:dev`, `b1:test` (section « backend/ — DÉPRÉCIÉ ») et `f1:install`, `f1:dev`, `f1:build` (section « frontend/ — DÉPRÉCIÉ »), commentaires de section inclus.

- [ ] **Step 5: Corriger le commentaire de section Docker**

Remplacer le commentaire `# Docker Compose (pile v1 : backend :8000 + frontend :3000)` par `# Docker Compose (pile full-stack : backend :8000 + frontend :3000)`.

- [ ] **Step 6: Vérifier que Taskfile est valide et que les tâches existent**

Run: `task --list`
Expected: liste affichée sans erreur YAML ; on voit `b:dev`, `b:test`, `f:dev`, `f:test`, `docker:up` ; plus aucune tâche `b1:*`/`f1:*`/`bv2:*`/`fv2:*`.

- [ ] **Step 7: Vérifier qu'un raccourci fonctionne**

Run: `task test`
Expected: enchaîne les tests backend puis frontend, tous verts.

- [ ] **Step 8: Commit**

```bash
git add Taskfile.yml
git commit -m "chore(taskfile): supprime les tâches v1, renomme bv2/fv2 en b/f

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: CI GitHub Actions

**Files:**
- Modify: `.github/workflows/ci.yml`

**Interfaces:**
- Consumes: répertoire `backend/`.
- Produces: workflow CI qui s'exécute sur `backend/**`.

- [ ] **Step 1: Mettre à jour le workflow**

Dans `.github/workflows/ci.yml` : remplacer le nom `CI backend-v2` par `CI backend` ; remplacer les deux occurrences de `backend-v2/**` (dans `push.paths` et `pull_request.paths`) par `backend/**` ; remplacer `working-directory: backend-v2` par `working-directory: backend` ; remplacer `cache-dependency-path: backend-v2/requirements-dev.txt` par `cache-dependency-path: backend/requirements-dev.txt`.

- [ ] **Step 2: Vérifier qu'il ne reste plus de référence `-v2` dans le workflow**

Run: `grep -n "v2" .github/workflows/ci.yml`
Expected: aucun résultat.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "chore(ci): cible backend/ (renommé depuis backend-v2)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: Documentation AGENTS.md (pile unique)

**Files:**
- Modify: `AGENTS.md`

**Interfaces:**
- Consumes: chemins `backend/`, `frontend/`. `CLAUDE.md` reste `@AGENTS.md` (inchangé).

- [ ] **Step 1: Supprimer la section « État du projet — migration en cours »**

Retirer entièrement la section `## État du projet — migration en cours` (le tableau « deux générations » et la liste de puces v1/v2 dépréciées). La remplacer par une courte intro de pile unique :

```markdown
## Pile applicative

Une seule génération en production :

- **Backend** (`backend/`) : archi en couches, modèle normalisé, Alembic.
- **Frontend** (`frontend/`) : Next.js 16 (App Router), TypeScript, Tailwind, shadcn/ui.

Specs de refonte historiques : `docs/superpowers/specs/`.
```

- [ ] **Step 2: Réécrire la section `## Stack`**

Supprimer les lignes « Backend v1 », « Frontend v1 (déprécié) ». Conserver les descriptions v2 mais retirer les mentions « v2 » / « CIBLE » / « Codée … pas encore déployée ». Résultat :

```markdown
## Stack
- **Backend** (`backend/`) : Python 3.11+, FastAPI 0.115, SQLAlchemy 2.0
  (sync), Pydantic v2 + pydantic-settings, **Alembic** (migrations), PostgreSQL
  (Supabase) / SQLite en dev. Scraping httpx + BeautifulSoup/lxml, fallback
  Playwright. Tests pytest, ruff. API versionnée sous `/api/v1`.
- **Frontend** (`frontend/`) : Next.js 16 (App Router) + TypeScript + Tailwind + shadcn/ui.
- **Déploiement** : backend → Render (`render.yaml`), front → Vercel, DB → Supabase.
```

- [ ] **Step 3: Réécrire la section `## Commandes`**

Supprimer les blocs « Backend v1 (depuis backend/, déprécié) » et « Frontend v1 (depuis frontend/, déprécié) ». Retirer les mentions « — CIBLE ». Les commandes v2 restent mais leurs chemins sont déjà `backend/`/`frontend/` (inchangés). Vérifier qu'aucune commande ne référence `backend-v2`/`frontend-v2`.

- [ ] **Step 4: Nettoyer les sections d'architecture**

Renommer `## Architecture backend v2 (`backend/`) — cible` en `## Architecture backend (`backend/`)`. Supprimer entièrement `## Architecture backend v1 (`backend/`) — déprécié`. Renommer `## Architecture frontend v2 (`frontend-v2/`) — cible` en `## Architecture frontend (`frontend/`)` et y remplacer `frontend-v2/` par `frontend/`. Supprimer entièrement `## Architecture frontend v1 (`frontend/`) — déprécié`.

- [ ] **Step 5: Nettoyer les références résiduelles dans les conventions**

Dans la section `## Conventions scrapers`, remplacer « porté de `backend/` » et les distinctions « En v2 / En v1 » par une formulation unique (la v1 n'existe plus). Dans `## Conventions générales`, retirer les mentions « v1 (déprécié) » du paragraphe sur le schéma DB (ne garder que la procédure Alembic).

- [ ] **Step 6: Vérifier l'absence de référence v1/-v2**

Run: `grep -niE "backend-v2|frontend-v2|v1|déprécié|migration en cours" AGENTS.md`
Expected: aucun résultat (hors éventuelle mention « Pydantic v2 » et « SQLAlchemy 2.0 » qui sont des versions de libs — vérifier visuellement que seules ces occurrences légitimes subsistent).

- [ ] **Step 7: Commit**

```bash
git add AGENTS.md
git commit -m "docs(agents): décrit une pile unique (v1 supprimée)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 7: Documentation README.md (pile unique)

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: chemins `backend/`, `frontend/`.

- [ ] **Step 1: Lire le README pour repérer les sections v1**

Run: `grep -nE "v1|v2|backend-v2|frontend-v2|déprécié" README.md`
Expected: liste des lignes à traiter (install backend v1, architecture v1, arbo, note render.yaml).

- [ ] **Step 2: Supprimer/fusionner les sections v1**

Pour chaque section dédiée v1 (« Backend v1 (`backend/`, déployé en prod — déprécié) », « Backend v1 (`backend/`) » sous Architecture, équivalents frontend) : supprimer la section v1 et, si une section v2 équivalente existe, la conserver comme **la** section de référence sans le suffixe « v2 ». Mettre à jour le chemin de l'instruction `backend/.env` (reste `backend/.env`, ok). Mettre à jour la note `python backend/extract_xlsx_urls.py` si ce script n'existe plus dans la v2 (vérifier `ls backend/extract_xlsx_urls.py` ; si absent, retirer la note).

- [ ] **Step 3: Mettre à jour l'arborescence projet**

Dans le bloc arborescence, retirer les lignes commentées « ⚠️ v1 — déployé en prod, déprécié » pour `backend/` et `frontend/` ; décrire `backend/` et `frontend/` comme la pile unique (FastAPI/Alembic ; Next.js). Retirer toute ligne `backend-v2/`/`frontend-v2/`.

- [ ] **Step 4: Mettre à jour la note render.yaml**

Remplacer la note « `render.yaml` cible actuellement `backend/` (v1). Lors de la bascule v2, mettre… » par une note indiquant que `render.yaml` cible `backend/` (FastAPI v2, `alembic upgrade head && uvicorn app.main:app`).

- [ ] **Step 5: Vérifier l'absence de référence v1/-v2**

Run: `grep -niE "backend-v2|frontend-v2|déprécié|bascule" README.md`
Expected: aucun résultat.

- [ ] **Step 6: Commit**

```bash
git add README.md
git commit -m "docs(readme): décrit une pile unique (v1 supprimée)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 8: Mise à jour de la mémoire agent (hors repo)

**Files (hors dépôt git, pas de commit) :**
- Modify: `~/.claude/projects/-home-thomas-jarrier-Workspace-TCN-data-triathlon/memory/backend-v2-refactor.md`
- Modify: `~/.claude/projects/-home-thomas-jarrier-Workspace-TCN-data-triathlon/memory/frontend-v2-plan.md`
- Modify: `~/.claude/projects/-home-thomas-jarrier-Workspace-TCN-data-triathlon/memory/MEMORY.md`

**Interfaces:** aucune (mémoire agent, pas de code).

- [ ] **Step 1: Mettre à jour `backend-v2-refactor.md`**

Indiquer que la v2 est désormais la pile **unique**, au chemin `backend/` (le legacy v1 a été supprimé sur la branche `chore/remove-v1-promote-v2`, PR vers `feat/refactor-backend-architecture` le 2026-06-22). Conserver le contexte d'archi en couches.

- [ ] **Step 2: Mettre à jour `frontend-v2-plan.md`**

Indiquer que le frontend v2 est désormais au chemin `frontend/` (legacy supprimé), même branche/date.

- [ ] **Step 3: Mettre à jour la ligne d'index dans `MEMORY.md`**

Ajuster les deux puces backend/frontend pour refléter les chemins canoniques `backend/`/`frontend/` et l'état « pile unique ».

*(Pas de commit : la mémoire vit hors du dépôt git.)*

---

### Task 9: Vérification finale & ouverture de la PR

**Files:** aucun (vérification + PR).

- [ ] **Step 1: Sweep global des références `-v2` sur le code et les configs actifs**

Run:
```bash
cd /home/thomas_jarrier/Workspace/TCN/data-triathlon
grep -rnE "backend-v2|frontend-v2" backend frontend render.yaml docker-compose.yml Taskfile.yml .github README.md AGENTS.md --exclude-dir=node_modules --exclude-dir=.next 2>/dev/null
```
Expected: aucun résultat. (Si un résultat apparaît, le corriger et l'ajouter au commit de la tâche concernée.)

- [ ] **Step 2: Suite de tests complète backend + frontend**

Run:
```bash
cd backend && pytest -m "not integration" && ruff check . && cd ../frontend && npm test && npm run lint && npm run build
```
Expected: ~130 tests backend + 33 tests frontend verts, lint propre, build prod OK.

- [ ] **Step 3: Revue de l'arborescence finale**

Run: `ls -d backend backend-v2 frontend frontend-v2 2>/dev/null`
Expected: seuls `backend` et `frontend` existent ; `backend-v2`/`frontend-v2` absents.

- [ ] **Step 4: Pousser la branche et ouvrir la PR vers `feat/refactor-backend-architecture`**

```bash
git push -u origin chore/remove-v1-promote-v2
gh pr create --base feat/refactor-backend-architecture --title "chore: supprime la v1 (legacy) et promeut la v2 comme seule génération" --body "$(cat <<'EOF'
## Résumé
- Supprime les briques legacy `backend/` (v1) et `frontend/` (v1)
- Renomme `backend-v2/`→`backend/` et `frontend-v2/`→`frontend/`
- Met à jour les configs de déploiement (render.yaml : `alembic upgrade head && uvicorn app.main:app` ; docker-compose ; Dockerfile Next.js standalone)
- Met à jour l'outillage (Taskfile `b:*`/`f:*`, CI `backend/**`) et la documentation (AGENTS.md, README.md)

## Hors périmètre (manuel)
- Réglage Vercel « Root Directory » `frontend-v2`→`frontend`
- Déclenchement effectif des déploiements Render/Vercel

## Tests
- backend : ~130 tests verts + ruff
- frontend : 33 tests verts + build prod OK

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```
Expected: PR créée, base `feat/refactor-backend-architecture`. La CI doit se déclencher (paths `backend/**`).

---

## Self-Review — couverture spec

| Exigence spec | Tâche |
|---------------|-------|
| Supprimer `backend/` v1 | Task 1 |
| Supprimer `frontend/` v1 | Task 2 |
| Renommer backend-v2→backend | Task 1 |
| Renommer frontend-v2→frontend | Task 2 |
| package.json name | Task 2 |
| Nettoyage DB de dev | Task 1 |
| render.yaml → v2 | Task 3 |
| docker-compose → v2 | Task 3 |
| Dockerfile Next.js + standalone | Task 3 |
| Taskfile (suppr v1, renommage) | Task 4 |
| CI workflow | Task 5 |
| AGENTS.md | Task 6 |
| README.md | Task 7 |
| Mémoire | Task 8 |
| Vérification (tests, grep, build) | Tasks 1,2,3,9 |
| PR vers feat/refactor-backend-architecture | Task 9 |
| Hors périmètre (Vercel, deploy) | documenté dans la PR (Task 9) |
