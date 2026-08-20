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

**Cette règle est spécifique au RBAC (#115), pas à toute garde transverse.**
Le mot de passe d'accès au site (#509) pose bien un `dependencies=` global,
sur l'inclusion de chaque sous-router (`app/api/v1/router.py`) — délibérément,
pour la raison inverse : fermer le site public dans son ensemble est
exactement son but, pas un accident à éviter. Les deux gardes sont
orthogonales et compatibles : une session RBAC ne dispense pas du mot de
passe site, et réciproquement. Rationale complète dans le commentaire de
`app/api/v1/router.py` et dans
`docs/superpowers/specs/2026-08-20-mot-de-passe-site-design.md`.

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

- **L'hygiène est une procédure, la révocation d'urgence est un outil** (#169).
  Les deux avaient été fondus, et l'argument « le dépôt n'a aucun ordonnanceur,
  une commande que personne ne lance ferait croire à une hygiène qui n'existe
  pas » ne couvrait que le premier. Il tient toujours pour lui : les sessions
  **expirées** sont purgées opportunément, à l'ouverture d'une session, pour le
  seul utilisateur concerné, et un cron y serait du théâtre. Le second n'arrive
  jamais, sauf le jour où — et la procédure supposait alors d'ouvrir `psql` sur
  Supabase à la main, sous stress, en production. `session.revoke_all` /
  `revoke_for_email` sont désormais livrés par **deux** chemins, délibérément
  redondants : `python -m app.cli revoke-sessions` (`app/cli/AGENTS.md`) et
  `POST /admin/sessions/revoke` (pouvoir `sessions:revoke`), tous deux à deux
  portées — tout, ou une adresse. Le back-office est ergonomique là où l'exploitant
  est déjà connecté ; la CLI reste praticable le jour où c'est justement du
  back-office qu'on se méfie.
  **Révoquer et retirer ne sont pas le même geste**, et c'est ce que #170
  attendait : retirer une adresse pose `is_active = False` et ferme par la
  **jointure**, sans effacer une ligne — une réinscription dans la fenêtre de TTL
  ressuscite les jetons exacts. Révoquer **supprime** les lignes et ne désactive
  personne : on coupe des jetons, les comptes restent ouverts, chacun se
  reconnecte. Fermer *une adresse* durablement se fait des deux côtés :
  `revoke-sessions --email` en CLI, « Fermer les sessions » par ligne dans
  `/admin/acces`. **Même cible des deux côtés, l'adresse** : cet écran liste des
  autorisations, pas des comptes, et `users.email` n'étant pas unique, le geste
  frappe tous ceux qui la portent. **Corollaire d'exploitation** : une adresse
  retirée quitte la liste, donc ses sessions ne sont plus fermables depuis
  l'écran — fermer d'abord, retirer ensuite, ou passer par la CLI, à qui
  l'autorisation est indifférente.
  **`sessions:revoke` n'a aucun plafond, et c'est le seul pouvoir du dépôt dans
  ce cas.** `allowed_emails:manage` vaut « fermer n'importe quel compte » mais
  bute sur `administrateurs_preserves` ; ici rien n'est retiré, aucun code ne
  change de mains, donc ni la non-amplification, ni l'invariant du dernier
  administrateur, ni `assert_may_distribute_superuser` ne sont sur le chemin. Un
  porteur non superutilisateur qui répète le geste tient tout le monde dehors, y
  compris le dernier administrateur, et **aucune CLI ne retire rien**
  (`grant-role` n'accorde, `allow-email` n'inscrit) : reprendre la main
  passerait par la base. Le plafond réel est qu'une révocation *unique* est
  auto-réparatrice — les comptes restent actifs, chacun se reconnecte. Le reste
  suppose un porteur de confiance, ce qui est le modèle de menace du dépôt ;
  scinder le pouvoir n'y changerait rien, seule une garde de non-amplification
  sur la révocation le ferait, qu'aucun besoin exprimé ne réclame.
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
- **Comparer des codes ne suffit pas à garder le rôle superutilisateur** (#239).
  `admin` ne porte **aucun** code : la non-amplification n'avait rien à comparer
  et laissait un simple porteur de `roles:assign` distribuer l'administration
  entière — à quiconque et à lui-même. `assert_may_distribute_superuser` ferme
  l'attribution **et** le retrait : destituer un administrateur est un geste
  d'administrateur, et l'invariant du dernier ne garde que le *dernier*, pas
  l'avant-dernier. Toute nouvelle façon de faire changer un rôle de mains doit
  la rappeler — la garde des *attributs* (`assert_may_set_superuser`, FR-010) ne
  la couvre pas.
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

# Liste d'autorisation en base (#170) et groupes d'appartenance (#197)

Deux epics indépendantes, chacune sa propre table (`allowed_emails` ;
`groups`/`user_groups`), toutes deux hors de la décision d'accès de #115 —
détail, invariants et pièges mesurés dans `docs/auth/liste-autorisation.md` et
`docs/auth/groupes.md`.
