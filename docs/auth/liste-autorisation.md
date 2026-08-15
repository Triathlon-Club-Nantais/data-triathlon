# Liste d'autorisation en base (#170)

Renvoyé depuis `backend/app/services/auth/AGENTS.md`.

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
- **L'autorisation porte le rôle du premier jour** (`allowed_emails.role_id`,
  #239). Sans lui, le geste d'administration était coupé en deux par un
  événement que l'administrateur ne contrôle pas — la première connexion de la
  personne : autoriser, *attendre*, puis attribuer depuis un autre écran ; entre
  les deux, un connecté sans aucun rôle. Quatre propriétés le tiennent, et la
  première a demandé une correction — elle était affirmée avant d'être vraie :
  - **Il se réclame.** `claim_initial_role` le rend **et** le lève d'un seul
    `UPDATE … WHERE role_id = <lu>`, et `provisioning` ne donne le rôle que s'il
    l'a obtenu. Lire puis lever laissait une fenêtre de quelques millisecondes
    où deux premières connexions simultanées sur la même adresse repartaient
    toutes deux avec le rôle — et sous le modèle de menace du dépôt, ces deux
    identités ne sont pas la même personne. La consommation avait de surcroît
    rendu cette course **silencieuse** : `role_id` vaut `NULL` que le rôle ait
    été donné une fois ou deux. Une condition dans le `WHERE` plutôt qu'un
    verrou : celui-ci serait inerte en SQLite et actif en PostgreSQL.
    Laissé en place, « une fois » n'était vrai que *par compte* : toute identité
    externe inconnue en crée un nouveau **même si l'adresse est déjà en base**
    (FR-003), donc chaque identité suivante portant l'adresse serait repartie
    avec le rôle — y compris après une révocation, et longtemps après que celui
    qui l'a choisi a perdu le droit de le donner. C'est très exactement
    l'appariement par adresse que #114 refuse, sur le chemin qui accorde du
    pouvoir. Le corollaire opérationnel était pire que le cas d'attaque : un
    administrateur pouvait *garer* un rôle sur une adresse à lui, être destitué,
    puis renaître administrateur.
  - **Il ne s'applique qu'à la création du compte.** Ni à une reconnexion, ni à
    une réactivation — sinon un retrait de rôle serait défait par la prochaine
    connexion de l'intéressé, sans que rien ne le dise.
  - **Le contrôle porte sur le choix, jamais sur l'application.** C'est
    `allowed_emails._assert_may_choose` qui porte les gardes de `grant_role` —
    `roles:assign`, la remise du rôle, la portée d'organisation — là où il y a
    un acteur ; `provisioning` n'en a aucun. Même asymétrie que `grant-role`. Le
    troisième écrivain de `user_roles` avait été ajouté avec une seule d'entre
    elles, et c'est ainsi que ces règles se perdent. **Un acteur absent ne
    désactive plus rien** : nommer un rôle sans acteur lève `ValueError` au lieu
    de sauter les gardes en silence, l'écriture, elle, ayant toujours été
    inconditionnelle.
  - **Les deux côtés du changement se gardent, et ce qui se garde est le
    changement.** Lever un rôle avait d'abord été traité comme un non-geste,
    sous prétexte qu'il « ne donne rien à comparer » — c'est vrai
    d'`assert_may_grant`, qui compare des codes, et faux
    d'`assert_may_distribute_superuser`, qui demande « êtes-vous
    superutilisateur ? » et que `revoke_role` porte déjà : destituer un
    administrateur est un geste d'administrateur. Sans la symétrie ici, un
    porteur de `roles:assign` effaçait — ou remplaçait par un rôle faible — le
    rôle garé sur l'adresse d'un futur administrateur, qui naissait alors
    diminué : pas une escalade, un sabotage de nomination par le pouvoir le plus
    courant du back-office, et sans trace (`created_by` n'est pas réécrit à la
    réinscription). Symétriquement, un `role_id` qui **redit** ce qui est déjà
    posé ne fait rien changer de mains et n'exige donc rien : sans quoi
    `{email, role_id: null}` — corps que beaucoup de clients envoient par
    défaut, et que l'API acceptait avant #239 — deviendrait un refus
    d'autoriser.
  - **Rien de ce qui échoue à l'application ne refuse la connexion** : un rôle
    disparu, une base sans organisation ou un rôle devenu hors portée
    journalisent et passent. Un visiteur légitime laissé dehors par un code
    d'erreur qui n'explique rien serait pire que l'absence de rôle qu'on
    cherchait justement à éviter.
  Il ne contredit pas « cette table autorise, elle n'identifie pas » : il ne
  désigne aucun titulaire, il dit avec quoi celui qui viendra commencera — et
  parce qu'il se réclame, il ne le dit qu'une fois.
  **Limite connue, non fermée** : le contrôle portant sur le choix et l'effet
  étant différé, un administrateur peut garer un rôle sur une adresse à lui,
  être destitué, puis renaître avec ce rôle à sa prochaine connexion. La
  réclamation ramène ce rejeu d'« indéfini » à « une fois », elle ne le supprime
  pas. Ce qui manque n'est pas une garde mais une **revue** : rien ne balaie les
  rôles garés au départ d'un administrateur, et `AllowedEmailRead` ne porte ni la
  date ni l'auteur du *choix du rôle*, seulement ceux de l'inscription.
- **`null` lève le rôle, un champ absent n'y touche pas** (`UNCHANGED`). Les
  distinguer n'est pas une subtilité d'API : sans le premier, « Aucun » était
  indicible, le rôle se collait à l'adresse pour toujours, et le 409 de
  `delete_role` — « retirez-le d'abord de ces adresses » — réclamait un geste
  inexistant, rendant le rôle indélébile. Sans le second, `allow-email`, qui ne
  se prononce pas sur le rôle, effacerait en silence un choix fait à l'écran.
- **`has_account` dit « quelqu'un est venu », pas « qui »** (`AllowedEmailRead`).
  Un booléen, calculé par rapprochement d'adresses en une requête pour toute la
  liste — c'est le retour qui manquait sur le rôle ci-dessus : « déjà appliqué »
  et « attend toujours » se ressemblent sans lui. **Ne pas en faire un lien vers
  le compte** : `users.email` n'est pas unique (FR-003), une adresse peut en
  porter plusieurs, et choisir lequel serait exactement l'appariement par adresse
  que #114 interdit. Le rapprochement ignore la casse — `users.email` garde celle
  du fournisseur, `allowed_emails` la normalise.
- **Le retrait désactive, l'ajout réactive.** Retirer une adresse passe
  `is_active = False` sur les comptes qui la portent, ce qui fait tomber leurs
  sessions **immédiatement** (l'invariant de `session.resolve` est une jointure).
  La réactivation à l'ajout n'est pas un raffinement : sans elle, réinscrire
  quelqu'un ne rouvrirait rien — un compte désactivé est refusé *avant* que la
  liste ne soit consultée, et l'exploitant verrait l'adresse au tableau pendant
  que la personne reste dehors. **Échéance tenue** (#169) : `is_active` reste le
  seul producteur applicatif de ce chemin — la révocation d'urgence n'y touche
  **pas**, et c'est ainsi que « fermé parce que retiré » se distingue de « fermé
  parce que révoqué » : le premier ferme par la jointure et laisse les lignes, le
  second supprime les lignes et laisse le compte actif.
  **Corollaire à ne pas découvrir en incident** : le retrait ne
  supprime aucune ligne de `user_sessions` — c'est la jointure qui refuse. Une
  réinscription dans la fenêtre de TTL (7 jours) **ressuscite donc les jetons
  exacts** que le retrait avait coupés, appareil oublié compris. L'écran dit
  « fermé immédiatement », et c'est vrai *tant que l'adresse reste absente* ;
  fermer pour de bon est un `revoke-sessions --email <adresse>`.
- **`allowed_emails:manage` vaut en pratique « fermer n'importe quel compte ».**
  Un porteur non superutilisateur peut désactiver tout le monde sauf le dernier
  administrateur — un chemin qui ne traverse pas `assert_may_grant`, donc **hors
  de la non-amplification de #115**. Le plafond est l'invariant ci-dessous, et
  c'est le prix assumé d'un pouvoir unique : le scinder en `read`/`write` ne le
  changerait pas, seule une garde de non-amplification sur la désactivation le
  ferait, ce qu'aucun besoin exprimé ne réclame aujourd'hui.
  **Et il ne vaut pas « distribuer des rôles ».** Nommer un rôle initial sur une
  adresse exige `roles:assign` **en plus** (`_assert_may_choose`), bien que la
  route ne soit gardée que par `allowed_emails:manage` : donner un rôle est un
  geste d'attribution, qu'il porte sur un compte existant ou sur un compte à
  naître. Sans cette garde, ce pouvoir unique aurait absorbé le second en
  silence — la non-amplification borne ce qu'on donne, elle ne dit jamais qu'on
  a le droit de donner. Elle se pose **avant** la résolution du rôle : sinon le
  couple 404/201 balaie le catalogue pour qui n'a même pas `roles:read`.
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
