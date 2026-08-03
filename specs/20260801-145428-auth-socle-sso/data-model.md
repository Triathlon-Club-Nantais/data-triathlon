# Data Model — Socle d'authentification SSO (#114)

Phase 1. Trois tables nouvelles, **aucune table existante modifiée**. Une seule révision Alembic.

Conventions reprises de l'existant (`athlete.py`, `participation.py`, `course.py`) : contraintes
nommées `uq_*`, `created_at` alimenté par `app.core.time.utcnow` (jamais `datetime.utcnow` ni
`func.now()`), colonnes `DateTime` naïves en UTC, clés étrangères indexées et **sans** `ondelete`.

---

## `users` — l'identité applicative

| Colonne | Type | Contraintes | Rôle |
| --- | --- | --- | --- |
| `id` | `int` | PK | |
| `email` | `str` | non nul, indexé, **non unique** | Adresse de contact, rafraîchie depuis le fournisseur. |
| `is_active` | `bool` | non nul, défaut `True` | Une désactivation ferme immédiatement toutes les sessions (FR-015). |
| `created_at` | `datetime` | non nul, défaut `utcnow` | |
| `athlete_id` | `int \| None` | FK `athletes.id`, indexé, nullable | Rattachement facultatif, prévu mais non exploité ici. |

**`email` n'est délibérément pas unique.** C'est l'expression en base de FR-003 : deux identités
externes portant la même adresse donnent **deux** utilisateurs distincts. Poser un `UNIQUE` ici
forcerait un appariement par adresse et rouvrirait la prise de contrôle par pré-inscription
(cf. `research.md` §4). Ne pas « corriger » cette absence.

Pas d'`ondelete` sur `athlete_id` : `database.py` n'émet aucun `PRAGMA foreign_keys=ON`, la
contrainte serait inerte en SQLite et active en PostgreSQL (`research.md` §11).

**`athlete_id` est une colonne seule : aucune `relationship` vers `Athlete` n'est déclarée.** Rien
ici ne lit l'athlète rattaché, et un attribut dont le seul comportement serait de lever
(`lazy="raise"`, premier jet de cette feature) est un attribut qui existe pour ne pas servir. #117
la posera quand quelque chose la lira : une `relationship` n'émet aucun DDL, l'ajouter ne coûtera
pas de migration.

**Cardinalité fixée par cette colonne : N utilisateurs → 1 athlète**, et l'absence d'`UNIQUE` est
imposée par FR-003 au même titre que celle sur `email`. Puisqu'une identité externe inconnue crée
**toujours** un nouvel utilisateur, une même personne en aura plusieurs — un `UNIQUE` ici
interdirait de rattacher le second à l'athlète du premier. Un utilisateur, en revanche, ne se
rattache qu'à un seul athlète : ce que le rattachement désigne, c'est *qui court*, jamais une liste.

**N'accueillera PAS `role`** (FR-041, SC-014). Le rôle de #115 est relatif à une **organisation** —
on est administrateur *d'un club*, pas administrateur tout court — et se portera donc par une
association `(user, organisation, role)`, hors de cette table. C'est exactement le raisonnement
appliqué plus bas au futur mot de passe, qui vit sur `identities` et non ici : ce qui est relatif à
un tiers ne se met pas en colonne sur `users`, sous peine d'avoir à l'en défaire.

Cette table reste donc **inchangée** par #115 : aucune colonne à ajouter, aucune à retirer. Elle
accueille en revanche sans restructuration l'exploitation de `athlete_id` (#117), déjà présent.

---

## `identities` — un moyen de se connecter

| Colonne | Type | Contraintes | Rôle |
| --- | --- | --- | --- |
| `id` | `int` | PK | |
| `user_id` | `int` | FK `users.id`, non nul, indexé | |
| `provider` | `str` | non nul | Identifiant court du moyen de connexion (`github`). |
| `subject` | `str` | non nul | Identifiant **opaque** chez le fournisseur. Stocké en `str` : un entier déborderait sur certains dialectes et n'est pas la forme de tous les fournisseurs. |
| `email` | `str` | non nul | Adresse **constatée chez ce fournisseur**, distincte de `users.email`. |
| `secret_hash` | `str \| None` | nullable | Vide pour une identité déléguée. Accueille le futur mot de passe. |
| `created_at` | `datetime` | non nul, défaut `utcnow` | |

**Contrainte** : `UniqueConstraint("provider", "subject", name="uq_identity_provider_subject")`.

C'est la **seule** clé de résolution (FR-002). Une ligne d'`identities` = un moyen de connexion,
révocable unitairement — ce qui est la raison pour laquelle le futur mot de passe vit **ici** et non
sur `users` : « supprimer ma connexion par mot de passe » doit être la suppression d'une ligne, pas
la mise à nul d'une colonne sur l'utilisateur.

Plusieurs identités peuvent pointer un même utilisateur. **Aucune n'est créée automatiquement à
partir d'une autre** : cette feature n'en crée jamais qu'une, à la première connexion.

---

## `user_sessions` — la preuve qu'un navigateur agit pour un utilisateur

| Colonne | Type | Contraintes | Rôle |
| --- | --- | --- | --- |
| `id` | `int` | PK | Ne franchit **jamais** l'API (identifiant séquentiel, énumérable). |
| `user_id` | `int` | FK `users.id`, non nul, indexé | |
| `token_hash` | `str` | non nul, **unique**, indexé | SHA-256 hexadécimal du jeton opaque. |
| `expires_at` | `datetime` | non nul, indexé | |
| `created_at` | `datetime` | non nul, défaut `utcnow` | |

**Contrainte** : `UniqueConstraint("token_hash", name="uq_user_session_token")`.

Nommée `user_sessions` et non `sessions` : `Session` désignerait deux choses dans des modules qui
importent aussi SQLAlchemy.

Le jeton brut n'existe qu'en mémoire et dans le cookie. La base n'en garde que l'empreinte
(FR-012). Une garde refuse d'ouvrir une session sur un jeton de moins de 43 caractères — c'est elle
qui rend SHA-256 nu suffisant, et non l'algorithme (`research.md` §3).

**Trois colonnes délibérément absentes**, toutes ajoutables plus tard par migration purement
additive : `last_seen_at` (une écriture par requête authentifiée pour zéro lecteur),
`user_agent` (donnée quasi personnelle sans durée de conservation), et `revoked_at` — la
déconnexion **supprime** la ligne, un effacement logique ne payant que pour un écran « mes
sessions » (#117) qui n'est pas livré.

---

## Invariant de validité — vérifié par test

Une session est acceptée **si et seulement si** les trois conditions suivantes sont réunies
(FR-013) :

1. une ligne `user_sessions` porte l'empreinte du jeton présenté ;
2. `expires_at` est dans le futur ;
3. l'utilisateur joint est `is_active`.

La troisième condition est une **jointure**, jamais un cache : c'est elle qui rend FR-015 vrai sans
avoir à parcourir les sessions à la désactivation. La désactivation d'un compte ferme donc ses
sessions **immédiatement**, y compris celles déjà en cours.

---

## Cycle de vie

```text
Connexion réussie
  └─ résolution (provider, subject)
       ├─ identité connue  → utilisateur existant, email rafraîchi
       └─ identité inconnue → NOUVEL utilisateur + NOUVELLE identité
                              (même si l'email existe déjà — FR-003)
  └─ suppression des sessions expirées de cet utilisateur (hygiène opportuniste)
  └─ création d'une session : jeton opaque en mémoire, empreinte en base

Requête authentifiée
  └─ empreinte du jeton → ligne → non expirée → utilisateur actif → utilisateur

Déconnexion
  └─ SUPPRESSION de cette ligne seule (les autres appareils survivent — FR-014)

Désactivation d'un compte
  └─ is_active = False → toutes ses sessions cessent d'être acceptées (FR-015)
     et un moyen d'exploitation permet d'en supprimer les lignes (FR-016)
```

---

## Ce qu'aucune table n'enregistre : les tentatives refusées

Une **quatrième table** consignant les connexions refusées — pour ajouter ensuite l'adresse depuis
le back-office, avec `AUTH_ALLOWED_EMAILS` lui-même passé en base — a été demandée en revue et
**écartée de cette feature**. Le besoin est réel ; la table est le mauvais outil pour y répondre
ici, pour trois raisons qui ne dépendent pas du calendrier :

- **ce serait la seule écriture en base pilotée par un visiteur non authentifié.** Tout porteur d'un
  compte GitHub y insérerait une ligne, sans plafond ni limitation de débit — une croissance de
  table commandée de l'extérieur, sur la base qui sert le site public ;
- **ce sont des données personnelles de tiers non consentants**, conservées sans durée définie. Le
  refusé n'est, par construction, pas un utilisateur : on n'a aucun titre à garder son adresse
  indéfiniment ;
- **un écran d'administration qui les affiche rend du texte d'origine externe.** Le nom
  d'affichage et l'adresse viennent du fournisseur, pas de nous.

Ce que cette feature fait à la place : **journaliser l'adresse refusée** côté backend
(`provisioning.resolve_user`, refus `account_not_allowed` uniquement). Cela ferme le trou réel — sans
cette trace, un refus n'était pas diagnosticable et l'exploitant ne savait pas quelle adresse
ajouter — sans rien conserver, sans écriture pilotée de l'extérieur, et dans un support dont la
rétention est déjà bornée par l'hébergeur. L'asymétrie est voulue : le refus pour **adresse non
certifiée** ne journalise pas l'adresse, que le fournisseur ne prouve pas et sur laquelle
l'exploitant n'a rien à faire.

Une adresse n'est pas un secret au sens de FR-038, dont le filet
(`tests/test_auth/test_no_secret_logged.py`) porte sur les clés, les jetons et le code de retour.

Le frottement qui motive la demande reste entier et est **hors périmètre** (suivi en #170) :
`get_settings` étant en `lru_cache`, ajouter un contributeur exige aujourd'hui un redéploiement. Le déplacement de la liste
en base ne demande d'ailleurs **aucune restructuration** — `provisioning.py` est déjà l'endroit
prévu pour cette évolution (l'en-tête du module le dit), `resolve_user` a la `Session` sous la main
et `_is_allowed` n'a qu'un appelant. Un seul point d'architecture sera à trancher alors :
`Settings.auth_is_configured` compte aujourd'hui `auth_allowed_emails` parmi les réglages
transverses, et ce garde de **configuration** deviendrait une requête en **base** à chaque appel de
`/auth/methods`.

---

## Migration Alembic

Une révision, trois `create_table`, aucune modification de table existante (FR : le site public
reste intact). La révision doit être relue à la main après génération, conformément aux contraintes
additionnelles de la constitution.

**Deux points à ne pas oublier**, sans quoi l'échec est obscur :

- `app/models/__init__.py` doit importer et exporter les trois modèles. `tests/conftest.py` fait
  `import app.models` puis `Base.metadata.create_all(...)` : sans cet import, les tables n'existent
  pas dans la base de test.
- Les contraintes doivent être **nommées** (`uq_identity_provider_subject`,
  `uq_user_session_token`), faute de quoi la révision descendante est indéterminée sur SQLite.

La révision est vérifiée en `upgrade` → `downgrade` → `upgrade`, comme le fait déjà
`tests/test_migrations.py`.
