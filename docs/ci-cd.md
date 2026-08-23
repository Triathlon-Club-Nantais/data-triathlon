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
- **`.github/workflows/render-sleep.yml`** — suspend et reprend les deux
  services Render pour tenir les 750 h/mois du plan free (#528, décision #530).
  `schedule` deux fois par jour, plus un `workflow_dispatch` de secours. Voir
  « Veille des services Render » plus bas.
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
| **PROD** | `triathlon-backend-production` | dashboard Render → service `triathlon-backend-production` → Settings |
| **PREVIEW** | `triathlon-backend-preview` (créé via MCP) | dashboard Render → service `triathlon-backend-preview` → Settings |

> Les IDs de service (`srv-…`) et les URLs publiques sont visibles dans le
> dashboard Render ; ils ne sont volontairement pas committés ici (dépôt public).

> **Le service de prod ne s'appelle pas `data-triathlon`** — c'est le nom du
> dépôt. Ce tableau l'a écrit jusqu'ici, comme `render.yaml` avant #259 ; le
> constat est celui de l'audit OWASP du 16/08/2026. Le *slug* du service, lui,
> est `data-triathlon-vq6u`, d'où l'URL `.onrender.com`. La distinction n'est
> plus documentaire depuis `render-sleep.yml`, qui résout les services **par
> leur nom** via l'API : un nom faux y sort rouge, il ne vise pas à côté.

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

**`DOCS_ENABLED` — un seul service la porte** (#399). Elle commande `/docs`,
`/redoc` et `/openapi.json`, et le code les **ferme par défaut** : la production
n'a donc rien à saisir, et c'est le service **preview** qui déclare
`DOCS_ENABLED=true` dans ses variables. Le sens du défaut n'est pas anodin —
`render.yaml` n'étant appliqué par personne, un défaut ouvert aurait fait
dépendre le correctif d'une saisie au dashboard, et une saisie oubliée ne se
voit pas (c'est exactement ce qu'a coûté #162). Vérification après déploiement :
`GET /docs` doit rendre **404** en production et **200** en preview.

**`CORS_ORIGINS` — celle dont une erreur ne se voit pas** (#402, constat A05-3 de
l'audit OWASP). Elle liste, en CSV, les origines autorisées à appeler l'API
depuis un navigateur. Le défaut du code ouvre les quatre origines locales
(`127.0.0.1` et `localhost`, ports 3000 et 5173 —
`backend/app/core/config.py`) : inutilisable en production, et pourtant **sans
aucun symptôme**. L'interface proxifie `/api/*` par un rewrite Next
(`frontend/next.config.ts`), donc ses appels partent en *same-origin* et
n'exercent jamais CORS. Mesuré le 16/08/2026 : la production ne renvoie aucun
en-tête `Access-Control-Allow-*`, et une origine hostile reçoit un 400 au
preflight. `allow_credentials` n'est jamais activé (`backend/app/main.py`), donc
aucun cookie ne peut partir en cross-origin.

| Variable | PROD | PREVIEW | Local |
|---|---|---|---|
| `CORS_ORIGINS` | origine de production du projet Vercel `data-triathlon` | origine de production du projet Vercel `data-triathlon-preview` | défaut du code (les quatre origines locales) |

À saisir **tout de même**, sur les deux services : le jour où un appel direct au
backend existe, l'oubli tombe côté navigateur. Et la valeur ne vit que dans le
dashboard Render, où rien ne la garde — un `*` posé « pour déboguer » ouvrirait
l'API à toute origine, et c'est justement l'absence de symptôme qui ferait durer
l'ouverture : aucune revue ne la voit passer, aucun écran ne s'en plaint. #402 ne
corrige pas le comportement, qui est bon, mais ce défaut de traçabilité.

### Rester sous les 750 h du plan free — la décision (#530)

Les deux services web se partagent **750 h d'instance par mois** pour tout le
workspace : au-delà, Render suspend l'ensemble des services free jusqu'au mois
suivant. Trois pistes ont été posées ; voici celle qui est retenue et pourquoi
les autres ne le sont pas.

**Retenu — suspendre les deux environnements par routine `schedule`** (piste 1,
mise en œuvre dans #528). C'est la seule option qui ne change ni d'hébergeur, ni
de compte, ni de facture : on garde la main sur la configuration serveur — c'est
l'objection qui a ouvert cette décision —, le coût reste nul, et un retour en
arrière tient dans la suppression d'un workflow. Elle s'appuie sur ce qui existe
déjà : l'API Render `suspend`/`resume` et le secret `RENDER_API_KEY` du dépôt.
La fenêtre horaire, le sort de la preview et la validation du couple
suspend/resume sur le plan free relèvent de #528, pas d'ici.

**Écarté — un second compte Vercel sur un alias Google** (piste 2). Vérifié, pas
supposé : les *Fair Use Guidelines* de Vercel (consultées le 23/08/2026) posent
que « circumventing or otherwise misusing Vercel's limits or usage guidelines is
a violation of our fair use guidelines », et renvoient aux conditions générales.
Ouvrir un second compte gratuit pour le même projet est précisément un
contournement de quota : le risque n'est pas la suspension du nouveau compte
seul, mais des deux — donc de la production. S'y ajoutent un coût de migration
non nul (deux projets, domaines, `VERCEL_TOKEN` / `VERCEL_ORG_ID` /
`VERCEL_PROJECT_ID`, URL de retour SSO #172, protection de déploiement) et un
accès suspendu à un alias détenu par une seule personne. Le rapport risque/gain
ne tient pas.

**Écarté — migrer le backend chez Vercel.** On y perd la main sur la
configuration serveur et le déploiement devient plus exigeant, pour un service
qui scrape et travaille en tâche de fond — pas le profil d'une fonction.

**Repli, si la mesure d'usage de #528 montre un dépassement malgré la routine** :
passer **un seul** des deux services (la production) sur un plan payant Render,
et laisser la preview sur le free. À ne décider que sur des heures relevées.

> Reste ouvert : le relevé d'usage réel (dashboard Render → workspace → *Usage*)
> demandé par #528. Il ne conditionne pas la décision ci-dessus — il conditionne
> le repli.

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
     **preview**. Sans ça, la preview taperait la base de production ;
   - `data-triathlon` **seul** : `NEXT_PUBLIC_POSTHOG_PROJECT_TOKEN` /
     `NEXT_PUBLIC_POSTHOG_HOST` (`https://eu.posthog.com`, cloud EU — RGPD),
     valeurs dans PostHog → Project settings → API keys. **À ne pas saisir sur
     `data-triathlon-preview`** : il n'existe qu'un projet PostHog, et le trafic
     de test n'a rien à faire dans les mêmes statistiques que celui du club
     (#426). Absentes, l'app tourne normalement, juste sans analytics et sans un
     mot en console (garde dans `instrumentation-client.ts`).
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
| `SITE_ACCESS_SESSION_TTL_DAYS` (#509, hors SSO — mot de passe d'accès au site) | défaut (7 j) | défaut | défaut |

> **Régénérer `AUTH_SESSION_SECRET_KEY` ne ferme aucune session.** C'est
> l'attente naturelle, et elle est fausse : le jeton de session est **opaque et
> vérifié en base**, il n'est pas signé — cette clé ne signe que le jeton
> d'état. Une rotation n'interrompt donc que les parcours de connexion en cours
> (600 s de fenêtre), et croire l'inverse ferait tenir une fuite pour colmatée.
> Pour fermer réellement les sessions, il y a désormais un outil et non une
> procédure (#169) : `/admin/acces` depuis le back-office — par adresse ligne à
> ligne, globale en bas de page —, ou `uv run python -m app.cli revoke-sessions
> --all` sur le serveur, ce second chemin restant praticable le jour où c'est du
> back-office qu'on se méfie. Pour une seule personne :
> `revoke-sessions --email <adresse>`. Ne plus passer par `psql` : c'est ce que
> #169 a retiré.
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

### Ajouter une adresse autorisée sans passer par `/admin` (#170)

La liste d'autorisation vit en base depuis #170. Sa mise en production est
**terminée** : la migration `a107b77b53e8` a repris ce que portait
`AUTH_ALLOWED_EMAILS` (livrée en v0.2.0), la reprise a été constatée dans
`/admin/acces`, et la variable a été retirée du blueprint comme des deux services
Render (#259). Ne pas la réintroduire — `Settings` porte `extra="ignore"`, elle
serait ignorée en silence.

Reste le cas d'une **liste vide** : installation neuve, ou base repartie de zéro.
Le rattrapage **n'est pas** `allow-email` : les deux services backend tournent en
`plan: free`, qui n'ouvre aucun shell. Il faut passer par la console SQL de
Supabase :

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

`VERCEL_TOKEN` et `RENDER_API_KEY` **n'expirent pas** et n'ont pas de rotation
programmée : c'est un choix, pas un oubli (#259). Une rotation régulière sur une
infrastructure tenue par une poignée de bénévoles coûterait plus qu'elle ne
protège, le jour où la clé n'est plus valable étant un déploiement qui échoue —
bruyamment, sans rien casser en production. Les deux se révoquent en revanche
**immédiatement** au moindre doute de fuite (dashboard Vercel / Render →
*Account Settings*), la révocation ne touchant aucun service en marche.

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

### Code scanning — CodeQL, deux analyses distinctes (#394)

Deux analyses CodeQL tournent en parallèle sur le dépôt, sans lien l'une avec
l'autre malgré un nom de mécanisme partagé (« dynamic/github-code-scanning/codeql ») :

- **`code-quality`** — déjà en place avant #394, non désactivable depuis
  l'API ni l'UI classique de default setup : c'est une fonctionnalité distincte
  (aperçu « Code quality »), dont les alertes ne sont exposées par aucune route
  REST (constaté dans le sondage `docs/superpowers/specs/2026-08-04-code-quality-codeql-sondage.md`).
- **`code-scanning` (sécurité)** — activée par #394. `GET
  /repos/…/code-scanning/default-setup` répondait `"state": "not-configured"` :
  le dépôt n'avait **aucun SAST** malgré l'analyse qualité qui tournait déjà
  (constat A08-1 de l'audit OWASP). Activée via :

  ```bash
  gh api --method PATCH repos/Triathlon-Club-Nantais/data-triathlon/code-scanning/default-setup \
    --input - <<'JSON'
  {
    "state": "configured",
    "query_suite": "default",
    "languages": ["python", "javascript-typescript", "actions"],
    "runner_type": "standard"
  }
  JSON
  ```

  Vérifié après coup : `code-scanning/alerts` et `code-scanning/analyses`
  rendent désormais du contenu (3 analyses, une par langage), là où ils
  répondaient `404 no analysis found` avant l'activation — c'est la default
  setup qui ne tournait pas, pas une question de filtrage. Le paramètre
  `query_suite` de cette API n'accepte que `default` / `extended` : il n'existe
  pas de valeur « security-and-quality » à ce niveau, contrairement au
  paramètre `queries:` d'un workflow CodeQL explicite — la distinction
  sécurité/qualité est portée par deux mécanismes séparés, pas par un choix de
  suite sur l'un des deux.

  Le langage `actions` est inclus : les requêtes de sécurité GitHub Actions
  (injection de commande, cache poisoning, permissions manquantes…) relèvent
  du même A08 (intégrité logicielle) que le constat d'origine.

**Non traité par #394, à noter pour qui reprendrait le sujet** : la propriété
d'organisation `github-codeql-config-file`, qui doit fusionner
`.github/codeql/codeql-config.yml` (filtrage `backend/alembic/versions` et
`backend/tests/fixtures`) dans la configuration générée, n'a jamais été posée
sur ce dépôt — `GET /repos/…/properties/values` n'en rend aucune trace (réponse
`[]`, aucune valeur explicite déclarée). Vérifié après l'activation de #394 :
le groupe de log « Augmented user configuration file contents » du run de
sécurité ne contient aucun `paths-ignore`. C'est un reste du sondage du
2026-08-04 (§7, « reste à faire ») jamais posé, indépendant de #394 : la poser
demanderait un `PATCH /repos/…/properties/values` au niveau organisation, hors
périmètre d'un chore sur un seul dépôt.

### SAST dans le lint — ruff `S` (flake8-bandit)

CodeQL vit côté GitHub ; le second filet vit dans la CI et sur le poste du
développeur. `S` est activé dans `backend/pyproject.toml` : bandit est **déjà
embarqué dans ruff**, donc aucune dépendance ni job de CI en plus, et
`uv run ruff check .` (déjà bloquant) suffit à le faire tourner.

Les deux outils ne voient pas les mêmes choses — à l'activation, **6 des 7
constats de ruff `S` étaient invisibles pour CodeQL**, et les 6 alertes CodeQL
ouvertes sont invisibles pour ruff. Ce qui a été traité :

- `S314` — `xml.etree` sur les flux scrapés (timepulse, wiclax) : parsing
  basculé sur **defusedxml**, qui refuse les bombes d'entités.
  `backend/tests/test_xml_hardening.py` verrouille le comportement.
- `S105` / `S104` — faux positifs sur des constantes d'URL, et le bind
  `0.0.0.0` volontaire du serveur de dev : `# noqa` motivés sur place.

`tests/**` est neutralisé via `per-file-ignores` : les tests ne sont pas une
frontière de confiance, et `S101` (`assert`) y sort 5347 fois.

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

Le bilan sort en **trois** formes : les 200 derniers Ko du rapport texte dans le
résumé de l'exécution, le rapport entier en artefact `rapport-<id>`, et la charge
`--json` en artefact `bilan-<id>.json` (90 jours chacun). Un batch dont
**toutes** les épreuves échouent sort en code 1 et rend l'exécution rouge ; un
échec partiel reste vert, avec le détail des épreuves fautives dans le bilan.

Le résumé est borné parce que la plateforme refuse **en entier** un
`$GITHUB_STEP_SUMMARY` de plus d'1 Mo : il ne tronque pas, il perd tout. Le
journal de scraping d'une seule épreuve suffit à l'atteindre (mesuré à 1029 Ko
sur le run 31202351491), d'où l'artefact séparé.

### Le jeton d'accès à la plateforme

Le réglage `GITHUB_BATCH_TOKEN` de l'instance porte un jeton **fine-grained**,
restreint à ce dépôt, avec la seule permission `actions: write` — de quoi
déclencher un `workflow_dispatch` et lire les exécutions, rien d'autre.

**Vide est un état légitime**, même politique que les réglages `AUTH_*` : le
lancement s'annonce alors non configuré et le reste du site est intact. Les deux
refus possibles portent des messages **distincts**, et c'est ce qui rend le
diagnostic possible sans accès aux journaux :

| Message rendu | Cause |
|---|---|
| « Le lancement de batches n'est pas configuré sur ce site. » | réglage absent |
| « Le jeton d'accès … est expiré ou révoqué. » | 401/403 de la plateforme |

Un jeton fine-grained expire — un an au plus. Le régénérer se fait dans
*Settings → Developer settings → Fine-grained tokens*, puis mise à jour du
réglage sur Render. Aucune autre action n'est requise : le workflow, lui, ne
connaît pas ce jeton.

**C'est la seule échéance de l'infrastructure**, et elle ne se recopie pas ici :
une date écrite dans un document diverge à la première régénération. La source
qui fait foi est l'écran *Fine-grained tokens*, qui affiche l'expiration de
chaque jeton ; GitHub prévient par courriel une semaine avant. Le jour où elle
tombe sans avoir été vue, le symptôme est borné — l'écran de lancement des
batches refuse en nommant la cause (tableau ci-dessus), et rien d'autre du site
ne bouge (#259).

### Reprise périodique — `schedule` (#47)

```yaml
schedule:
  - cron: "0 3 * * 1"   # lundi 3 h UTC
```

Le lundi ramasse les épreuves du week-end, à une heure creuse. Une occurrence
planifiée ne porte **aucune entrée** : c'est le mode `rescrape` sans filtre qui
s'exécute, et c'est la raison du repli `|| 'production'` sur `environment` et
`concurrency`. Sans lui, le cron hériterait du défaut `preview` et ne
rafraîchirait jamais la base réelle — une panne qu'on ne découvre qu'en
cherchant pourquoi les résultats datent.

Une occurrence planifiée est soumise au même verrou de concurrence qu'un
lancement manuel : elle est ignorée si un batch tourne déjà. C'est voulu.

**Deux pièges, tous deux silencieux :**

1. **GitHub désactive les workflows planifiés d'un dépôt sans activité depuis
   60 jours** (D13). Rien ne casse, rien n'est notifié : le cron cesse
   simplement de se déclencher. Un dépôt actif ne le rencontre pas, mais une
   période creuse suffit. La seule parade est de le constater — d'où le rappel
   de suivi à J+30 et le contrôle de SC-007 (quatre échéances consécutives sans
   intervention).
2. **La durée.** Le job est borné à 120 minutes, et l'import paie aujourd'hui
   deux requêtes par participant contre une base distante (issue #258) : une
   reprise complète peut atteindre la borne. Elle sort alors **rouge**, ce qui
   est bruyant et donc acceptable — mais tant que #258 n'est pas traité, la
   reprise hebdomadaire est à surveiller, voire à borner par un `limit`.

**Destinataire de la notification d'échec** : la plateforme notifie l'auteur de
la dernière modification du fichier de cron, pas l'équipe. À constater sur la
première occurrence rouge (quickstart §12) ; si ce n'est pas la bonne personne,
c'est l'hypothèse « aucun canal d'alerte nouveau » de la spec qu'il faut
rouvrir, pas une situation avec laquelle vivre.

## Veille des services Render — `render-sleep.yml` (#528)

Les deux services web se partagent **750 h d'instance par mois** sur tout le
workspace : au-delà, Render suspend l'ensemble des services free jusqu'au mois
suivant. Le mois faisant 730 h, deux services éveillés en permanence en
réclament 1460. Le workflow les couche, par l'API Render (`POST
/v1/services/{id}/suspend` et `/resume`, 202, jeton `RENDER_API_KEY` déjà présent
au niveau dépôt).

**Deux régimes, et c'est délibéré** :

| Service | Coucher | Lever |
|---|---|---|
| **production** | cron `0 1 * * *` | cron `0 4 * * *` |
| **preview** | cron `0 1 * * *` | **jamais par cron** — `deploy.yml` la reprend avant son deploy hook |

La preview ne se rallume que pour servir la vérification post-déploiement, puis
attend la nuit. C'est là qu'est le gros du quota : la fenêtre nocturne seule ne
rend que ~90 h par mois et par service, quand une preview qui ne s'éveille qu'à
la demande en rend plusieurs centaines.

**Heure UTC, pas heure de Paris.** Le cron d'Actions ignore l'heure d'été : la
coupure de production tombe entre 2 h et 5 h l'hiver, 3 h et 6 h l'été. Viser
Paris à la minute demanderait deux jeux de crons et une bascule saisonnière à
entretenir, pour une fenêtre qui reste nocturne dans les deux cas.

**La procédure de vérification ci-dessous n'est pas touchée** : le `resume`
précède le deploy hook dans `deploy.yml`, sur les deux environnements. C'est
nécessaire — un deploy hook envoyé à un service suspendu ne le rallume pas — et
c'est aussi le filet du paragraphe suivant.

**Le piège, le même que celui de `batch.yml` mais plus cher.** GitHub désactive
les workflows planifiés d'un dépôt sans activité depuis 60 jours (D13), sans
rien dire. Si la désactivation tombe entre le cron de 1 h et celui de 4 h, la
production reste **éteinte** jusqu'à ce que quelqu'un s'en aperçoive. Deux
parades, volontaires toutes les deux : le `workflow_dispatch` (`action: resume`,
`target: production`), et le `resume` de `deploy.yml` — un déploiement rallume
toujours sa cible, quel que soit l'état du cron.

**Ce workflow ne déclare aucun environment, et c'est la condition pour qu'il
fonctionne.** L'environment `Production` porte une *required reviewer* (cf.
« Environments GitHub » plus haut) : un job qui le déclarerait — comme le fait
`deploy.yml` pour lire son deploy hook — mettrait le lever de 4 h en attente
d'une approbation humaine, donc laisserait le site éteint jusqu'au clic, tous
les matins. D'où la résolution des services **par leur nom** via
`GET /v1/services`, qui ne demande que `RENDER_API_KEY`, secret **de dépôt**.

Le prix de ce choix est que les noms vivent dans le workflow. Ils n'y sont pas
un secret — ce document les porte déjà en clair, à la différence des `srv-…` —
et un renommage dans le dashboard fait sortir le job **rouge** plutôt que de le
laisser viser un autre service : le filtre `name` de l'API n'étant pas une
égalité, le workflow n'agit que sur une correspondance exacte et **unique**.

**À constater au premier passage réel**, dans cet ordre — la documentation
publique de Render ne répond ni à l'un ni à l'autre :

1. **Sur la preview d'abord** (`workflow_dispatch` → `suspend`, `target:
   preview`), que suspend/resume est bien ouvert au plan **free**. Si l'API le
   refuse, tout le dispositif tombe et le repli est le plan payant sur la seule
   production (décision #530).
2. Le code rendu quand le service est **déjà** dans l'état demandé — un cron qui
   sortirait rouge chaque nuit sur un service déjà suspendu serait du bruit à
   traiter, pas une panne.
3. Ce que voit un visiteur pendant la fenêtre coupée : Render ne sert pas de page
   de maintenance, l'appel échoue en erreur de connexion. Vérifier que le front
   Vercel rend une erreur lisible et non une page blanche.

Et le relevé qui reste dû : **les heures d'instance réellement consommées**
(dashboard Render → workspace → *Usage*), avant et après un mois plein de
routine. C'est lui qui dira si la routine suffit ou s'il faut basculer la
production sur un plan payant.

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
