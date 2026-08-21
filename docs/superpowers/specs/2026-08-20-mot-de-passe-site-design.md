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
sauf **six** exceptions nommées (cinq à la livraison, `feedback` ajouté en
revue de #513 — voir § Suites de la revue de #513) :

- `health` (`/health`, `/version`) — needs d'infra (keep-warm Render) et
  donnée non sensible, déjà documentée comme volontairement publique ;
- le nouveau routeur `site_access` lui-même (`POST/DELETE /site-access/session`,
  et `GET /site-access/session` pour la vérification depuis le frontend) —
  c'est lui qui pose le cookie, il ne peut pas exiger sa propre présence ;
- `benevoles` (#271) — la page bénévoles vise explicitement une population
  qui peut ne pas être adhérente (§ Ce que ça change dans les invariantes
  existantes évoque déjà « potentiellement non-adhérents »). La gater
  derrière le mot de passe site fermerait la page de vérification à tout
  bénévole extérieur au club, ce que #271 a justement ouvert.
  `require_benevole_access` reste sa **seule** garde, inchangée ;
- **`auth`** (SSO) et **`admin_site_access`** — **correction apportée en
  cours d'implémentation, après un blocage de déploiement détecté en revue
  de la garde transverse (Task 8)** : gater `auth` derrière le mot de passe
  site interdisait toute connexion SSO sans lui, et gater
  `admin_site_access` exigeait le cookie site pour le poser — sur une
  installation neuve, sans configuration, **aucune** des deux routes n'est
  jamais atteignable, y compris par un administrateur. Un déploiement frais
  restait fermé pour toujours, sans échappatoire en base ni en CLI. Les deux
  routeurs restent protégés par ce qui les protégeait déjà avant #509 :
  `admin_site_access` par `require_permission(P.SITE_ACCESS_MANAGE)` (RBAC),
  `auth` par ses propres contrôles (liste d'autorisation, #170). C'est
  exactement le patron déjà en place pour `admin_benevole_access`, qui n'a
  jamais été doublement gardé par `require_benevole_access` — la garde
  transverse ne fait que le reproduire pour la paire équivalente ici.
  Le bootstrap du tout premier administrateur reste le même qu'aujourd'hui
  (`app/cli/AGENTS.md`, `grant-role`), inchangé par #509.

Tout le reste **hors ces six** : un visiteur externe ne doit atteindre
aucune page publique, ni aucune écriture publique existante
(`POST /participations`, `POST /admin/pending-providers`) sans le mot de passe
site d'abord — ces routes restent ouvertes **côté
RBAC** (FR-018/FR-022 de #115 ne changent pas), mais exigent désormais le
cookie site comme tout le reste. Une fois la session site ouverte, la garde
RBAC de #115 s'applique normalement par-dessus.

## Garde frontend — layout, pas middleware

`frontend/app/admin/layout.tsx` documente déjà pourquoi ce dépôt évite
`middleware.ts` pour ce type de garde : un middleware ne constate que la
*présence* du cookie, jamais sa validité, et un `matcher` mal borné
intercepte `/api/*` et casse la réécriture vers le backend. Cette feature
reprend donc le même patron de garde-par-layout — appel serveur à
`GET /api/v1/site-access/session`, puis, si 401, le formulaire de mot de passe
(redirection vers `/acces` à la livraison ; **rendu sur place depuis la revue
de #513**, voir § Suites de la revue de #513) — mais **pas sur
`app/layout.tsx`** : ce fichier définit
`<html>`/`<body>` pour **toute** l'application, `/acces` et `/benevoles`
compris, et une redirection posée là boucle sur elle-même (`/acces` rend le
layout racine, qui revérifie la session, qui redirige vers `/acces`…) et
fermerait au passage `/benevoles`, dont l'exemption backend ci-dessus n'aurait
plus d'effet si le frontend redirige avant même que la page ne s'affiche.

La garde se pose donc sur un groupe de routes, `app/(public_restricted)/layout.tsx`
(parenthèses : invisible dans l'URL), qui accueille toutes les routes
existantes sauf trois, par un déplacement mécanique de dossiers
(`git mv app/dashboard "app/(public_restricted)/dashboard"`, etc.) : `dashboard`,
`resultats`, `athletes`, `courses`, `club`, `carte`, `ajouter` — plus `login` à
la livraison, ressorti en revue de #513 (§ Suites de la revue de #513).
`app/layout.tsx` (html/body/nav) ne change pas de rôle, il englobe toujours
tout. `/acces`, `/benevoles` **et `/admin`** restent des routes **sœurs**,
hors du groupe, donc jamais soumises à cette garde — `/benevoles` garde sa
propre garde côté client (`AccessGate`, déjà en place), `/acces` est la page
que la garde cible.

**`admin` en est sorti après coup — correction apportée en revue finale**,
sur le même défaut que celui déjà nommé côté backend (§ Ce que ça change
dans les invariantes existantes) : y placer `admin` fermait le seul chemin
**navigateur** pour poser le tout premier mot de passe. Sur un déploiement
neuf, `site_access_config` est vide ; `/admin/acces`, gardé par ce layout,
redirigeait vers `/acces`, qui ne peut accepter aucun mot de passe puisque
aucun n'existe — sans issue en navigateur, y compris pour un administrateur.
Le correctif backend de la même nature (exempter `auth` et
`admin_site_access` de `require_site_access`, ci-dessus) n'avait corrigé que
l'API ; ce même geste manquait côté frontend. `admin` reste protégé par ce
qui le protégeait déjà — `app/admin/layout.tsx` (SSO/RBAC), inchangé — donc
rien n'est exposé de plus qu'avant #509 : seul l'écran de connexion redevient
visible sans le mot de passe site, symétrique de l'exemption `auth` déjà
acceptée côté API.

**Conséquence assumée** : les six pages publiques aujourd'hui prérendues
statiquement (`frontend/AGENTS.md`, `serverFetch` inchangé) basculent en
rendu dynamique — impossible de garder un prérendu statique tout en
vérifiant un cookie à chaque requête. C'est l'effet recherché, au même titre
que pour `/admin` (#115) : protéger *tout* le site implique que *tout* le
site devienne dynamique.

**Ce raisonnement s'est arrêté une marche trop tôt — corrigé par #526.** Il a
constaté que `serverFetch` n'avait plus de prérendu à protéger, et en a conclu
qu'il pouvait rester *inchangé*. Or il devait devenir **obligatoirement**
cookie-relayant : les six pages qu'il sert lisent `athletes`, `courses`,
`participations` et `stats`, tous gardés par `require_site_access`, qui est
fail-closed. Un cookie site valide passait donc la garde du layout, puis chaque
enfant se prenait un 401 en pleine passe de rendu serveur — React #441 et
`app/error.tsx` sur tout le site dès qu'un mot de passe était configuré,
constaté sur la preview après la fusion de #513.

Ni la suite backend ni la suite frontend ne pouvaient l'attraper : la fixture
`client` neutralise `require_site_access` par `dependency_overrides` (§ Tests,
décision assumée), et les pages sont testées avec `apiServer` mocké. Seule la
vérification manuelle de bout en bout que #513 avait explicitement laissée
en suspens l'aurait montrée — elle demandait un mot de passe **configuré**, et
c'est exactement l'état qu'aucun test n'exerce. À retenir pour toute garde
transverse fail-closed : la neutraliser globalement en test rend la
vérification manuelle non-optionnelle, pas simplement recommandée.

## Administration

Écran existant `admin/acces`, qui héberge déjà `BenevoleAccessConfig` : un
composant jumeau `SiteAccessConfig` y prend place, même contrat d'API
(`GET/PUT /admin/site-access`, `POST /admin/site-access/generate`), gardé par
un nouveau pouvoir RBAC `site_access:manage` (catalogue `core/permissions.py`,
`FEATURE_ROLES` — même regroupement que `benevole_access:manage`).

## Hors périmètre de ce livrable

- Renouvellement glissant de la session (voir § Expiration) ;
- Compte/identité pour les écritures anonymes (voir § Modèle de données).

## Plafond de débit — revenu sur la décision initiale (revue finale)

`POST /site-access/session` est désormais **la seule porte publique non
authentifiée du site** — à la différence de `POST /benevoles/session`, sur
lequel le déferrement initial se calquait, et qui ne sert qu'une poignée de
bénévoles. Le calcul `hashlib.scrypt` qu'elle déclenche à chaque tentative
(~16 Mo, 50-100 ms CPU) devient donc un levier de déni de service **et**
de force brute sur l'offre gratuite Render, exactement le risque que #395
plafonne ailleurs. `public_write_rate_limit` (`api/deps.py`) est réutilisé
tel quel, et `SiteAccessLogin.password` gagne un `max_length` — les deux
changements coûtent une ligne chacun et ne demandent aucune nouvelle
infrastructure. *La réutilisation du seau `public_write` a été défaite en revue
de #513 (§ Suites de la revue de #513) ; le plafond lui-même, lui, reste.*

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

## Suites de la revue de #513

Six correctifs et trois gestes de forme, tous vérifiés contre le code avant
d'être écrits. Ils ne
rouvrent pas le design : ils ferment ce que la garde transverse avait cassé sans
que la suite ne le voie. Les deux derniers (8 et 9) débordent sur le jumeau #271,
à dessein — un renommage ou une suppression qui ne vaudrait que d'un côté
défairait le jumelage.

1. **`login` ressorti du groupe gardé** (`git mv "app/(public_restricted)/login" app/login`).
   Le § Garde frontend avait sorti `admin` sans sortir `login`, or la garde
   d'`admin` renvoie un anonyme vers `/login` : sur un déploiement neuf, le
   chemin devenait `/admin` → `/login` → `/acces` → impasse, aucun mot de passe
   n'existant encore à saisir. C'était le **même** défaut que celui déjà corrigé
   deux fois (backend en Task 8, `admin` en revue finale), à un dossier près —
   d'où un test de **structure de dossiers**, `app/routes-garde-site.test.ts` :
   l'erreur est un rangement, invisible à la lecture de n'importe quel fichier.
2. **`GET /benevoles/athletes`**, jumeau gardé par `require_benevole_access`. La
   réattribution de participation (`ParticipationPanel`) appelait
   `GET /athletes`, passée sous la garde site : un bénévole n'a que le mot de
   passe bénévoles, sa recherche rendait 401 en silence. Exempter `athletes` de
   la garde site aurait rouvert toute la recherche d'athlètes à l'anonyme — la
   route jumelle la garde derrière ce que le bénévole possède déjà. Le front
   distingue désormais « aucun résultat » d'« échec de recherche ».
3. **`MAX_PASSWORD_LENGTH` partagé** entre `schemas/site_access.py` (borne de la
   connexion, ajoutée en revue finale) et `schemas/site_access_config.py` (borne
   de l'administration). Elles divergeaient : l'administration acceptait un mot
   de passe plus long que ce que la connexion pouvait soumettre, donc un accès
   configuré et inutilisable.
4. **`feedback` exempté de la garde site.** `FeedbackButton` vit dans le layout
   racine du front : il se rend donc aussi sur `/acces` et `/benevoles`, où
   aucun cookie de site n'existe. Son unique route reste bornée par honeypot et
   par un plafond compté en base ; `admin_feedback`, lui, reste gardé.
5. **Seau de débit dédié `site_access`, 60/h.** Partager `public_write` couplait
   la porte d'entrée du site à la saisie manuelle de résultats — saisir sa saison
   empêchait d'ouvrir une session, et un club derrière une seule IP NAT/CGNAT
   épuisait les 30 tentatives collectivement. Plus large pour la raison inverse
   des autres seaux : premier geste de chaque visiteur, IP partagée, saisie au
   clavier faillible. Ce qu'il ferme reste le déni de service par `scrypt`, pas
   la force brute sur un secret de 144 bits.
6. **Le formulaire est rendu sur place, plus par redirection vers `/acces`.**
   `redirect("/acces")` perdait la destination : un lien partagé vers
   `/courses/42` finissait sur le tableau de bord. Un layout serveur ne reçoit en
   Next 16 ni le chemin ni les `searchParams`, donc « transporter la
   destination » n'était pas implémentable là où la garde est posée —
   `middleware.ts` est exclu par design et `authInterrupts`/`unauthorized()`
   reste expérimental en 16.3.1. Rendre le formulaire à la place des enfants
   supprime le problème au lieu de le contourner : l'URL ne bouge pas, le
   `router.refresh()` qui suit la connexion rejoue le layout cookie en main, et
   il n'y a aucun paramètre `next` à valider contre la redirection ouverte.
   `/acces` reste une route à part entière (navigation directe, retour de
   déconnexion) et rend le même composant avec `apres="accueil"`.

7. **Le groupe de routes est renommé `(public_restricted)`** — nom demandé en
   revue. `(protege)` décrivait le mécanisme ; celui-ci décrit l'état : ces pages
   restent **publiques côté RBAC**, seule leur porte d'entrée est restreinte. En
   anglais, à la différence des routes sœurs (`acces`, `benevoles`…) : un nom de
   groupe entre parenthèses n'apparaît dans aucune URL, il ne se rend jamais à un
   utilisateur, donc il tombe du côté technique du Principe I. `git mv` du dossier
   seul — aucun import n'y référait, les chemins ne vivaient que dans des
   commentaires et dans `routes-garde-site.test.ts`.
8. **Les délégations d'une ligne vers `shared_password` sont supprimées**, des
   **deux** côtés (#271 et #509). La mutualisation demandée en revue était déjà
   faite (commit `4e2f8ef`, `services/shared_password.py` porte le scrypt et le
   HMAC) ; ce qui restait dans `site_access.py` et `benevole_access.py` était
   quatre fonctions qui ne faisaient que renvoyer au socle. Les appelants
   (routeurs, garde, tests) l'appellent directement. Ce qui reste dans les deux
   modules de domaine est ce qui leur est propre : le nom du cookie, le TTL, la
   génération du secret, `replace_password`.

9. **`SINGLETON_ID` devient `CONFIG_ROW_ID`**, des deux côtés du jumelage
   (`site_access_config_repository` et `benevole_config_repository`, #271). La
   revue n'avait pas compris à quoi servait la constante, et le nom en était la
   cause : « singleton » décrit la forme de la table, pas ce que la constante
   porte — l'`id` de la ligne en base. Ce qu'elle **fait** reste écrit au-dessus
   d'elle : figer la clé primaire est ce qui rend le singleton vrai, deux
   remplacements concurrents au premier réglage entrant en collision de PK
   (`IntegrityError` rattrapée par le savepoint) au lieu de créer une seconde
   configuration que personne ne lirait. Renommage seul, aucun changement de
   comportement : la valeur reste `1`, les lignes déjà en base ne bougent pas,
   donc pas de migration.
