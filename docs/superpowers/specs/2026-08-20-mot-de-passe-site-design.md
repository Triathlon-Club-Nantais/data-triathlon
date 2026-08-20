# Mot de passe d'accès au site (#509) — design

Ferme l'accès public au site entier (front + API) derrière un mot de passe
partagé, distribué aux adhérents du club. Reprend le patron déjà livré par
#271 (`services/benevole_access.py`) — mot de passe haché+salé, cookie de
session signé HMAC, aucun état serveur à la vérification — étendu à tout le
site plutôt qu'à la seule page bénévoles, avec un secret distinct.

## Ce que ça change dans les invariantes existantes

Deux points documentés du dépôt sont **délibérément inversés** par cette
feature, pas contournés en silence :

- `backend/app/api/v1/router.py` porte aujourd'hui : « Aucun `dependencies=`
  ici ni sur aucun router (FR-018) : la protection se pose route par route. »
  Le but explicite de #509 — fermer l'accès public dans son ensemble — est
  exactement ce que cette règle existait pour éviter *par accident*. Cette
  feature pose donc une garde transverse, nommément, en remplacement de ce
  commentaire.
- `backend/app/services/auth/AGENTS.md` : « Aucune route existante n'est
  protégée — c'est le périmètre de #115. » Reste vrai pour le RBAC (#115) :
  cette feature ajoute une **deuxième** garde, orthogonale, en amont. Une
  session RBAC ne dispense pas du mot de passe site, et réciproquement.

Le mot de passe bénévoles (#271) et le mot de passe site sont deux secrets
indépendants, sur deux tables, deux cookies, deux écrans d'administration.
Une session bénévoles ouverte n'ouvre pas le site, et inversement — ce sont
deux populations différentes (adhérents vs bénévoles qui valident des
résultats en marge d'une épreuve, potentiellement non-adhérents).

## Modèle de données

Nouvelle table `site_access_config`, schéma identique à
`benevole_access_config` (`password_hash`, `password_salt`, `session_secret`,
`updated_at`, `updated_by_user_id`) — une seule ligne à tout instant, absence
de ligne = accès non configuré (fail-closed, même contrat que #271). Table
distincte plutôt que colonnes supplémentaires sur `benevole_access_config` :
les deux secrets tournent indépendamment, et un `UPDATE` de l'un ne doit
jamais pouvoir toucher l'autre par erreur d'un futur appel groupé.

**Pas de compte système « anonyme » attaché à un rôle.** Contrairement au
compte système bénévoles (cible de `AdminActionLog.user_id` pour des actions
d'écriture attribuées), le mot de passe site ne garde que de la *lecture* :
les écritures publiques existantes (`POST /feedback`,
`POST /admin/pending-providers`) restent anonymes, comme aujourd'hui. Rien
dans ce périmètre n'a besoin d'une identité à laquelle rattacher un pouvoir
RBAC. Si un besoin concret apparaît plus tard, il se traite alors — l'ouvrir
par anticipation ici serait de la configuration spéculative.

## Mécanisme partagé (factorisation)

La signature/vérification HMAC du cookie (`sign_session`/`verify_session` de
`services/benevole_access.py`) migre vers un module neutre,
`services/signed_cookie.py`, sans connaissance du domaine (mot de passe,
bénévoles ou site) — deux appelants distincts plutôt qu'une deuxième copie du
même HMAC. Le hachage de mot de passe (`hash_password`/`verify_password`,
`hashlib.scrypt`) migre au même endroit pour la même raison. `benevole_access.py`
et le nouveau `services/site_access.py` deviennent tous deux de fines couches
métier au-dessus de ce socle commun — noms de cookie, adresses système,
politique d'expiration restant propres à chacun.

## Expiration — différence assumée avec #271

Le cookie bénévoles est un cookie de session navigateur, sans `max_age`
(pas de durée exigée par cette feature-là). #509 demande explicitement une
persistance **avec** expiration (« toute les semaine, à challenger ») : le
cookie site porte donc un `max_age`, **et** l'horodatage déjà présent dans la
valeur signée (`{horodatage}.{signature}`) est vérifié côté serveur contre un
TTL (`SITE_ACCESS_SESSION_TTL_DAYS`, défaut 7 — même patron que
`AUTH_SESSION_TTL_DAYS`). Les deux ensemble : un cookie recopié ailleurs
n'étend pas sa durée de vie au-delà du TTL serveur. Pas de renouvellement
glissant pour ce premier livrable — un adhérent ressaisit le mot de passe une
fois la fenêtre passée ; si l'usage montre que c'est gênant, un
renouvellement à chaque requête valide se rediscute alors (donnée
d'exploitation, pas une hypothèse de design).

## Garde backend

`app/api/deps.py` gagne `require_site_access`, jumelle de
`require_benevole_access` : lit `site_access_config`, vérifie le cookie
`tcn_site_session` contre `session_secret` **et** le TTL. Fail-closed :
configuration absente ou cookie absent/invalide/expiré → 401 uniforme.

Posée dans `app/api/v1/router.py`, à l'inclusion de chaque sous-router
(`include_router(module.router, dependencies=[Depends(require_site_access)])`),
sauf trois exceptions nommées :

- `health` (`/health`, `/version`) — needs d'infra (keep-warm Render) et
  donnée non sensible, déjà documentée comme volontairement publique ;
- le nouveau routeur `site_access` lui-même (`POST/DELETE /site-access/session`,
  et `GET /site-access/session` pour la vérification depuis le frontend) —
  c'est lui qui pose le cookie, il ne peut pas exiger sa propre présence ;
- `benevoles` (#271) — **correction apportée en cours de planification** : la
  page bénévoles vise explicitement une population qui peut ne pas être
  adhérente (§ Ce que ça change dans les invariantes existantes évoque déjà
  « potentiellement non-adhérents »). La gater derrière le mot de passe site
  fermerait la page de vérification à tout bénévole extérieur au club, ce que
  #271 a justement ouvert. `require_benevole_access` reste sa **seule** garde,
  inchangée.

Tout le reste, **`auth` (SSO) compris** : un visiteur externe ne doit
atteindre ni les pages publiques, ni même l'écran de connexion admin, sans
le mot de passe site d'abord. Une fois la session site ouverte, la garde
RBAC de #115 s'applique normalement par-dessus.

## Garde frontend — layout, pas middleware

`frontend/app/admin/layout.tsx` documente déjà pourquoi ce dépôt évite
`middleware.ts` pour ce type de garde : un middleware ne constate que la
*présence* du cookie, jamais sa validité, et un `matcher` mal borné
intercepte `/api/*` et casse la réécriture vers le backend. Cette feature
reprend donc le même patron de garde-par-layout — appel serveur à
`GET /api/v1/site-access/session`, redirection vers `/acces` (formulaire de
mot de passe) si 401 — mais **pas sur `app/layout.tsx`** : ce fichier définit
`<html>`/`<body>` pour **toute** l'application, `/acces` et `/benevoles`
compris, et une redirection posée là boucle sur elle-même (`/acces` rend le
layout racine, qui revérifie la session, qui redirige vers `/acces`…) et
fermerait au passage `/benevoles`, dont l'exemption backend ci-dessus n'aurait
plus d'effet si le frontend redirige avant même que la page ne s'affiche.

La garde se pose donc sur un groupe de routes, `app/(protege)/layout.tsx`
(parenthèses : invisible dans l'URL), qui accueille toutes les routes
existantes (`dashboard`, `resultats`, `athletes`, `courses`, `club`, `carte`,
`ajouter`, `admin`, `login`) par un déplacement mécanique de dossiers
(`git mv app/dashboard app/\(protege\)/dashboard`, etc.). `app/layout.tsx`
(html/body/nav) ne change pas de rôle, il englobe toujours tout. `/acces` et
`/benevoles` restent des routes **sœurs**, hors du groupe, donc jamais
soumises à cette garde — `/benevoles` garde sa propre garde côté client
(`AccessGate`, déjà en place), `/acces` est la page que la garde cible.

**Conséquence assumée** : les six pages publiques aujourd'hui prérendues
statiquement (`frontend/AGENTS.md`, `serverFetch` inchangé) basculent en
rendu dynamique — impossible de garder un prérendu statique tout en
vérifiant un cookie à chaque requête. C'est l'effet recherché, au même titre
que pour `/admin` (#115) : protéger *tout* le site implique que *tout* le
site devienne dynamique.

## Administration

Écran existant `admin/acces`, qui héberge déjà `BenevoleAccessConfig` : un
composant jumeau `SiteAccessConfig` y prend place, même contrat d'API
(`GET/PUT /admin/site-access`, `POST /admin/site-access/generate`), gardé par
un nouveau pouvoir RBAC `site_access:manage` (catalogue `core/permissions.py`,
`FEATURE_ROLES` — même regroupement que `benevole_access:manage`).

## Hors périmètre de ce livrable

- Renouvellement glissant de la session (voir § Expiration) ;
- Compte/identité pour les écritures anonymes (voir § Modèle de données) ;
- Rate-limiting dédié sur `POST /site-access/session` — à évaluer avec le
  même patron que le plafond par IP de #395 si un abus est constaté ; pas de
  besoin exprimé aujourd'hui.

## Tests

TDD, comme partout. Un point de terrain change la portée de la fixture
partagée : `tests/conftest.py::client` est utilisée par la quasi-totalité de
la suite (~745 tests), et la garde `require_site_access` s'appliquant à
pratiquement tous les routers, un `client` qui ne présente aucun cookie
casserait toute la suite d'un coup — ce n'est pas ce que ce livrable doit
mesurer, et fabriquer une ligne `site_access_config` (donc un `User` FK) dans
**chaque** test risquerait en plus de fausser un test qui compte les lignes
de `users`. La fixture neutralise donc `require_site_access` par
`app.dependency_overrides`, exactement comme elle le fait déjà pour `get_db` :
```python
app.dependency_overrides[require_site_access] = lambda: None
```
Aucune ligne en base, aucun cookie à fabriquer — la quasi-totalité de la
suite continue de tester ce qu'elle testait. Les tests qui veulent
spécifiquement l'anonyme (le nouveau filet ci-dessous) retirent cette
surcharge (`app.dependency_overrides.pop(require_site_access, None)`) pour
éprouver la vraie garde.

Nouveau filet, `test_site_access_gate.py` : dérive l'inventaire des routes
comme `test_public_routes_still_open.py` (jamais à la main), affirme que
toute route hors `health`/`version`/`site-access/session`/`benevoles/*`
répond 401 sans le cookie site, et que les mêmes répondent normalement une
fois le cookie posé. `test_public_routes_still_open.py` et
`test_permissions_catalogue.py` n'ont, eux, pas besoin de changer d'assertion
— `client` portant déjà le cookie site, ils continuent de n'éprouver que
l'axe RBAC qu'ils testaient déjà ; seul
`test_aucune_dependance_globale_sur_les_routers_existants` doit être vérifié
à la main plutôt que supposé : il inspecte `module.router.dependencies`, un
attribut que `include_router(module.router, dependencies=[...])` ne modifie
pas sur l'objet importé — la garde ci-dessus ne le fait donc pas rougir, mais
c'est à confirmer par une exécution, pas par lecture seule.
