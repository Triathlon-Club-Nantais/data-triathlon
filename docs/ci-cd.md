# CI/CD — Render (backend) + Vercel (frontend)

Pipeline gratuit où **rien ne se déploie sans CI verte**, avec deux flux :

| Déclencheur | Environnement | Backend (Render) | Frontend (Vercel) |
|---|---|---|---|
| **Merge dans `main`** | preview / test | service Render preview (deploy hook) | `vercel deploy` (preview) |
| **Tag `v*` sur `main`** | production | service Render prod (deploy hook) | `vercel deploy --prod` |

Toute PR déclenche la CI seule (aucun déploiement).

## Workflows GitHub Actions

- **`.github/workflows/ci.yml`** — source unique des contrôles qualité,
  réutilisable (`workflow_call`) et déclenché sur `pull_request`.
  - Backend : `uv run ruff check .` + `uv run pytest -m "not integration"` (Python 3.13).
  - Frontend : `npm run lint` (eslint) + `npm test` (vitest) + `npm run build`
    (typecheck TS strict + build Next/RSC).
- **`.github/workflows/deploy.yml`** — déclenché sur `push` (branche `main` et
  tags `v*`). Appelle `ci.yml` puis, **seulement si la CI passe** (`needs: ci`),
  lance `deploy-preview` (sur `main`) ou `deploy-production` (sur tag `v*`).
- **`.github/workflows/pages.yml`** — publie ce site de documentation
  (`docs/`) sur GitHub Pages. Sur `pull_request`, le job `build` seul valide que
  le site compile ; sur `main`, `deploy` publie. Il remplace le workflow
  implicite « pages build and deployment » du mode *legacy*, qui ne se
  déclenchait qu'après merge : un bloc JSX dans un plan `docs/superpowers/`
  avait ainsi cassé le rendu Liquid directement sur `main`.

Le gating repose sur `needs: ci` : si un job CI échoue, le job de déploiement
n'est jamais exécuté. Côté Render, `autoDeploy: false` (dans `render.yaml` **et**
dans les réglages du service) empêche tout déploiement automatique hors hook.

## Mise en place côté plateformes (manuel)

### Render (offre gratuite) — 2 services web

Deux services existent désormais dans le workspace « Triathlon Club Nantais »,
région Frankfurt, plan free, runtime python :

| Rôle | Service | Accès |
|---|---|---|
| **PROD** | `data-triathlon` (existant) | dashboard Render → service `data-triathlon` → Settings |
| **PREVIEW** | `triathlon-backend-preview` (créé via MCP) | dashboard Render → service `triathlon-backend-preview` → Settings |

> Les IDs de service (`srv-…`) et les URLs publiques sont visibles dans le
> dashboard Render ; ils ne sont volontairement pas committés ici (dépôt public).

Réglages restants à faire **dans le dashboard** (non supportés par le MCP) :

**Service PROD `data-triathlon`** :
1. **Settings → Auto-Deploy = No** (il est encore en `autoDeploy: yes / checksPass` ;
   en prod on ne déploie que sur tag via hook).
2. Vérifier que `DATABASE_URL` (Supabase prod) est bien présent.
3. Copier l'URL du **Deploy Hook** (Settings → Deploy Hook) → secret `RENDER_DEPLOY_HOOK_PROD`.

**Service PREVIEW `triathlon-backend-preview`** :
1. **Settings → Root Directory = `backend`** (créé avec un rootDir vide — le MCP
   ne permet pas de le définir ; sans ça le build échoue : pas de `pyproject.toml`
   ni de `uv.lock` à la racine du repo).
2. Renseigner `DATABASE_URL` (Supabase preview).
3. Copier l'URL du **Deploy Hook** (Settings → Deploy Hook) → secret `RENDER_DEPLOY_HOOK_PREVIEW`.

> Le premier déploiement automatique du service preview à sa création échoue
> (rootDir vide + `DATABASE_URL` absent) : sans gravité, il sera correct après
> ces réglages et le premier hook.

### Vercel (offre Hobby) — 1 projet

1. **Root Directory = `frontend`**.
2. **Désactiver le déploiement Git automatique** pour que seul le pipeline
   déclenche les déploiements : Settings → Git → désactiver la connexion
   d'auto-deploy, ou définir un *Ignored Build Step* renvoyant `exit 0` sur les
   pushs Git.
3. `VERCEL_ORG_ID` et `VERCEL_PROJECT_ID` (projet `data-triathlon` existant,
   team « Triathlon Club Nantais ») — à récupérer (non committés, dépôt public) :
   - via la CLI : `vercel link` puis lire `.vercel/project.json`
     (`orgId` → `VERCEL_ORG_ID`, `projectId` → `VERCEL_PROJECT_ID`) ;
   - ou dans le dashboard : Project → Settings → General.
4. Créer un **`VERCEL_TOKEN`** (Account Settings → Tokens).
5. Variables d'environnement projet :
   - env **Preview** : `BACKEND_URL` / `API_URL` → backend Render **preview**.
   - env **Production** : `BACKEND_URL` / `API_URL` → backend Render **prod**.

### Authentification SSO (#114) — variables par environnement

**Six** des huit réglages `AUTH_*` sont déclarés dans `render.yaml` : en
`sync: false`, à deux exceptions près — `AUTH_SESSION_SECRET_KEY` en
`generateValue: true` et `AUTH_COOKIE_SECURE` en `value: "true"`. Les deux durées
de vie (`AUTH_SESSION_TTL_DAYS`, `AUTH_STATE_TTL_SECONDS`) n'y figurent pas et
restent aux défauts du code (7 j / 600 s). Tous se renseignent **côté backend** —
le frontend n'en porte aucun, il ne fait que proxifier `/api/*`.

> **`render.yaml` ne décrit que le service de production.** Le service
> **preview** est créé à la main (voir plus haut), donc le blueprint ne s'y
> applique pas : `generateValue` n'y joue pas et **aucun** réglage `AUTH_*` n'y
> apparaît tout seul. Sur preview, la clé de session est à générer et à saisir
> soi-même, comme en local.

| Variable | PROD | PREVIEW | Local |
|---|---|---|---|
| `AUTH_SESSION_SECRET_KEY` | généré par Render (`generateValue`) | **à saisir à la main** (hors blueprint) | `python -c "import secrets; print(secrets.token_urlsafe(64))"` |
| `AUTH_GITHUB_CLIENT_ID` / `_SECRET` | application OAuth « prod » | application OAuth « preview » | application OAuth « local » |
| `AUTH_ALLOWED_EMAILS` | adresses des contributeurs, en CSV | idem, ou vide pour fermer | votre adresse GitHub vérifiée |
| `AUTH_REDIRECT_BASE_URL` | URL Vercel **production** | URL Vercel du déploiement stable | `http://127.0.0.1:3000` |
| `AUTH_COOKIE_SECURE` | `true` | `true` | `false` |
| `AUTH_SESSION_TTL_DAYS` / `AUTH_STATE_TTL_SECONDS` | défauts (7 j / 600 s) | défauts | défauts |

> **Régénérer `AUTH_SESSION_SECRET_KEY` ne ferme aucune session.** C'est
> l'attente naturelle, et elle est fausse : le jeton de session est **opaque et
> vérifié en base**, il n'est pas signé — cette clé ne signe que le jeton
> d'état. Une rotation n'interrompt donc que les parcours de connexion en cours
> (600 s de fenêtre), et croire l'inverse ferait tenir une fuite pour colmatée.
> Pour fermer réellement les sessions : `is_active = False` sur un compte,
> `DELETE FROM user_sessions` pour tous (procédure détaillée dans `AGENTS.md`).
>
> Corollaire : personne n'a besoin de connaître cette clé, d'où le
> `generateValue` en production. La saisir à la main n'apporte aucun levier
> qu'on n'ait déjà, et fait transiter un secret par un presse-papiers.

Trois points qui coûtent cher s'ils sont découverts en production :

- **une application OAuth GitHub n'accepte qu'une seule URL de retour**, port
  compris. Il faut donc **une application par environnement** : prod, preview,
  et une par développeur. Le retour vise l'**interface**
  (`<origine>/api/v1/auth/github/callback`), jamais le backend Render — le
  cookie d'état est posé sur l'origine de l'interface et ne serait pas renvoyé
  autrement, faisant échouer **tout** retour de parcours en `state_mismatch` ;
- **les déploiements de prévisualisation par PR sont hors périmètre** : leur URL
  change à chaque exécution, donc aucune URL de retour stable ne peut être
  enregistrée chez GitHub. La connexion n'y fonctionne pas, et c'est assumé —
  seul le déploiement preview **stable** (celui que vise `AUTH_REDIRECT_BASE_URL`)
  est utilisable. Le site public, lui, reste entier sur toutes les previews ;
- `AUTH_ALLOWED_EMAILS` **vide interdit toute connexion** et fait rendre `[]` à
  `/auth/methods`. Ce n'est pas un défaut permissif : une variable oubliée sur
  Render ferme l'accès au lieu de l'ouvrir à n'importe quel compte GitHub.
  Deux conséquences d'exploitation : **ajouter un contributeur exige un
  redéploiement** (`get_settings` est en `lru_cache`, la liste est lue au
  démarrage du processus) ; et un refus se diagnostique **dans les journaux du
  backend**, où l'adresse soumise est tracée — le code rendu au visiteur, lui,
  reste muet sur la valeur (FR-030).

### Secrets GitHub

Settings → Secrets and variables → Actions :

| Secret | Usage |
|---|---|
| `RENDER_DEPLOY_HOOK_PREVIEW` | URL du deploy hook Render preview |
| `RENDER_DEPLOY_HOOK_PROD` | URL du deploy hook Render prod |
| `VERCEL_TOKEN` | Token CLI Vercel |
| `VERCEL_ORG_ID` | ID de l'organisation Vercel |
| `VERCEL_PROJECT_ID` | ID du projet Vercel |

### GitHub Pages (documentation) — une seule bascule

Le dépôt était en mode *legacy* (Settings → Pages → « Deploy from a branch »,
`main` + `/docs`). Après merge de `pages.yml`, basculer la source **une fois** :

```bash
gh api --method PUT repos/Triathlon-Club-Nantais/data-triathlon/pages \
  -f build_type=workflow
```

ou Settings → Pages → Source → *GitHub Actions*. Tant que la bascule n'est pas
faite, `deploy-pages` échoue : le service refuse un déploiement par workflow
quand la source est encore une branche. Aucun secret à créer — le
`GITHUB_TOKEN` du workflow suffit, avec les `permissions:` déclarées dedans
(`pages: write`, `id-token: write`), le défaut du dépôt étant `read`.

Le site publie `docs/` moins ce que `docs/_config.yml` exclut : `superpowers/`
et `test/` sont des documents de travail, ils restent lisibles dans le dépôt.
Pages est figé sur **Jekyll 3.10**, sans `render_with_liquid` — un fichier
publié qui ouvre une variable Liquid (deux accolades ouvrantes, courant dans les
blocs JSX) casse le build, y compris à l'intérieur d'un bloc de code : Liquid
passe avant Markdown. L'exclusion est ce qui met les plans à l'abri ; dans une
page **publiée**, il faut entourer le passage des balises Liquid `raw` /
`endraw`.

### Optionnel (recommandé) — garde-fou production

Créer les *Environments* GitHub `preview` et `production`, puis ajouter une
**required reviewer** sur `production` : un tag `v*` déclenchera la CI mais la
mise en production attendra une validation manuelle.

## Publier une version

```bash
# Preview : il suffit de merger dans main (PR mergée)

# Production : taguer un commit de main
git checkout main && git pull
git tag v0.1.0
git push origin v0.1.0
```

## Vérification

1. Ouvrir une PR → les jobs `backend` et `frontend` passent.
2. Merger dans `main` → `deploy.yml` enchaîne `ci` puis `deploy-preview`
   (hook Render preview + Vercel preview).
3. `git tag v0.1.0 && git push --tags` → `ci` puis `deploy-production`
   (hook Render prod + `vercel --prod`).
4. Sur une CI volontairement cassée (erreur ruff/test), confirmer que le job de
   déploiement **n'est pas exécuté**.
