# Audit — OWASP Top 10 (2021) du dépôt et des environnements

**Date** : 2026-08-16
**Issue** : #321
**Objet** : un verdict par catégorie OWASP sur le dépôt `data-triathlon` et ses
trois environnements, pièces à l'appui.
**Statut** : audit. Il **prime** sur le design, la spec et le plan. Toute
divergence se tranche en re-mesurant.

> **Ce document est publié.** `docs/` alimente GitHub Pages
> (`.github/workflows/pages.yml`) et le dépôt est public. Il ne cite donc
> **aucune valeur de secret** — emplacement et nature seulement — et décrit les
> faiblesses ouvertes en termes suffisants pour les corriger, jamais sous forme
> d'exploitation prête à l'emploi.

## Méthode

Trois sources, dans cet ordre de force : **la mesure sur environnement réel**,
la **lecture du code**, la **lecture de configuration de plateforme**.

- **Périmètre statique** : les 20 modules de routes de `backend/app/api/v1/`
  (dont 12 portant des ressources `/admin/`), `app/core/` (`http`, `permissions`, `config`, `exceptions`,
  `logging`), `app/services/auth/`, `frontend/` (App Router, `lib/api/`), les
  4 workflows de `.github/workflows/`, `render.yaml`, `.env.example`.
- **Mesures en production** (lecture seule, aucune écriture, aucune charge) :
  en-têtes HTTP, exposition de `/docs`, comportement CORS, redirection HTTPS,
  code de retour de 12 ressources sans session.
- **Mesures actives** : uniquement sur **preview**, et bornées à la
  démonstration du constat A04-1 — 13 signalements de test créés, tous titrés
  `[audit #321] … — a supprimer` (§Traces laissées).
- **Configuration de plateforme** : API GitHub (code scanning, secret scanning,
  Dependabot), API Render, API Vercel.

**Environnements**

| Rôle | Backend | Frontend | Version au moment de l'audit |
| --- | --- | --- | --- |
| production | Render `triathlon-backend-production` | Vercel `data-triathlon` | `v0.3.0` |
| preview | Render `triathlon-backend-preview` | — (projet Vercel preview **absent**, cf. §Écarts documentaires) | `v0.3.1-145-g7809a36` |
| local | SQLite | `next dev` | branche d'audit |

Les URL et identifiants de service ne sont pas recopiés ici (dépôt public,
convention posée par `render.yaml` et `docs/ci-cd.md`).

## Verdicts

| Catégorie | Verdict | Constats |
| --- | --- | --- |
| A01 Broken Access Control | **couvert** | 0 |
| A02 Cryptographic Failures | **couvert** | 1 (faible) |
| A03 Injection | **couvert** | 0 |
| A04 Insecure Design | **à corriger** | 3 (1 moyen prouvé, 2 moyens) |
| A05 Security Misconfiguration | **à corriger** | 3 (2 moyens, 1 faible) |
| A06 Vulnerable Components | **à corriger** | 2 (1 moyen, 1 faible) |
| A07 Identification & Authentication | **couvert** | 1 (faible) |
| A08 Software & Data Integrity | **à corriger** | 3 (1 moyen, 2 faibles) |
| A09 Logging & Monitoring | **couvert** | 0 |
| A10 SSRF | **couvert** | 1 (faible) |
| Secrets | **couvert** | 0 |
| Données personnelles | **à instruire** (#313) | 1 (faible) |

**14 constats**, dont **5 moyens** et **9 faibles**. Aucun critique, aucun élevé.

---

## A01 — Broken Access Control : **couvert**

**La priorité n°1 de l'issue ne produit aucun constat.** C'est le résultat le
plus solide de l'audit, et il tient à trois choses qui se renforcent.

**1. La garde est posée route par route, côté API, sur la totalité du
back-office.** Inventaire exhaustif des `@router` de `backend/app/api/v1/` :
toutes les ressources sous `/api/v1/admin/` portent un
`Depends(require_permission(P.X))`, **sauf** `POST /admin/pending-providers`
(`admin.py:31`), publique par conception et nommément déclarée telle. Aucun
`dependencies=` de router ni d'application — ce qui est précisément ce qui rend
cette exception vivable (`api/deps.py:88`, `api/v1/router.py:32`).

**2. Le rail de navigation n'est pas la garde, et le code le dit.**
`frontend/AGENTS.md` prévient du piège ; `frontend/app/admin/layout.tsx` se
documente lui-même comme « d'interface seulement ». Mesuré en **production**,
sans cookie :

| Ressource | Statut |
| --- | --- |
| `GET /api/v1/admin/users` | 401 |
| `GET /api/v1/admin/roles` | 401 |
| `GET /api/v1/admin/permissions` | 401 |
| `GET /api/v1/admin/allowed-emails` | 401 |
| `GET /api/v1/admin/groups` | 401 |
| `GET /api/v1/admin/batches` | 401 |
| `GET /api/v1/admin/athletes` | 401 |
| `GET /api/v1/admin/pending-providers` | 401 |
| `GET /api/v1/auth/me` | 401 |
| `GET /api/v1/auth/methods` | 200 (publique par contrat) |

**3. Un filet AST interdit la régression.**
`backend/tests/test_auth/test_public_routes_still_open.py` exige que toute
ressource sous le préfixe `/admin/` soit gardée **ou** déclarée publique
nommément (`ADMIN_PUBLIQUES`), et interdit toute dépendance globale sur
l'application et sur les routers. Une route ajoutée sans garde fait rougir la
CI — la protection ne dépend pas de la vigilance du relecteur.

**IDOR : sans objet, et pour une raison structurelle.** Aucune ressource de
l'API n'appartient à un utilisateur : athlètes, courses et participations sont
des données de club, et les pouvoirs sont globaux par conception (#115). Il n'y
a donc pas d'identifiant à cloisonner par propriétaire. Le seul objet
personnel est la **session**, résolue par le cookie et jamais par un
identifiant d'URL (`services/auth/session.py:61`) ; `GET /auth/me` ne porte que
sur soi et n'exige aucun pouvoir, ce qui est la bonne asymétrie.

**Deux points documentés et assumés, hors constat** : `sessions:revoke` n'a
aucun plafond (son porteur peut fermer toutes les sessions, y compris celle du
dernier administrateur — raisonnement complet dans
`backend/app/services/auth/AGENTS.md`) ; et `POST`/`DELETE /participations`
sont asymétriques (création publique depuis #270, suppression gardée), ce qui
est le choix explicite de la mise en quarantaine.

## A02 — Cryptographic Failures : **couvert** (1 constat faible)

**Cookie de session** (`api/v1/auth.py:87`) : `httponly`, `samesite=lax`,
`secure` piloté par `auth_cookie_secure`, **aucun attribut `Domain`**, et le
nom est *dérivé* du réglage — préfixe `__Host-` en production, qui ferme
l'écrasement depuis un sous-domaine. L'effacement reprend les mêmes attributs,
défaut corrigé et commenté sur place (RFC 6265bis §4.1.3).

**Jeton de session** : `secrets.token_urlsafe(32)` (256 bits), **empreinte
SHA-256 en base**, jamais la valeur ; la garde de longueur
(`TOKEN_MIN_LENGTH = 43`) est ce qui rend SHA-256 nu suffisant, et elle est
vérifiée à l'ouverture comme à la résolution.

**Jeton d'état** : JWS HS256 (`joserfc`), clé refusée sous 32 caractères au
démarrage (`core/config.py:134`), TTL 600 s, usage unique par effacement du
cookie sur **tous** les chemins de sortie.

**HTTPS** : forcé sur les deux plateformes — mesuré, `http://` → 301
(Render/Cloudflare) et 308 (Vercel).

> **Constat A02-1 — pas d'en-tête HSTS sur le backend.** *Faible.*
> Mesuré en production : la réponse de `GET /api/v1/health` ne porte aucun
> `Strict-Transport-Security`, là où le front Vercel pose
> `max-age=63072000; includeSubDomains; preload`. Le backend étant joignable
> directement (cf. A05-4), un premier appel en clair reste possible avant la
> redirection. **Environnement** : preview et production.
> **Correctif** : poser l'en-tête sur les réponses de l'API — même middleware
> que celui du constat A05-2, dont c'est une ligne.

## A03 — Injection : **couvert**

**SQL — aucune requête construite par concaténation.** Inventaire de tous les
`execute(`, `text(`, f-strings SQL et `.format(` de `app/repositories/`,
`app/services/`, `app/core/` et `app/api/` : **un seul** SQL littéral dans tout
le dépôt, `db.execute(text("SELECT 1"))` du *health check*
(`api/v1/health.py:20`), sans paramètre. Tout le reste passe par l'API
d'expression SQLAlchemy 2.0, paramétrée par construction. Les deux
`PRAGMA` de `core/database.py` sont des constantes de code.

**XSS — aucune surface.** Aucun `dangerouslySetInnerHTML`, `eval`, `innerHTML`
ni `new Function` dans `frontend/app`, `frontend/components`, `frontend/lib` et
`frontend/hooks`. React échappe, et rien ne le contourne. Le seul
`dangerouslySetInnerHTML` observable en production vient de la page 404 générée
par Next.js lui-même (bloc `<style>` constant).

**Injection de commande — fermée là où elle serait catastrophique.**
`.github/workflows/batch.yml` détient la base de production : **aucune valeur
d'entrée n'est interpolée dans un `run:`**, toutes transitent par `env:` et ne
sont lues que citées. `deploy.yml` applique la même règle au nom de tag
(`REF_NAME` par `env:`), et construit son JSON par `jq --arg`. La règle est
écrite en tête de fichier, avec sa vérification.

**Injection de log** : `core/sql_observability.py` écrase les espaces du SQL
**et** du label d'unité de travail — tous deux composés depuis des données
scrapées —, ce qui ferme le retour à la ligne dans le formateur JSON. Les
appels `logger.*` de `app/` passent par les arguments `%s`, jamais par
concaténation.

**Injection d'en-tête** : aucune valeur d'entrée n'atteint un nom ou une valeur
d'en-tête de réponse ; les seuls en-têtes écrits sont des constantes
(`NO_STORE_HEADERS`, les trois du flux SSE).

**Injection de chemin** : aucune ouverture de fichier pilotée par une entrée
utilisateur. Le seul téléversement (`admin_batches.py`) est lu **en mémoire**,
jamais écrit sur disque, et son corps est borné par lecture réelle et non par
`Content-Length`.

## A04 — Insecure Design : **à corriger** (3 constats)

> **Constat A04-1 — la limitation de débit des signalements est contournable
> par un en-tête que le client contrôle.** *Moyen. Prouvé par la mesure.*
>
> `POST /feedback` compte les soumissions récentes par adresse IP
> (`services/feedback_service.py:33`), l'IP venant de `request.client.host`
> (`api/v1/feedback.py:47`). Le `startCommand` Render lance `uvicorn` **sans**
> `--forwarded-allow-ips`, et le proxy de Render est local pour l'application :
> uvicorn fait donc confiance à `X-Forwarded-For`, que n'importe quel client
> peut écrire.
>
> **Mesure sur preview**, limite configurée à 5 par heure :
> - 7 soumissions avec un `X-Forwarded-For` **différent** à chaque fois → **7 ×
>   201**, aucune limitation ;
> - 6 soumissions avec le **même** `X-Forwarded-For` → 5 × 201 puis **429**.
>
> La seconde série établit que le compteur suit bien l'en-tête ; la première,
> qu'il suffit de le faire varier. C'est aujourd'hui **la seule limitation de
> débit du projet**.
> **Environnement** : preview et production (même `startCommand`).
> **Correctif** : décider explicitement de la chaîne de confiance —
> `--forwarded-allow-ips` limité à l'adresse du proxy de la plateforme, ou
> `ProxyHeadersMiddleware` configuré, et lecture de l'IP à ce seul endroit. Un
> compteur qu'on croit posé et qui ne l'est pas est pire qu'un compteur absent :
> il tient lieu de réponse à la question.

> **Constat A04-2 — aucune limitation de débit sur l'import d'épreuve.**
> *Moyen.*
>
> `POST /scrape/event` et `POST /scrape/event/stream` (`api/v1/scrape.py:35` et
> `:68`) sont **publics**, sans session ni plafond, et chacun déclenche une
> campagne de requêtes HTTP sortantes (jusqu'à ~26 vers un même hôte pour un
> fournisseur mesuré) suivie d'une écriture de plusieurs centaines de lignes.
> Le SSE ne prend même pas `optional_user`, il n'y a donc aucune trace de qui
> l'appelle. Sur l'offre gratuite Render (un process, limiteur de threads AnyIO
> mesuré à 40 et routes toutes `def`), quelques appels concurrents suffisent à
> saturer le site public — et le trafic sortant part vers des tiers depuis
> notre adresse.
> **Environnement** : preview et production. Le garde SSRF (A10) ferme la
> *destination*, pas le *volume* : ce sont deux problèmes distincts.
> **Correctif** : un plafond par IP — une fois A04-1 corrigé, l'IP étant
> jusque-là falsifiable — sur les deux routes de scraping, et le passage du SSE
> sous `optional_user` pour qu'un appel soit imputable. Le cache TTL de
> `services/cache.py` limite le re-scraping d'une **même** épreuve, jamais le
> nombre d'épreuves distinctes demandées.

> **Constat A04-3 — deux écritures publiques non bornées.** *Moyen.*
>
> - `POST /admin/pending-providers` (`api/v1/admin.py:31`) accepte
>   `PendingProviderCreate.url: str` — **aucune longueur maximale, aucune
>   validation de forme**, là où le champ jumeau de `FeedbackCreate` borne à
>   2000 caractères. La colonne est un `TEXT` côté PostgreSQL. Un anonyme peut
>   donc insérer des lignes de taille arbitraire, sans plafond de fréquence.
> - `POST /participations` (`api/v1/participations.py:59`) est publique depuis
>   #270 et crée athlète + course + participation. La mise en quarantaine
>   (`is_pending_validation=True`, forcée côté serveur) protège correctement les
>   **agrégats publics** — ce pour quoi elle a été conçue —, mais elle
>   n'empêche ni la croissance de la base, ni la pollution de la fiche d'un
>   athlète réel, sa seule surface d'affichage étant justement cette fiche.
>
> **Environnement** : preview et production.
> **Correctif** : borner `PendingProviderCreate.url` (`HttpUrl` ou
> `max_length`, sur le patron de `ScrapeRequest` et de `FeedbackCreate`), et
> poser sur ces deux routes le même plafond que celui d'A04-2. Ni l'un ni
> l'autre ne demande de fermer la route : c'est le volume qu'on borne, pas
> l'accès.

**Ce que le design fait bien, et qui n'est pas repris en constat** : `POST
/feedback` a un honeypot à réponse indiscernable ; `admin_batches` borne à 2 Mo
par comptage réel et refuse un lot au-delà de 500 épreuves plutôt que de le
tronquer ; la base visée par un batch vient du déploiement et jamais du corps
de la requête ; le retour de parcours SSO valide en local **avant** tout octet
réseau, avec un test qui le vérifie sur chaque chemin d'échec.

## A05 — Security Misconfiguration : **à corriger** (3 constats)

> **Constat A05-1 — `/docs` et `/openapi.json` exposés en production.**
> *Moyen.*
>
> Mesuré : `GET /docs` → **200**, `GET /openapi.json` → **200** sur le backend
> de production. `create_app()` (`app/main.py:85`) ne passe ni `docs_url=None`
> ni `openapi_url=None`. Le schéma complet de l'API — dont les 12 modules
> d'administration, leurs corps de requête et leurs codes d'erreur — est donc
> servi à qui le demande.
> **Nuance honnête** : le dépôt est public, aucun de ces chemins n'est un
> secret. Le gain est de retirer la carte prête à l'emploi et l'interface
> d'appel interactive, pas de cacher une information.
> **Environnement** : production (et preview, même code).
> **Correctif** : conditionner `docs_url` / `redoc_url` / `openapi_url` à un
> réglage, ouvert en développement et en preview, fermé en production.

> **Constat A05-2 — aucun en-tête de sécurité, ni côté API ni côté front.**
> *Moyen.*
>
> Mesuré en production. **Backend** : la réponse ne porte ni
> `X-Content-Type-Options`, ni `Referrer-Policy`, ni `X-Frame-Options`, ni
> `Content-Security-Policy` (ni HSTS, cf. A02-1). **Frontend** : Vercel pose
> HSTS et `x-robots-tag: noindex`, mais `next.config.ts` ne déclare **aucune**
> fonction `headers()` — pas de CSP, pas de `X-Frame-Options` /
> `frame-ancestors`, pas de `Referrer-Policy`, pas de `Permissions-Policy`. Le
> back-office est donc encadrable dans une iframe tierce, et la seule barrière
> contre un clickjacking sur les gestes destructifs est le `SameSite=Lax` du
> cookie.
> **Environnement** : preview et production.
> **Correctif** : `headers()` dans `next.config.ts` pour le front
> (`X-Frame-Options: DENY` ou `frame-ancestors 'none'`, `nosniff`,
> `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy`
> minimale) ; un middleware d'une dizaine de lignes côté API pour `nosniff`,
> `Referrer-Policy` et HSTS. La CSP mérite d'être traitée à part : Next.js et
> PostHog demandent un `nonce`, c'est le seul point qui coûte plus qu'une
> ligne.

> **Constat A05-3 — la valeur CORS de production n'est écrite nulle part.**
> *Faible.*
>
> Le **comportement** est bon : mesuré, une origine hostile reçoit un 400 sans
> `Access-Control-Allow-Origin` au preflight, et ni `http://localhost:3000`
> (le défaut du code) ni l'origine du front de production ne se voient
> attribuer d'ACAO — le front n'en a pas besoin, il proxifie `/api/*` côté
> serveur (`next.config.ts:16`). `allow_credentials` n'est jamais activé
> (`app/main.py:87`), donc aucun cookie ne peut partir en cross-origin.
> Ce qui manque est la **traçabilité** : `CORS_ORIGINS` n'apparaît ni dans la
> liste `envVars` de `render.yaml`, ni dans `docs/ci-cd.md`. Sa valeur réelle
> ne vit que dans le dashboard Render, où rien ne la garde. Une modification
> distraite — un `*` « pour déboguer » — ouvrirait l'API à toute origine sans
> qu'aucune revue ne la voie.
> **Environnement** : preview et production.
> **Correctif** : déclarer `CORS_ORIGINS` dans `render.yaml` et dans le tableau
> des variables par environnement de `docs/ci-cd.md`. S'articule avec #259.

**Constat de contexte, sans correctif proposé** : les deux backends Render sont
joignables **directement** depuis Internet (`ipAllowList: 0.0.0.0/0`), pas
seulement à travers le proxy Vercel. C'est ce qui donne leur portée réelle à
A05-1, A05-2 et A04-2 : toute protection posée côté front est contournable en
appelant Render en direct. Le restreindre n'est pas possible sur l'offre
gratuite ; c'est une donnée du modèle de menace, pas un défaut à corriger.

**Verbosité des erreurs : correcte.** `register_exception_handlers`
(`core/exceptions.py:86`) ne rend que `{"detail": <message métier français>}`.
Mesuré : une ressource inexistante rend « Résultat introuvable », un type
invalide rend le 422 standard de Pydantic (nom du champ et type attendu, pas de
trace), et aucune trace d'exécution ne franchit la frontière HTTP. Le 403 ne
nomme ni le pouvoir exigé ni ceux portés (`api/deps.py:26`).

## A06 — Vulnerable Components : **à corriger** (2 constats)

**Frontend : sain.** `npm audit` — **0 vulnérabilité**, dépendances de
développement comprises (842 paquets). Les 9 alertes `high` `brace-expansion`
relevées dans une session antérieure ont disparu du parc.

**Alertes Dependabot : activées et vides.** `GET /repos/…/vulnerability-alerts`
→ 204 (activées), `automated-security-fixes` → `{"enabled": true,
"paused": false}`, `dependabot/alerts` → **aucune alerte ouverte**.

> **Constat A06-1 — aucun contrôle de vulnérabilité sur les dépendances
> Python.** *Moyen.*
>
> `ci.yml` lance `ruff` et `pytest`, rien d'autre. `uv sync --locked` garantit
> la **reproductibilité** du parc, jamais son innocuité. Aucun `pip-audit`,
> aucun `uv pip audit`, aucun équivalent. Les alertes Dependabot couvrent bien
> `uv.lock`, mais elles sont un signal asynchrone : rien ne fait rougir une PR
> qui introduit une version vulnérable. Le parc concerné porte toute la surface
> exposée — `fastapi`, `uvicorn`, `httpx`, `authlib`, `lxml`, `openpyxl`,
> `psycopg2-binary`.
> **Environnement** : CI, donc les trois.
> **Correctif** : un step `pip-audit` dans le job `backend` de `ci.yml`, en
> miroir de ce que `npm audit` fait déjà côté front.

> **Constat A06-2 — pas de `dependabot.yml`.** *Faible.*
>
> `.github/` ne contient que `codeql/` et `workflows/`. Les **alertes** de
> sécurité fonctionnent (ci-dessus), mais les **mises à jour de version** ne
> sont pas configurées : rien ne propose de PR de montée de version, ni pour
> `uv.lock`, ni pour `package-lock.json`, ni pour les actions GitHub — ces
> dernières rejoignant le constat A08-2.
> **Correctif** : un `.github/dependabot.yml` à trois écosystèmes (`pip` ou
> `uv` sur `backend/`, `npm` sur `frontend/`, `github-actions` sur `/`), cadence
> mensuelle pour ne pas noyer la revue.

## A07 — Identification & Authentication Failures : **couvert** (1 constat faible)

**Cycle de vie.** TTL de 7 jours **sans prolongation glissante**
(`config.py:96`) ; purge des sessions expirées de l'utilisateur à chaque
ouverture (`session.py:42`) ; résolution soumise à un invariant à trois
conditions dont la troisième — compte actif — est une **jointure** et non un
cache, ce qui rend une désactivation immédiate sans avoir à parcourir les
sessions.

**Révocation (#169) : livrée par deux chemins délibérément redondants.**
`POST /admin/sessions/revoke` (pouvoir `sessions:revoke`) et
`python -m app.cli revoke-sessions`, chacun à deux portées — tout, ou une
adresse. Le second reste praticable le jour où c'est du back-office qu'on se
méfie.

**Fixation de session : fermée par construction.** Le cookie d'état est effacé
sur **tous** les chemins de sortie du callback, succès compris (usage unique
sans table ni verrou) ; le préfixe `__Host-` interdit l'attribut `Domain`, donc
l'écrasement depuis un sous-domaine ; un jeton neuf est émis à chaque connexion.

**Confusion de fournisseur : fermée.** Le `provider` fait partie de la charge
signée, et un état émis pour A est refusé au retour de B (`flow.py:68`). Toutes
les formes de refus rendent le même code `state_mismatch`.

**Redirection ouverte : fermée par construction.** `/auth/{provider}/authorize`
n'accepte **aucun** paramètre, et la destination de retour vient de la
configuration (`auth_redirect_base_url`), jamais de l'entrée. Les codes
d'erreur qui atterrissent dans l'URL de `/login` appartiennent à un ensemble
fermé, avec repli explicite (`auth.py:227`).

**Pas de mot de passe, donc pas de bourrage d'identifiants** : l'authentification
est intégralement déléguée, aucune empreinte de mot de passe n'existe en base.

> **Constat A07-1 — aucune limitation de débit sur l'ouverture de parcours.**
> *Faible.*
>
> `GET /auth/{provider}/authorize` est publique et sans plafond. Le coût unitaire
> est réel mais faible (signature JWS, aucune écriture en base — l'état vit dans
> un cookie, ce qui est un bon choix de conception), et le callback valide
> localement avant tout réseau. Le levier de charge existe donc, mais il est
> mince.
> **Environnement** : preview et production.
> **Correctif** : à traiter avec A04-2, même mécanisme, même correction de la
> chaîne d'IP en préalable. Ne mérite pas sa propre issue.

## A08 — Software & Data Integrity Failures : **à corriger** (3 constats)

> **Constat A08-1 — l'analyse de sécurité CodeQL ne tourne pas.** *Moyen.*
> **Cette catégorie était réputée couverte par l'issue #321 ; elle ne l'est
> pas.**
>
> Mesuré : `GET /repos/…/code-scanning/default-setup` répond
> `{"state": "not-configured"}`, et `code-scanning/alerts` comme
> `code-scanning/analyses` répondent `404 no analysis found`. Ce qui s'exécute
> est le workflow géré `dynamic/github-code-scanning/codeql` avec
> `analysis-kinds: code-quality` — c'est-à-dire les suites
> `python-code-quality.qls` / `javascript-code-quality.qls`, qui cherchent des
> défauts de qualité, **pas** des vulnérabilités. Le sondage
> `docs/superpowers/specs/2026-08-04-code-quality-codeql-sondage.md` §7
> l'établissait déjà (« l'analyse qui tourne n'est pas la default setup de code
> scanning ») ; l'issue #321 a repris l'affirmation inverse en prémisse.
> **Conséquence** : le dépôt n'a **aucun SAST**. Les 12 catégories de ce rapport
> ont donc été instruites à la main, sans filet automatique derrière.
> **Environnement** : dépôt, donc les trois.
> **Correctif** : activer la default setup de **code scanning** (`security`) en
> plus de l'analyse `code-quality` déjà en place. Les deux coexistent ; le
> `paths-ignore` de `.github/codeql/codeql-config.yml` s'appliquera aux deux, ce
> qui est à vérifier une fois activé — filtrer `backend/tests/fixtures` est
> souhaitable des deux côtés, `backend/alembic/versions` a été retenu pour des
> raisons de qualité qui ne valent pas nécessairement en sécurité.

> **Constat A08-2 — actions GitHub non épinglées par empreinte.** *Faible.*
>
> `actions/checkout@v4`, `actions/setup-node@v4`, `astral-sh/setup-uv@v8.3.2`,
> `azure/login@v2`, `actions/upload-artifact@v4`, `actions/deploy-pages@v4`,
> `actions/jekyll-build-pages@v1` : toutes référencées par un tag **mutable**.
> Un tag repointé chez l'éditeur s'exécuterait dans `batch.yml`, qui détient la
> `DATABASE_URL` de production et un jeton fédéré Azure, et dans `deploy.yml`,
> qui porte `RENDER_API_KEY` et `VERCEL_TOKEN`. `npm i -g vercel@54` est dans le
> même cas, borné au major.
> **Correctif** : épingler par SHA au moins les deux workflows privilégiés
> (`batch.yml`, `deploy.yml`), avec le commentaire de version en regard.
> Dependabot (A06-2) maintient ces empreintes s'il est configuré pour
> `github-actions`.

> **Constat A08-3 — `ci.yml` et `deploy.yml` ne déclarent pas leurs
> permissions.** *Faible.*
>
> `batch.yml` (`id-token: write`, `contents: read`) et `pages.yml` déclarent les
> leurs ; `ci.yml` et `deploy.yml` n'en déclarent aucune et héritent donc du
> défaut du dépôt pour `GITHUB_TOKEN`. Or `ci.yml` s'exécute sur
> `pull_request` — le déclencheur qui exécute du code de contributeur.
> **Atténuation forte, et c'est pourquoi le constat reste faible** : le
> déclencheur est bien `pull_request` et non `pull_request_target`, donc le
> jeton d'une PR de fork est en lecture seule quoi qu'il arrive, et aucun secret
> de dépôt ne lui est exposé.
> **Correctif** : `permissions: contents: read` en tête des deux fichiers.

**Ce que la chaîne fait bien.** Aucun déploiement sans CI verte (`needs: ci`,
doublé d'`Auto-Deploy = No` côté Render) ; authentification Azure par **OIDC**,
sans secret à durée illimitée ; ouverture *just-in-time* du pare-feu Azure,
règle nommée d'après le `run_id` et retirée en `if: always()` ; `uv sync
--locked` et `npm ci` ; masquage explicite des sous-chaînes de secret
(`::add-mask::`) parce que GitHub ne masque que la valeur exacte ; verrou de
concurrence par base pour les batches.

## A09 — Logging & Monitoring Failures : **couvert**

**Un accès refusé laisse une trace, et la bonne.** `api/deps.py:116` journalise
en WARNING l'identifiant de l'utilisateur, le pouvoir manquant, la méthode et le
chemin — pendant que la réponse rendue au client, elle, ne nomme rien. C'est la
répartition juste : le diagnostic côté serveur, le silence côté client.

**Les gestes d'administration sont journalisés deux fois.** `services/admin_actions.py`
émet un `logger.info` par geste **et** écrit dans `admin_action_log` par le
repository dédié, dans la **même transaction** que l'effet — un refus lève avant,
et rien n'est écrit, ni la donnée ni sa trace. Le journal n'enregistre que ce
qui a effectivement changé.

**Aucun secret ne fuit, et un test le verrouille.**
`backend/tests/test_auth/test_no_secret_logged.py` interdit la présence du
`client_secret`, de la clé de signature, du code de retour OAuth et du jeton de
session dans les journaux applicatifs. `core/sql_observability.py` journalise le
SQL **paramétré**, jamais ses valeurs liées — qui portent des noms d'athlètes et
des libellés de club —, avec son propre test de non-régression.
`FeedbackRead` ne porte jamais `ip_address`, présent en base pour le seul
comptage.

**Réserve, sans constat.** Il n'existe pas de journal des **connexions
réussies** côté serveur : `capture_event("user_logged_in", …)` part vers
PostHog, qui est un outil produit et non un journal d'audit. Le manque est réel
mais théorique tant que le nombre de comptes se compte sur les doigts d'une
main ; il deviendra un vrai sujet le jour où l'on cherchera « qui s'est connecté
quand ». À rouvrir si l'usage du back-office s'élargit.

## A10 — SSRF : **couvert** (1 constat faible)

**La garde tient, et elle a été re-vérifiée sur pièces** — l'audit ne la
réécrit pas.

- **Voie de sortie unique.** `core/http.client()` est la seule fabrique de
  client HTTP de `app/` ; un méta-test AST (`tests/test_core_http.py`) refuse
  tout usage nu d'`httpx` ailleurs, y compris les liaisons
  `authlib.integrations.httpx_client` et `httpx.HTTPTransport` — le point exact
  où circulent un `client_secret` et un code d'autorisation.
- **Contrôle sur chaque saut.** `_GuardTransport.handle_request` valide la
  requête initiale **et** chaque redirection, `request.url` étant déjà résolue
  par httpx (un `event_hook` ne verrait ni la requête initiale ni le `Location`
  résolu).
- **Prédicat juste.** `not ip.is_global` plutôt qu'une disjonction de six
  tests : ferme en plus la plage CGNAT et les plages de documentation. Les
  adresses IPv4-mapped sont ramenées à leur forme IPv4. Une adresse illisible
  est traitée comme interne.
- **Schémas bornés** à `http`/`https`, contrôle nécessaire puisqu'un `transport=`
  explicite désactive le filtrage de schéma d'httpx.
- **Le nom vérifié est `raw_host`**, celui du fil, jamais sa forme Unicode —
  IDNA 2003 contre IDNA 2008 désignant deux domaines enregistrables distincts.
- **Porte d'entrée** : `ScrapeRequest.url` est un `HttpUrl`, ce qui écarte
  `file://`, `gopher://` et `javascript:` dès la validation.

> **Constat A10-1 — fenêtre de re-résolution DNS (rebinding).** *Faible.*
>
> `_check_target` résout le nom, puis httpcore le résout **à nouveau** pour
> ouvrir la connexion : ce sont deux résolutions distinctes. Un nom servi par un
> DNS à TTL 0 rendant d'abord une adresse publique puis une adresse interne
> franchirait la garde. Le mémo `_resolved` ne l'atténue pas — il évite la
> répétition, il ne verrouille pas la destination.
> **Environnement** : preview et production.
> **Correctif** : le fermer proprement suppose de résoudre soi-même et de
> connecter à l'adresse validée (transport personnalisé). Le rapport
> coût/bénéfice est défavorable et il est **assumé** : consigné ici pour que ce
> soit une décision et non un oubli.

## Secrets : **couvert**

- **Aucun secret dans l'arbre** : recherche des motifs usuels (jetons GitHub,
  clés AWS, blocs de clé privée) sur tout le dépôt, hors `node_modules` — aucun
  résultat. Les seuls fichiers d'environnement suivis sont les trois `.example`.
- **Aucun secret dans l'historique** : aucun `.env`, `.pem` ou `.key` n'a jamais
  été ajouté (`git log --diff-filter=A` sur l'ensemble des refs).
- **Secret scanning GitHub** : une seule alerte depuis l'origine du dépôt,
  **résolue en faux positif** — une clé d'API Google présente dans une fixture
  HTML de scraper, c'est-à-dire dans la capture fidèle d'une page publiée par un
  chronométreur tiers. Le classement est correct.
- **Hygiène de la chaîne** : `render.yaml` s'interdit tout identifiant de
  service et toute URL d'instance (dépôt public) ; `deploy.yml` masque
  explicitement les sous-chaînes extraites d'un secret ; la clé de signature est
  en `generateValue` plutôt qu'en saisie manuelle, « personne n'a besoin de la
  connaître ».
- **Point de ménage, pas de sécurité** : `AUTH_ALLOWED_EMAILS` est encore
  déclarée côté Render alors que l'application ne la lit plus depuis #170. Elle
  ne donne aucun accès (le fail-closed vit désormais dans
  `services/auth/provisioning`). À retirer avec #259.

## Données personnelles : **à instruire** (#313)

**Ce que l'API publique expose sans session**, mesuré sur la production :
`GET /athletes/{id}` rend nom, prénom, genre, club et l'intégralité des
participations (dates, temps, rangs, URL de la source). C'est la raison d'être
du produit, et ces données sont déjà publiées par les chronométreurs.

**Ce qu'elle ne rend pas** : la date de naissance, fermée derrière
`athletes:read` et décrite dans le catalogue comme « la seule donnée personnelle
que le site garde fermée » (`core/permissions.py:167`) — vérifié, `AthleteBrief`
ne porte pas le champ. L'adresse IP d'un signalement ne franchit jamais la
frontière HTTP.

> **Constat DP-1 — l'API n'a pas de `robots.txt`.** *Faible.*
>
> Le front porte `<meta name="robots" content="noindex">` et Vercel renvoie
> `x-robots-tag: noindex` : le site n'est pas indexable. Le backend Render,
> lui, rend **404 sur `/robots.txt`** et sert du JSON nominatif à qui l'appelle
> en direct. L'intention de non-indexation posée sur le front est donc
> contournée par une porte restée ouverte à côté.
> **Environnement** : preview et production.
> **Correctif** : un `robots.txt` (ou un en-tête `X-Robots-Tag: noindex`) sur
> l'API. À trancher **dans** #313, qui porte le cadre légal : c'est là que se
> décide ce qui doit être indexable, pas ici.

---

## Traces laissées par l'audit

**Sur preview** : 13 signalements de test créés par `POST /feedback`
(identifiants 1 à 13), tous titrés `[audit #321] … — a supprimer`, portant un
corps qui les désigne comme tels. Ils sont la pièce à conviction du constat
A04-1 ; **à supprimer une fois l'issue fille ouverte**, depuis
`/admin/retours-utilisateurs`.

**Sur la production** : rien. Aucune écriture, aucune charge, aucune donnée de
test — uniquement des `GET` de lecture et l'inspection d'en-têtes.

## Écarts documentaires relevés en chemin

Sans rapport avec la sécurité, mais constatés en vérifiant la configuration ;
notés pour qui reprendra `docs/ci-cd.md`.

- Le **projet Vercel `data-triathlon-preview`** décrit par `docs/ci-cd.md` et
  par `deploy.yml` **n'existe pas** dans l'équipe Vercel : un seul projet y est
  listé, `data-triathlon`. Le job `deploy-preview` déploie donc vers ce que
  désigne le `VERCEL_PROJECT_ID` de l'environment GitHub `preview`, qu'il faut
  vérifier.
- Le service Render de production se nomme `triathlon-backend-production`, là où
  `render.yaml` écrit `data-triathlon` — or ce nom est précisément ce par quoi
  un Blueprint apparie un service existant, comme le fichier le documente
  lui-même.

## Issues filles proposées

Une par constat retenu, étiquetée `security`, dans cet ordre de priorité.

| # | Constat | Sévérité | Titre proposé |
| --- | --- | --- | --- |
| 1 | A04-1 | moyen | `fix(security): trust the proxy chain so feedback rate limiting cannot be bypassed` |
| 2 | A08-1 | moyen | `chore(security): enable CodeQL code scanning alongside code quality` |
| 3 | A04-2 | moyen | `feat(security): rate-limit the public scraping endpoints` |
| 4 | A05-2 | moyen | `feat(security): add security headers to the frontend and the API` |
| 5 | A06-1 | moyen | `chore(ci): audit Python dependencies for known vulnerabilities` |
| 6 | A04-3 | moyen | `fix(security): bound the two public write endpoints` |
| 7 | A05-1 | faible | `chore(security): close /docs and /openapi.json in production` |
| 8 | A08-2 | faible | `chore(ci): pin GitHub Actions by commit SHA in privileged workflows` |
| 9 | A06-2 | faible | `chore(ci): configure Dependabot version updates` |
| 10 | A05-3 + A02-1 | faible | `chore(security): document CORS_ORIGINS and add HSTS to the API` |
| 11 | A08-3 | faible | `chore(ci): declare least-privilege permissions in ci.yml and deploy.yml` |
| 12 | DP-1 | faible | à traiter **dans** #313, pas d'issue dédiée |

**A07-1** rejoint l'issue n°3 (même mécanisme, même préalable) et **A10-1** ne
donne pas lieu à issue : c'est une limite assumée, consignée pour qu'elle reste
une décision.

## Ce que cet audit ne couvre pas

Hors périmètre par l'issue : pentest externe mandaté, tests de charge ou de déni
de service, audit RGPD complet (#313). Non couvert faute de moyen de mesure :
la configuration interne de Supabase et d'Azure PostgreSQL (chiffrement au
repos, rotation des identifiants de base), et le contenu réel des variables
d'environnement des dashboards Render et Vercel — seul leur **effet observable**
a été mesuré.
