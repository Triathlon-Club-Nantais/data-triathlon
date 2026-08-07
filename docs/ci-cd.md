# CI/CD — Render (backend) + Vercel (frontend)

Pipeline gratuit où **rien ne se déploie sans CI verte**, avec deux flux :

| Déclencheur | Environnement | Backend (Render) | Frontend (Vercel) |
|---|---|---|---|
| **Merge dans `main`** (ou `workflow_dispatch`) | preview / test | service Render preview (deploy hook) | `--prod` sur le projet `data-triathlon-preview` |
| **Tag `v*` sur `main`** | production | service Render prod (deploy hook) | `--prod` sur le projet `data-triathlon` |

**Les deux flux déploient en production — de deux projets Vercel différents.**
Ce n'est pas une coquille : un *preview deployment* change d'URL à chaque
exécution, alors que chaque projet a un domaine de production stable. Router la
preview vers la production d'un second projet est ce qui lui donne une URL fixe,
donc une URL de retour SSO enregistrable et une protection de déploiement qui
tient (#172). Le ciblage ne passe par aucune variable dédiée : les deux jobs
déclarent déjà un *environment* GitHub, et le `VERCEL_PROJECT_ID` défini sur
l'environment `preview` surcharge celui du dépôt.

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
n'est jamais exécuté. Côté Render, c'est **Auto-Deploy = No dans les réglages du
service** qui empêche tout déploiement automatique hors hook.

> **`render.yaml` n'est appliqué par personne.** Les deux services ont été créés
> à la main, pas depuis un Blueprint : Render ne lit jamais ce fichier, et la
> configuration qui fait foi est celle du dashboard. Le fichier est maintenu à
> jour comme base de référence, mais toute modification y est **sans effet** —
> la reporter dans le dashboard, sur les deux services. Ce décalage a un coût
> mesuré : c'est #162, où le `buildCommand` du fichier prétendait écrire un
> fichier `VERSION` qui n'a jamais existé.

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

### Vercel (offre Hobby) — 2 projets

| Rôle | Projet Vercel | Ciblé par |
|---|---|---|
| **PROD** | `data-triathlon` | environment GitHub `production` (secret de dépôt) |
| **PREVIEW** | `data-triathlon-preview` | environment GitHub `preview` (secret d'environment) |

À faire **sur chacun des deux projets**, team « Triathlon Club Nantais » :

1. **Root Directory = `frontend`**.
2. **Désactiver le déploiement Git automatique** pour que seul le pipeline
   déclenche les déploiements : Settings → Git → désactiver la connexion
   d'auto-deploy, ou définir un *Ignored Build Step* renvoyant `exit 0` sur les
   pushs Git.
3. Relever `VERCEL_ORG_ID` et `VERCEL_PROJECT_ID` (non committés, dépôt public) :
   - via la CLI : `vercel link` puis lire `.vercel/project.json`
     (`orgId` → `VERCEL_ORG_ID`, `projectId` → `VERCEL_PROJECT_ID`) ;
   - ou dans le dashboard : Project → Settings → General.
4. Variables d'environnement **Production** du projet — c'est celles-là que
   lisent les deux jobs, chacun déployant en `--prod` de son propre projet :
   - `data-triathlon` : `BACKEND_URL` / `API_URL` → backend Render **prod** ;
   - `data-triathlon-preview` : `BACKEND_URL` / `API_URL` → backend Render
     **preview**. Sans ça, la preview taperait la base de production.
5. Sur `data-triathlon-preview` seul : configurer la protection de déploiement /
   SSO sur son URL fixe, désormais stable.

Puis, une fois pour le compte : créer un **`VERCEL_TOKEN`** (Account Settings →
Tokens), commun aux deux projets.

> `VERCEL_PROJECT_ID` porte le **même nom sur les deux environments GitHub**, avec
> une valeur différente de part et d'autre : chaque job ne voit que celle de
> l'environment qu'il déclare. D'où l'absence d'un `VERCEL_PROJECT_ID_PREVIEW` et
> de toute ligne `env:` dupliquée dans `deploy.yml`.

### Authentification SSO (#114) — variables par environnement

**Six** des huit réglages `AUTH_*` sont **documentés** dans `render.yaml` : en
`sync: false`, à deux exceptions près — `AUTH_SESSION_SECRET_KEY` en
`generateValue: true` et `AUTH_COOKIE_SECURE` en `value: "true"`. Les deux durées
de vie (`AUTH_SESSION_TTL_DAYS`, `AUTH_STATE_TTL_SECONDS`) n'y figurent pas et
restent aux défauts du code (7 j / 600 s). Tous se renseignent **côté backend** —
le frontend n'en porte aucun, il ne fait que proxifier `/api/*`.

> **Aucun de ces réglages ne s'applique tout seul, sur aucun des deux services.**
> Ce fichier n'est lu par personne (voir plus haut) : `generateValue` n'a jamais
> joué, et la clé de session a été **saisie à la main** en production comme en
> preview. Les déclarations ci-dessus disent quelle valeur poser, pas qui la
> pose.

| Variable | PROD | PREVIEW | Local |
|---|---|---|---|
| `AUTH_SESSION_SECRET_KEY` | **à saisir à la main** | **à saisir à la main** | `python -c "import secrets; print(secrets.token_urlsafe(64))"` |
| `AUTH_GITHUB_CLIENT_ID` / `_SECRET` | application OAuth « prod » | application OAuth « preview » | application OAuth « local » |
| `AUTH_REDIRECT_BASE_URL` | URL de production de `data-triathlon` | URL de production de `data-triathlon-preview` | `http://127.0.0.1:3000` |
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
- **les *preview deployments* de Vercel sont hors périmètre** : leur URL change à
  chaque exécution, donc aucune URL de retour stable ne peut être enregistrée
  chez GitHub. C'est précisément pourquoi le job `deploy-preview` déploie en
  production du projet `data-triathlon-preview` (#172) : la connexion ne
  fonctionne que sur cette URL fixe. Le site public, lui, reste entier partout ;
- **la liste d'autorisation n'est plus une variable d'environnement** (#170) :
  elle vit dans la table `allowed_emails`, éditable depuis `/admin/acces` sans
  redéploiement. Une liste vide interdit toujours toute connexion — le refus
  tombe désormais au **retour** du parcours (`account_not_allowed`) et non plus à
  son entrée, `/auth/methods` n'interrogeant aucune table. Un refus se
  diagnostique **dans les journaux du backend**, où l'adresse soumise est tracée ;
  le code rendu au visiteur, lui, reste muet sur la valeur (FR-030). L'amorçage
  d'une installation neuve passe par
  `uv run python -m app.cli allow-email --email <adresse>`.

### Mettre en production la liste d'autorisation en base (#170)

**L'ordre compte, et l'inverser ferme l'accès à tout le monde.** La migration qui
crée `allowed_emails` reprend, au moment du `alembic upgrade head` du
`startCommand`, ce que porte encore `AUTH_ALLOWED_EMAILS` dans l'environnement du
processus. Elle s'exécute donc **avant** la première requête : il n'y a pas de
fenêtre pendant laquelle un contributeur autorisé se verrait refuser la connexion.

1. **Déployer.** La table est créée et remplie depuis la variable.
2. **Vérifier** dans `/admin/acces` (« Gestion des utilisateurs » → « Accès au
   back-office ») que les adresses attendues y sont.
3. **Seulement ensuite**, et dans une PR de suivi, retirer l'entrée de
   `render.yaml` puis la variable du tableau de bord Render. Elle y est
   volontairement **conservée** par la livraison qui pose la table : c'est elle
   que lit la reprise, et la retirer d'un même geste ferait dépendre la
   production d'un comportement non vérifié — Render supprime-t-il une valeur
   `sync: false` quand la clé disparaît du blueprint ? Une variable qui traîne
   est **inoffensive** (`Settings` porte `extra="ignore"`) ; une variable
   supprimée trop tôt ferme l'accès à tout le monde.

**Si l'étape 2 montre une liste vide** — reprise manquée, variable absente au
moment de la migration —, le rattrapage **n'est pas** `allow-email` : les deux
services backend tournent en `plan: free`, qui n'ouvre aucun shell. Il faut
passer par la console SQL de Supabase :

```sql
INSERT INTO allowed_emails (email, created_at)
VALUES ('votre.adresse@exemple.fr', now())
ON CONFLICT (email) DO NOTHING;
```

L'adresse doit être écrite **en minuscules et sans espaces** : c'est la forme
normalisée que le code compare, et une majuscule y serait invisible et
silencieuse. Une connexion suffit ensuite à créer le compte, puis `grant-role`
depuis un environnement qui a un shell.

### Secrets GitHub

Presque tous sont des **secrets d'environment** — Settings → Environments →
`preview` / `production` → *Environment secrets* — et non des secrets de dépôt.
Un job ne voit que ceux de l'environment qu'il déclare, plus ceux du dépôt.

| Secret | Portée | Usage |
|---|---|---|
| `RENDER_DEPLOY_HOOK_PREVIEW` | environment `preview` | URL du deploy hook Render preview |
| `RENDER_DEPLOY_HOOK_PROD` | environment `production` | URL du deploy hook Render prod |
| `RENDER_API_KEY` | **dépôt** | Clé d'API Render — injecte `APP_VERSION` avant chaque hook (#162) |
| `VERCEL_TOKEN` | les deux environments | Token CLI Vercel |
| `VERCEL_ORG_ID` | les deux environments | ID de l'organisation Vercel |
| `VERCEL_PROJECT_ID` | les deux environments | ID du projet Vercel — **valeurs différentes** (cf. plus bas) |

`RENDER_API_KEY` se crée dans le dashboard Render → *Account Settings* → **API
Keys** ; sa valeur n'est affichée qu'à la création. Elle est portée par le compte
et couvre les deux services, d'où une **saisie unique au niveau dépôt**.

C'est le seul secret dans ce cas, et le compromis est à connaître : c'est aussi
le plus puissant du lot — un deploy hook ne sait que déclencher un déploiement,
cette clé écrit sur toute l'infrastructure Render du workspace. Un secret de
dépôt est lisible par **tout workflow de n'importe quelle branche**, là où un
secret d'environment `production` protégé par une *required reviewer* ne se
délivre qu'après approbation. La déplacer sur les deux environments (même valeur,
saisie deux fois) resserre cette portée sans rien changer au workflow.

À ne pas confondre avec les `RENDER_DEPLOY_HOOK_*`, qui ne sont **pas** des
jetons d'API : un deploy hook déclenche un déploiement et rien d'autre, il
n'ouvre aucun accès à `api.render.com/v1`. D'où une clé distincte pour écrire
`APP_VERSION`.

Le service visé, lui, ne se saisit pas : il est **extrait du deploy hook**
(`…/deploy/srv-…`), ce qui interdit par construction de pousser la version prod
sur la preview. Sans la clé — ou avec une clé révoquée — le job échoue et rien
n'est déployé : ce n'est pas un secret optionnel.

`VERCEL_PROJECT_ID` est le seul dont la **valeur** diffère d'un environment à
l'autre : l'ID de `data-triathlon-preview` sur `preview`, celui de
`data-triathlon` sur `production`. C'est ce qui route la preview vers le second
projet Vercel (#172) sans qu'aucun job n'ait à nommer sa cible.

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

### Environments GitHub — requis, et un garde-fou optionnel

Les *Environments* `preview` et `production` sont **nécessaires** : les deux jobs
les déclarent, et c'est `preview` qui porte le `VERCEL_PROJECT_ID` du projet
preview (voir plus haut).

Optionnel mais recommandé : ajouter une **required reviewer** sur `production` —
un tag `v*` déclenchera la CI, mais la mise en production attendra une validation
manuelle.

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
2. Merger dans `main` (ou lancer un `workflow_dispatch`) → `deploy.yml` enchaîne
   `ci` puis `deploy-preview` : hook Render preview + déploiement sur l'URL fixe
   de `data-triathlon-preview`. Relancer une fois : **la même URL**.
3. Sur cette preview, vérifier qu'on interroge bien le backend Render *preview*
   (footer de version + une lecture API).
4. `git tag v0.1.0 && git push --tags` → `ci` puis `deploy-production`
   (hook Render prod + déploiement sur `data-triathlon`, inchangé).
5. **Fermer la boucle de version** (#162), la seule vérification qui éprouve les
   deux moitiés du correctif : `curl -s <URL prod>/api/v1/version` doit rendre le
   tag — et non « dev », ni le tag précédent —, et le déploiement affiché dans le
   dashboard Render doit porter le **commit taggé**, pas le HEAD de `main`. Le
   premier valide l'écriture d'`APP_VERSION`, le second le `&ref=` du hook. Un
   déploiement relancé à la main depuis le dashboard, lui, réutilise
   l'`APP_VERSION` en place : il annoncerait le tag précédent sur du code plus
   récent. Après une telle relance, retaguer ou corriger la variable à la main.
6. Sur une CI volontairement cassée (erreur ruff/test), confirmer que le job de
   déploiement **n'est pas exécuté**.
