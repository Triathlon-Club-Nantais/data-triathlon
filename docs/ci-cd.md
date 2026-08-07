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
| `AUTH_ALLOWED_EMAILS` | adresses des contributeurs, en CSV | idem, ou vide pour fermer | votre adresse GitHub vérifiée |
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
- `AUTH_ALLOWED_EMAILS` **vide interdit toute connexion** et fait rendre `[]` à
  `/auth/methods`. Ce n'est pas un défaut permissif : une variable oubliée sur
  Render ferme l'accès au lieu de l'ouvrir à n'importe quel compte GitHub.
  Deux conséquences d'exploitation : **ajouter un contributeur exige un
  redéploiement** (`get_settings` est en `lru_cache`, la liste est lue au
  démarrage du processus) ; et un refus se diagnostique **dans les journaux du
  backend**, où l'adresse soumise est tracée — le code rendu au visiteur, lui,
  reste muet sur la valeur (FR-030).

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

## Batches de production — `batch.yml` (#47)

Les batches de mise à jour des résultats (`rescrape-db`, import d'une liste
d'URL) ne tournent **pas** dans le service web : celui-ci est sur l'offre
gratuite, un seul process, et un batch de plusieurs dizaines de minutes y
priverait le site public de sa ressource. Ils tournent sur un runner GitHub
Actions, qui lance la CLI.

### Deux environments dédiés : `batch-preview` et `batch-production`

Un par base. Les deux environments ne portent **pas les mêmes secrets** parce
qu'ils ne visent pas la même infrastructure : la preview vit sur Supabase, la
production sur Azure PostgreSQL Flexible Server (voir `docs/infra-azure.md`).

| Secret | Portée | Usage |
|---|---|---|
| `DATABASE_URL` | environment `batch-preview` | Base de preview (Supabase, hôte pooler) |
| `DATABASE_URL` | environment `batch-production` | Base de production (Azure PG Flexible) |
| `AZURE_CLIENT_ID` | environment `batch-production` | Fédération OIDC — service principal `gh-batch-data-triathlon` |
| `AZURE_TENANT_ID` | environment `batch-production` | Tenant du service principal |
| `AZURE_SUBSCRIPTION_ID` | environment `batch-production` | Souscription contenant le serveur PG |
| `AZURE_RESOURCE_GROUP` | environment `batch-production` | RG du serveur PG (`TCN_Data_BDD`) |
| `AZURE_POSTGRES_SERVER` | environment `batch-production` | Nom du serveur (`tcndatabdd`) |

C'est l'environment, et lui seul, qui décide de la base écrite : rien dans le
script du workflow ne la nomme. La cible est choisie par l'entrée `target`, avec
un défaut `preview` — un lancement manuel distrait ne doit pas écrire chez les
adhérents — et un repli sur `production` quand aucune entrée n'est fournie,
c'est-à-dire pour les exécutions **planifiées**.

Les cinq secrets `AZURE_*` ne sont ni sensibles au sens strict (ce sont des
identifiants publics de la souscription) ni des jetons long-lived. Ils sont
posés en secrets pour que rien de l'infrastructure Azure ne fuite dans les
logs GHA. Le seul secret à vrai dire *puissant* est l'accès Azure lui-même, et
il n'existe que sous forme de jeton OIDC éphémère, émis par GitHub à ce job
précis et accepté par Azure via le federated credential dont le `subject`
mentionne l'environment nominativement.

Côté application, la cible n'est **pas** un choix offert dans l'écran : elle vient
du réglage `GITHUB_BATCH_TARGET` de l'instance. L'administration de la preview
écrit dans la base de preview, celle de la production dans la sienne ; un champ
dans le formulaire permettrait à l'une d'écrire chez l'autre.

**Environment dédié, et non `Production`** — deux raisons, toutes deux
constatées sur le dépôt :

- `Production` **ne porte pas** de `DATABASE_URL` : ses secrets sont les jetons
  de déploiement (Render, Vercel). L'URL de la base vit côté Render, en variable
  de service. Il n'y a donc rien à réutiliser ;
- `Production` porte une **`required_reviewers` active**. Un job qui la déclare
  ne démarre qu'après approbation humaine — excellent pour un déploiement,
  rédhibitoire pour une action déclenchée depuis un écran : le batch resterait
  en attente pendant que l'interface annonce « en cours ».

Et pas un **secret de dépôt** non plus : il serait lisible par tout workflow de
n'importe quelle branche (cf. le compromis assumé de `RENDER_API_KEY` plus
haut), ce qui est la pire portée pour la base de production.

Ce qui contrôle l'accès ici, c'est le pouvoir `batch:run` côté application.

### L'hôte de la base : viser le **pooler**, pas la connexion directe

C'est le piège de cette configuration côté Supabase, et il ne se devine pas.

Les runners GitHub hébergés **n'ont pas d'IPv6**, alors que l'hôte de connexion
directe de Supabase (`db.<ref>.supabase.co`) résout en IPv6 seule sur les projets
récents. Une `DATABASE_URL` pointant dessus donne un **échec de connexion
réseau** au démarrage du batch, sans le moindre rapport apparent avec le code.

Le secret doit donc porter l'hôte du **pooler** (`…pooler.supabase.com`),
joignable en IPv4. En cas de doute, préférer le mode *session* au mode
*transaction* : ce dernier ne supporte pas les instructions préparées côté
serveur, et un batch ouvre une connexion longue.

Vérification, à faire **avant** tout batch réel : lancer `batch.yml` en
`mode: rescrape`, `limit: 1`, `dry_run: true`. Vert en moins d'une minute.

### L'hôte Azure : ouvrir le pare-feu au run (#243)

Le serveur PostgreSQL de production est un Azure Flexible Server protégé par
liste d'IP (voir `docs/infra-azure.md` pour l'inventaire). Les runners GHA
hébergés n'ont ni IP fixe, ni range assez étroit pour un allowlist statique :
`api.github.com/meta` publie plusieurs milliers d'adresses. Deux options
écartées, chacune pour une bonne raison :

- **« Allow public access from any Azure service »** — trop large sur une base
  d'adhérents, exposerait à toute VM Azure tierce.
- **Self-hosted runner** — sur-dimensionné pour quelques exécutions par jour et
  réintroduit la dépendance à une machine.

La voie retenue est une **ouverture *just-in-time*** : un step ajoute l'IP du
runner en règle firewall nommée `gh-batch-<run_id>`, un dernier step la
supprime en `if: always()`. La règle est donc imputable à une exécution
précise, et refermée même en cas d'échec du batch.

**Authentification Azure par OIDC**, sans secret long-lived. Le service
principal `gh-batch-data-triathlon` porte un rôle custom scopé au serveur —
`PG Firewall Rule Writer (tcndatabdd)`, actions `firewallRules/{read,write,delete}`
et rien de plus — et un federated credential dont le `subject` mentionne
`batch-production` : le jeton n'est délivré qu'à ce job. Toute la mise en
place tient dans quatre commandes `az`, décrites dans l'issue #243.

Diagnostic si le batch échoue au step `Open Azure firewall` :

- `azure/login` KO → `subject` du federated credential ne correspond pas
  exactement à `repo:Triathlon-Club-Nantais/data-triathlon:environment:batch-production`,
  ou `AZURE_CLIENT_ID` / `AZURE_TENANT_ID` erronés.
- `az … firewall-rule create` KO → l'assignation de rôle n'est pas visible
  (propagation courte, mais réelle), ou le scope ne cible pas le serveur.

Vérification, à faire **avant** tout batch réel : lancer `batch.yml` en
`target: production`, `mode: rescrape`, `limit: 1`, `dry_run: true`. Vert en
moins d'une minute. Pendant l'exécution, la règle `gh-batch-<run_id>` est
visible via `az postgres flexible-server firewall-rule list -g TCN_Data_BDD -s tcndatabdd` ;
après, elle a disparu.

### Lancer un batch sans l'interface

C'est le repli quand l'interface d'administration est indisponible, et c'est
aussi la seule voie tant que la partie applicative n'est pas déployée : onglet
**Actions** → *Batch* → **Run workflow**, puis renseigner le mode et ses options.
Les entrées y sont les mêmes que celles envoyées par l'interface.

Deux propriétés du workflow à connaître avant d'y toucher :

- **aucune entrée n'est interpolée dans un script** — elles transitent par `env:`
  et sont lues citées. Une valeur d'entrée vient d'un fichier téléversé par un
  humain, et un `run:` la substituerait avant le shell, sur une machine qui
  détient la base de production. `backend/tests/test_workflows.py` tient la
  règle ;
- **un seul batch à la fois par base** (`concurrency: batch-<cible>`), et un job
  borné à deux heures. Le groupe porte la cible : un batch de preview
  n'empêche pas un batch de production, ce sont deux bases. Sans la borne de
  durée, une exécution coincée rendrait tout lancement impossible six heures
  durant.

Le bilan sort en deux formes : le rapport texte dans le résumé de l'exécution, et
la charge `--json` en artefact `bilan-<id>.json` (90 jours). Un batch dont
**toutes** les épreuves échouent sort en code 1 et rend l'exécution rouge ; un
échec partiel reste vert, avec le détail des épreuves fautives dans le bilan.

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
