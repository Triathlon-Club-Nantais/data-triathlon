# Authentification (#114)
Socle SSO du back-office : ouvrir une session par délégation à GitHub, sans
jamais détenir de mot de passe, **et laisser le site public strictement intact**.
Spec, plan et tâches : `specs/20260801-145428-auth-socle-sso/` ; le sondage
`docs/superpowers/specs/2026-08-01-auth-librairies-sondage.md` **prime** sur eux.

**Trois tables**, aucune existante modifiée. `users` (identité applicative),
`identities` (un moyen de se connecter), `user_sessions` (la preuve qu'un
navigateur agit pour un utilisateur). Trois invariants qu'on ne « corrige » pas :

- **`users.email` n'est pas unique** — une identité externe inconnue crée
  **toujours** un nouvel utilisateur, même si l'adresse est déjà en base.
  Apparier sur l'adresse rouvrirait la prise de contrôle par pré-inscription ;
- la **seule** clé de résolution est le couple `(provider, subject)` — ni
  l'adresse, ni le login du fournisseur, qui se renomme et redevient
  enregistrable par un tiers ;
- **`users` ne porte aucun rôle**, et n'en portera pas. Le rôle de #115 est
  relatif à une **organisation** — on est administrateur *d'un club*, pas
  administrateur tout court — et vivra dans une association
  `(user, organisation, role)`. Un scalaire `role` posé ici serait à défaire par
  une migration destructive au premier utilisateur ayant deux rôles dans deux
  clubs. C'est le même raisonnement qui place le futur mot de passe sur
  `identities` : ce qui est relatif à un tiers ne se met pas en colonne sur
  `users`. Un test le vérifie sur le schéma appliqué, pas seulement sur le modèle.

**Jeton opaque, empreinte en base.** Le cookie porte `secrets.token_urlsafe(32)`
(43 caractères) ; la base n'en garde que le SHA-256. Aucun sel, aucun KDF : ce
que bcrypt compense — faible entropie et dictionnaire — n'existe pas ici, et un
KDF coûterait à **chaque** requête authentifiée. C'est la **garde de longueur**
(`session.TOKEN_MIN_LENGTH`) qui rend SHA-256 nu suffisant, pas l'algorithme :
le jour où un code court entrerait dans la même colonne, elle deviendrait
cassable hors ligne. Une session est acceptée **si et seulement si** elle existe,
n'a pas expiré, et que son utilisateur est actif — la troisième condition est une
**jointure**, jamais un cache.

**Le registre vit dans `services/auth/idp/`**, et le nom est délibéré : « provider »
désigne déjà un **chronométreur** partout ailleurs (`PendingProvider`,
`--provider`, `PROVIDER_LABELS`, `GET /scrape/detect`). Employer le même mot
créerait un second sens et un second `registry.py` homonyme. Le contrat
`IdentityProvider` **n'énumère aucun mécanisme** : `authorize()` rend un
`round_trip` opaque que le flux signe sans le lire, ce qui permettra à OIDC d'y
ranger son `nonce` sans toucher au contrat, au flux, ni au fournisseur GitHub.
Une doublure de test ne s'enregistre **jamais** au niveau module — elle
existerait en production, et `is_configured()` est un garde de configuration,
pas un garde de sécurité.

**Sept réglages `AUTH_*`** (`backend/README.md` pour le tableau,
`docs/ci-cd.md` pour les valeurs par environnement) : `AUTH_SESSION_SECRET_KEY`
(≥ 32 caractères ou le démarrage échoue ; **vide = non configuré**, état
légitime), `AUTH_GITHUB_CLIENT_ID` / `_SECRET`, `AUTH_REDIRECT_BASE_URL`
(origine de l'**interface**, jamais celle de l'API, et **sans défaut**),
`AUTH_COOKIE_SECURE` (dont le nom des cookies est **dérivé** : `__Host-` exige
`Secure`), `AUTH_SESSION_TTL_DAYS`, `AUTH_STATE_TTL_SECONDS`. Ils étaient huit :
`AUTH_ALLOWED_EMAILS` est passée en base (#170, section dédiée plus bas).

**Deux** de ces réglages sont **transverses** — la clé de signature et l'origine
de retour —, et ce sont eux qu'éprouve `Settings.auth_is_configured` ; les
secrets d'un fournisseur restent derrière son propre `is_configured()`. Les
mêler masquerait un second fournisseur pourtant
configuré et obligerait à modifier ce garde à chaque ajout, ce que FR-033
proscrit. Les **deux** gardes sont éprouvées à l'entrée du parcours, socle
d'abord : sans la clé, `joserfc` levait un `ValueError` nu qui ressortait en
**500** — une page technique dans un navigateur en pleine navigation, là où le
contrat impose un 503 lisible.

`AUTH_REDIRECT_BASE_URL` est dans ce garde pour une raison mesurée : elle part
dans le `redirect_uri` enregistré chez le fournisseur. Avec un défaut localhost,
un déploiement qui l'oubliait paraissait **pleinement configuré** — la page de
connexion affichait son bouton — pendant que GitHub répondait par sa propre page
d'erreur. Le visiteur ne revenait jamais, aucun code de l'ensemble fermé ne se
déclenchait, et rien n'était journalisé côté backend.

**Une installation non configurée le dit au démarrage, en développement.** Sur
une base SQLite, `main._warn_if_auth_unconfigured` journalise les réglages
transverses absents et les fournisseurs non configurés — sans rien changer au
comportement, FR-036 restant intact. Le silence complet coûtait une session de
diagnostic : un `backend/.env` nommé `.env.local` (la convention du **frontend**)
n'est pas lu par `pydantic-settings`, et le seul symptôme était un
`/auth/methods` à `[]`. Le discriminant est `is_sqlite`, déjà employé comme garde
« environnement jetable » par `scripts/reset_db.py`, et **pas** un neuvième
réglage ; en production le silence est délibéré. L'avertissement nomme les
fournisseurs par leur **slug** seul : le contrat `IdentityProvider` n'énumère
aucun mécanisme, et deviner `AUTH_<SLUG>_CLIENT_ID` le replacerait dans l'usine.

**La garde `/admin` ne ferme que si une connexion est possible.** Sans les
secrets, `/auth/me` rend 401 pour tout le monde : rediriger ferait de cet écran,
ouvert jusqu'ici, une impasse pour **tous** — l'inverse de FR-036. Elle
distingue donc « anonyme avéré » (401) de « on ne sait pas » (backend
injoignable), et ne redirige que dans le premier cas, `/auth/methods` non vide.

**Aucune route existante n'est protégée** — c'est le périmètre de #115 —, et la
garde `frontend/app/admin/layout.tsx` est **d'interface seulement** : elle évite
d'exposer un écran inutilisable, elle ne protège aucune donnée. Deux tests le
verrouillent : l'un parcourt l'inventaire des routes et refuse tout 401/403,
l'autre interdit une dépendance globale sur l'application et sur les routers
existants. La protection future se posera **route par route**, jamais par un
`dependencies=` global qui fermerait le site public sans qu'on le voie.

**Toute sortie HTTP du parcours passe par `core.http.guarded_transport()`.**
`OAuth2Client` d'Authlib hérite de `httpx.Client`, donc `transport=` y descend
nativement. Le détecteur AST de `tests/test_core_http.py` a été **étendu** pour
le voir — il était aveugle aux liaisons d'`authlib.integrations.httpx_client` et
à `httpx.HTTPTransport`, soit la première sortie HTTP qui aurait échappé au
filet de #101, à l'endroit exact où circulent un `client_secret` et un code
d'autorisation. `services/auth/idp/github.py` est, avec `core/http.py`, le seul
fichier de son allowlist (`_FABRIQUES`), et l'exemption est doublée d'un test
positif : nominative, jamais un motif de dossier.

**L'ordre du retour de parcours est contractuel**, pas stylistique : validation
locale → effacement du cookie d'état → présence du `code` → réseau (FR-025). Le
limiteur de threads AnyIO est mesuré à **40** et toutes les routes du projet sont
`def` : un retour de parcours coûteux est un levier de déni de service **sur le
site public**. Un test vérifie qu'aucun octet ne part sur chacun des chemins
d'échec local. Tout échec **redirige** vers `/login?error=<code>`, où `<code>`
appartient à un ensemble **fermé** de cinq valeurs anglaises traduites par
l'interface — jamais un message du fournisseur ni une donnée d'entrée.

Trois points que le code ne dit pas :

- **La fermeture en masse des sessions est une procédure, pas un outil.** Pour
  **un compte** : `is_active = False` ferme immédiatement toutes ses sessions,
  l'invariant étant une jointure. Pour **tous** : supprimer toutes les lignes de
  `user_sessions`. Aucune commande CLI n'est livrée — le dépôt n'a aucun
  ordonnanceur, et une commande que personne ne lance ferait croire à une
  hygiène qui n'existe pas. Les sessions expirées sont purgées **opportunément**,
  à l'ouverture d'une session, pour le seul utilisateur concerné.
  **Cet argument ne couvre que l'hygiène**, pas la révocation d'urgence : en
  incident, la procédure suppose d'ouvrir `psql` sur Supabase à la main. Les deux
  besoins ont été fondus à tort ; le second est suivi en #169, hors périmètre.
- **L'adresse refusée est journalisée, la table des tentatives est écartée.**
  Un refus `account_not_allowed` trace l'adresse soumise dans les journaux du
  backend : sans elle, aucun refus n'est diagnosticable et l'exploitant ne sait
  pas quelle adresse ajouter. Une adresse n'est pas un secret au sens de FR-038,
  dont le filet porte sur les clés, les jetons et le code de retour. Le refus
  pour **adresse non certifiée** ne la journalise pas — le fournisseur ne la
  prouve pas. Consigner ces tentatives **en base** a été demandé en revue et
  écarté (suivi en #170, avec le passage de la liste d'autorisation en base) : ce
  serait la seule écriture pilotée par un visiteur non authentifié, sans plafond,
  sur de la donnée personnelle de tiers. Raisonnement complet :
  `specs/20260801-145428-auth-socle-sso/data-model.md`, §Ce qu'aucune table
  n'enregistre.
- **Une rotation de `AUTH_SESSION_SECRET_KEY` ne ferme aucune session.** Le
  jeton de session est **opaque et vérifié en base**, il n'est pas signé : la clé
  ne signe que le jeton d'état, donc une rotation n'interrompt que les parcours
  de connexion en cours. Croire l'inverse ferait tenir une fuite pour colmatée.
- **Le piège multi-worktree.** Une application OAuth GitHub n'accepte **qu'une
  seule** URL de retour, port compris, et `next dev` d'un second worktree
  atterrit sur `:3001` sans le dire. L'authentification n'est donc utilisable que
  depuis l'espace de travail principal. Corollaire pour `backend/.env`, que
  `.worktreeinclude` recopie : n'y figez ni `AUTH_REDIRECT_BASE_URL` ni les
  identifiants OAuth. Le retour vise l'**interface**
  (`<origine>/api/v1/auth/github/callback`) et jamais le backend — le cookie
  d'état est posé sur l'origine de l'interface, et un retour pointant sur le port
  du backend ferait échouer **tout** parcours en `state_mismatch`.

# Autorisation (#115)

Le socle ci-dessus dit *qui* agit ; celui-ci dit *ce qu'il peut faire*. Spec,
plan et tâches : `specs/20260804-214724-auth-rbac-roles/`.

**Le pouvoir est dans le code, le rôle est en base.** `core/permissions.py` tient
la **liste de référence** des treize codes (`<domaine>:<geste>`) ; `roles`,
`role_permissions` et `user_roles` tiennent la composition et l'attribution,
éditables à chaud. Les deux se confondent facilement, et l'ont été : le code
porté par un rôle *est* une donnée en base — ce qui n'existe pas, c'est une table
`permissions` listant les codes possibles. Précédent du dépôt :
`Course.event_type`, chaîne en base et nomenclature en Python. Ajouter un pouvoir
est donc un membre de plus dans `P`, **jamais une migration**.

**`roles.is_superuser` referme la seule objection sérieuse** à ce partage : « une
fonctionnalité livrée mardi n'est administrable que si quelqu'un pense à cocher
son pouvoir ». Un rôle superutilisateur franchit tout pouvoir, présent **et à
venir** — le semis ne lui colle donc aucun code, lui donner ceux du jour le
figerait au jour d'aujourd'hui.

Cinq choses à ne pas défaire :

- **L'ordre 401-avant-403 est structurel.** `require_permission` compose
  `current_user` : une requête sans session n'atteint jamais le contrôle de
  pouvoir. Ce n'est pas un `if` défensif qu'on pourrait inverser par
  inadvertance.
- **La non-amplification est bornée à l'inventaire** (FR-011), à l'octroi comme
  au retrait, et cette borne est la **condition de réversibilité**. Un code
  périmé n'est porté par personne — pas même un superutilisateur, dont les
  pouvoirs effectifs *sont* le catalogue : le comparer rendrait son rôle
  immodifiable, et `is_system` ou attribué, indélébile. Un nettoyage de code
  ordinaire suffirait à geler un rôle définitivement.
- **Un code hors catalogue n'accorde rien et ne casse rien** (FR-042). La garde
  demande « porte-t-il *ce* code ? », jamais « quels codes porte-t-il ? » : les
  lignes orphelines sont inertes par construction. L'API les range dans
  `stale_permissions` ; la purge est l'effet d'un `PATCH`, il n'existe aucune
  ressource dédiée.
- **L'invariant du dernier administrateur garde l'état, pas les chemins** — et il
  garde la **perte** du dernier, pas l'absence. `administrateurs_preserves()`
  compare avant et après : sur une installation neuve personne n'est encore
  administrateur, et un invariant jugeant le seul état d'arrivée y refuserait
  *toute* opération, y compris sans rapport avec les superutilisateurs.
  409 et non 403 : l'appelant *est* administrateur, sa requête est bien formée,
  c'est le résultat qui est interdit.
- **Trois rôles sont semés, et ce semis ne se rejoue jamais** (FR-041) : `admin`
  (superutilisateur, aucun code), `validator` (`quality:override`), `moderator`
  (`pending_providers:read` **et** `:handle`, couplés — instruire sans pouvoir
  lire n'a pas de sens). Dès lors qu'un rôle est éditable à chaud, sa composition
  est une donnée d'exploitation : aucune migration ultérieure ne la réécrit.
  Ajouter un rôle *nouveau* par migration reste sans risque.

**Ce que le filet ne prouve plus.** `tests/test_auth/test_public_routes_still_open.py`
a changé de nature : il exige que toute ressource sous `/api/v1/admin/` soit
gardée ou **déclarée publique nommément**, et que les fermetures hors préfixe
(`POST`/`DELETE /participations`) le soient aussi. Il établit qu'une ressource
exige *un* pouvoir — jamais *qui* le porte : la composition est une donnée
d'exploitation, et c'est le prix assumé de l'édition sans redéploiement.

**`POST /admin/pending-providers` reste public**, et c'est ce qui interdit toute
garde par préfixe : le formulaire du site l'appelle en `.catch(() => {})` chez un
visiteur anonyme. Une garde de router supprimerait la fonctionnalité sans que
rien ne la nomme.

**Un point de reprise entoure l'écriture, jamais un `flush` d'après-coup.**
`role_repository.create` flushe lui-même : le `try/except IntegrityError` de
`create_role` enveloppait donc un `flush` sur une session déjà propre, et une
collision de slug sous concurrence sortait en **500** au lieu du 409 du contrat.
Corrigé en 2026-08 (revue de #197, dont le service jumeau portait le même
défaut), avec un test qui neutralise la lecture préalable pour atteindre la
contrainte. Le `SAVEPOINT` remplace aussi un `db.rollback()` qui emportait toute
la transaction en cours. Règle générale : **attraper l'`IntegrityError` là où
elle est levée**, c'est-à-dire autour de l'appel au repository.

**`grant-role` contourne délibérément deux règles** : la non-amplification (sans
session, il n'y a pas d'acteur dont comparer les pouvoirs — l'accès au serveur
*est* le privilège) et l'invariant du dernier administrateur (elle ne fait
qu'accorder). Voir `app/cli/AGENTS.md`.

# Liste d'autorisation en base (#170)

**Qui a le droit d'exister comme utilisateur est une donnée, plus un réglage.**
La table `allowed_emails` remplace `AUTH_ALLOWED_EMAILS` : ajouter un
contributeur était le geste d'administration le plus fréquent du club et le plus
coûteux — `get_settings` étant en `lru_cache`, il valait un redéploiement Render.
Spec, plan et tâches : `specs/20260806-174652-auth-liste-autorisation-base/`.

**Deux modules, deux responsabilités.** `provisioning.py` **lit** la liste au
passage d'une connexion (`_is_allowed(db, email)` → `allowed_email_repository`,
sans cache, à chaque tentative) ; `allowed_emails.py` l'**écrit**, depuis l'écran
ou depuis la CLI. Les fondre ferait rentrer `authorization` dans le chemin de
connexion, qui n'a rien à en savoir.

Cinq points à ne pas défaire :

- **`auth_is_configured` ne pèse plus la liste**, et c'est le seul écart au
  Principe IV de cette feature. `GET /auth/methods` annonce donc GitHub même
  avec une liste vide, là où il rendait `[]`. La faire peser là transformerait
  une route **publique et non authentifiée**, appelée par la page de connexion,
  en requête base — le levier de charge que #114 a fermé sur le retour de
  parcours (limiteur AnyIO mesuré à 40, toutes les routes en `def`). Le
  fail-closed n'est pas perdu : il tombe au **retour**, en `account_not_allowed`.
- **Un seul pouvoir, `allowed_emails:manage`**, et non une paire `read`/`write` :
  la liste n'a aucun lecteur autre que l'écran qui la modifie, un porteur du seul
  `read` regarderait un écran où tous les gestes échouent. Le rôle `admin` étant
  superutilisateur, il le franchit sans migration ni semis — c'est ce qui répond
  à « réservé aux administrateurs » **sans** nommer un rôle dans une garde.
- **Le retrait désactive, l'ajout réactive.** Retirer une adresse passe
  `is_active = False` sur les comptes qui la portent, ce qui fait tomber leurs
  sessions **immédiatement** (l'invariant de `session.resolve` est une jointure).
  La réactivation à l'ajout n'est pas un raffinement : sans elle, réinscrire
  quelqu'un ne rouvrirait rien — un compte désactivé est refusé *avant* que la
  liste ne soit consultée, et l'exploitant verrait l'adresse au tableau pendant
  que la personne reste dehors. **Échéance connue** : `is_active` acquiert ici son
  premier producteur applicatif ; le second sera #169 (révocation d'urgence), à
  qui il reviendra de distinguer « fermé parce que retiré » de « fermé parce que
  révoqué ». **Corollaire à ne pas découvrir en incident** : le retrait ne
  supprime aucune ligne de `user_sessions` — c'est la jointure qui refuse. Une
  réinscription dans la fenêtre de TTL (7 jours) **ressuscite donc les jetons
  exacts** que le retrait avait coupés, appareil oublié compris. L'écran dit
  « fermé immédiatement », et c'est vrai *tant que l'adresse reste absente* ;
  fermer pour de bon relève de #169.
- **`allowed_emails:manage` vaut en pratique « fermer n'importe quel compte ».**
  Un porteur non superutilisateur peut désactiver tout le monde sauf le dernier
  administrateur — un chemin qui ne traverse pas `assert_may_grant`, donc **hors
  de la non-amplification de #115**. Le plafond est l'invariant ci-dessous, et
  c'est le prix assumé d'un pouvoir unique : le scinder en `read`/`write` ne le
  changerait pas, seule une garde de non-amplification sur la désactivation le
  ferait, ce qu'aucun besoin exprimé ne réclame aujourd'hui.
- **L'invariant du dernier administrateur est celui de #115, réutilisé.**
  `remove()` s'exécute dans `authorization.administrateurs_preserves(db)`, sans
  argument d'organisation. La règle qui vient à l'esprit — « on ne retire pas sa
  propre adresse » — est trop stricte (un administrateur qui part, alors qu'un
  autre reste, en a le droit) et trop laxiste (retirer *l'autre* verrouille tout
  autant). 409, pas 403 : c'est le résultat qui est interdit.
- **La migration `a107b77b53e8` reprend `AUTH_ALLOWED_EMAILS` depuis
  `os.environ`**, une fois, au `alembic upgrade head` du `startCommand`. Sans
  elle, le déploiement mettait dehors toute la production, administrateurs
  compris. Ordre d'exploitation dans `docs/ci-cd.md` : déployer → vérifier →
  supprimer la variable. L'inverser vide la source de la reprise.

L'amorçage d'une base neuve passe par `python -m app.cli allow-email`
(`app/cli/AGENTS.md`) : liste vide → personne ne se connecte → personne n'ouvre
l'écran qui inscrirait la première adresse.
# Groupes d'appartenance (#197)

Un **groupe** dit à quoi on **appartient** — Codir, arbitres, commission
bénévolat. Un **rôle** dit ce qu'on **peut faire**. Deux objets, au sens de
GitHub Teams ou d'une OU LDAP. Spec, plan et tâches :
`specs/20260806-143225-auth-groupes-appartenance/`.

**Deux tables, `groups` et `user_groups`, et le patron de #115 à quatre
différences près.** Trois sont énoncées par l'issue, la quatrième est tombée à
l'arbitrage du 2026-08-06 :

- **pas d'`is_superuser`** — un groupe n'accorde rien ;
- **pas d'invariant du dernier membre** — vider un groupe ne verrouille personne
  dehors, à l'inverse du dernier administrateur ;
- **pas de non-amplification** — il n'y a aucun pouvoir à amplifier, et l'appeler
  quand même laisserait croire le contraire ;
- **`groups.organisation_id` est non nul**, là où celui de `roles` est nullable.
  Un rôle **global** est une définition réutilisable — « validateur » a le même
  sens dans deux clubs ; un groupe est une **composition**, celle d'un club
  précis, et « Codir » sans club ne désigne rien. Deux conséquences en cascade :
  cette table n'a pas besoin de l'index partiel `WHERE organisation_id IS NULL`
  à double dialecte qui garde `roles.slug`, et `user_groups` ne porte **aucune**
  colonne d'organisation — la répéter rendrait représentable un état incohérent
  qu'aucune contrainte portable ne fermerait.

**`services/auth/groups.py` est un module séparé, et c'est un choix de
vérifiabilité, pas de rangement.** AC6 exige qu'« aucune décision d'accès ne
consulte les groupes », et un test ne sait pas lire une intention. Deux modules
distincts rendent l'énoncé mécanique : ni `api/deps.py` ni `authorization.py` ne
**nomment** `Group`, `UserGroup`, `group_repository` ou `services.auth.groups` —
`tests/test_auth/test_groups_grant_nothing.py` le vérifie par lecture d'AST, et
la faute est éprouvée par mutation. Ce test **doit rougir le jour de la v2**,
quand des rôles portés par un groupe entreront dans la décision d'accès : on le
supprimera alors sciemment, et sa mort sera le signal que #197 a rempli son
office. Le contourner serait faire céder la borne en silence.

**La suppression d'un groupe peuplé est refusée** (409, le nombre dans le
message), et **aucune cascade** ne va de `Group` vers ses membres — la refuser
puis la laisser à l'ORM ferait tenir la règle par le seul chemin. Aucun droit
n'est pourtant perdu : ce qu'on protège est la **composition**, qu'aucune
migration ne reconstitue et qu'aucun autre système ne détient. Le miroir est
voulu : `User.groups` **cascade**, lui — supprimer quelqu'un emporte ses
appartenances, et le groupe survit.

**Trois filets touchent cette feature, et un seul a bougé.**
`test_permissions_catalogue.py` prend les trois pouvoirs neufs automatiquement
(il est paramétré sur `permissions.ALL`) et `test_public_routes_still_open.py`
classe les sept routes par la seule règle du préfixe `/api/v1/admin/` : ni l'un
ni l'autre n'a été modifié. **`tests/test_core/test_permissions.py`, lui, épingle
les codes à la main** et a dû être complété — c'est sa raison d'être : ajouter un
pouvoir doit être un geste conscient, et c'est le seul endroit du dépôt qui s'y
oppose. Le plan de la feature l'avait manqué ; le filet l'a rattrapé.

**Ce que la v1 ne fait pas**, et qui n'est pas un oubli : aucun groupe n'est semé
(la composition d'un CA n'est pas devinable par une migration, d'où l'absence
d'`is_system`), aucun groupe n'est imbriqué, aucune appartenance n'expire, et
aucun rôle n'est attaché à un groupe. Ce dernier point est la v2 — c'est lui qui
ferait entrer les groupes dans la décision d'accès, et il ne se décide pas là.
